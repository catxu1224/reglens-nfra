import { createHash } from 'node:crypto';
import { mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { parse } from 'csv-parse/sync';
import { stringify } from 'csv-stringify/sync';

const input = resolve(process.argv[2] || 'data/nfra_penalties_3yearsv3.csv');
const output = resolve(process.argv[3] || 'seeds/nfra_penalties.csv');
const raw = await readFile(input, 'utf8');
const rows = parse(raw, { bom: true, columns: true, skip_empty_lines: true });
if (!rows.length) throw new Error('Source CSV has no records.');

const columns = Object.keys(rows[0]);
if (columns.length !== 20 || !columns.includes('机构类型') || !columns.includes('机构大类') || !columns.includes('处罚书url')) {
  throw new Error('Source CSV does not match the expected 20-column schema.');
}

const identityFields = columns.filter(name => name !== 'update_time');
const occurrences = new Map();
const hash = value => createHash('sha256').update(value).digest('hex');
const seed = rows.map((row, index) => {
  const signature = hash(JSON.stringify(identityFields.map(name => row[name])));
  const occurrence = (occurrences.get(signature) || 0) + 1;
  occurrences.set(signature, occurrence);
  return {
    source_key: hash(`NFRA:${signature}:${occurrence}`),
    seed_row_number: index + 1,
    ...row,
  };
});

const temp = `${output}.tmp`;
await mkdir(dirname(output), { recursive: true });
await writeFile(temp, '\ufeff' + stringify(seed, { header: true, columns: ['source_key', 'seed_row_number', ...columns] }), 'utf8');
await rename(temp, output);
console.log(`Built seed with ${seed.length} rows at ${output}`);
