import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parse } from 'csv-parse/sync';
import { createPool, migrate } from '../server/db.mjs';

const seedPaths = (process.env.SEED_FILE
  ? [process.env.SEED_FILE]
  : ['seeds/nfra_penalties.csv', 'seeds/nfra_penalties_incremental.csv']
).map(path => resolve(path));
const files = await Promise.all(seedPaths.map(path => readFile(path, 'utf8')));
const rows = files.flatMap((text, index) => parse(text, { bom: true, columns: true, skip_empty_lines: true })
  .map(row => ({ ...row, _seed_origin: index === 0 ? 'snapshot' : 'incremental' })));
const importName = process.env.SEED_FILE ? seedPaths[0] : 'default';
const importHash = createHash('sha256').update(files.join('\n')).digest('hex');
const headers = [
  '被处罚单位（公司）', '被处罚单位（分行）', '被处罚个人', '机构类型', '机构大类',
  '文号', '地区', '机关', '违法违规事实', '处罚决定', '处罚对象', '处罚依据',
  '处罚金额', '发布时间', '合规风险点', '处罚类型', '处罚案由', '处罚机关',
  '处罚书url', 'update_time',
];
const columns = [
  'source_key', 'source_row_number', 'content_hash', 'company', 'branch', 'person',
  'institution_type', 'institution_sector', 'decision_no', 'region', 'agency',
  'violation', 'decision_text', 'penalty_subject', 'legal_basis', 'amount_raw',
  'amount_yuan', 'published_date', 'risk_points', 'penalty_types', 'causes',
  'penalty_authority', 'notice_url', 'source_update_time', 'seed_origin',
];
const hash = value => createHash('sha256').update(value).digest('hex');
const optional = value => value === '' ? null : value;

function amountYuan(raw) {
  if (!raw) return null;
  const value = raw.replaceAll(',', '');
  const match = value.match(/[0-9]+(?:\.[0-9]+)?/);
  if (!match) return null;
  const amount = Number(match[0]) * (/亿/.test(value) ? 1e8 : /万/.test(value) ? 1e4 : 1);
  return Number.isFinite(amount) ? amount : null;
}

function valuesFor(row) {
  for (const name of ['source_key', 'seed_row_number', ...headers]) {
    if (!(name in row)) throw new Error(`Seed is missing column ${name}.`);
  }
  if (!/^[a-f0-9]{64}$/.test(row.source_key)) throw new Error('Invalid source_key.');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(row['发布时间'])) throw new Error('Invalid publication date.');
  if (!['银行', '保险', '其他'].includes(row['机构大类'])) throw new Error('Invalid institution sector.');
  if (!['机构', '个人'].includes(row['处罚对象'])) throw new Error('Invalid penalty subject.');
  const contentHash = hash(JSON.stringify(headers.map(name => row[name])));
  return [
    row.source_key, Number(row.seed_row_number), contentHash,
    optional(row['被处罚单位（公司）']), optional(row['被处罚单位（分行）']), optional(row['被处罚个人']),
    optional(row['机构类型']), row['机构大类'], optional(row['文号']), optional(row['地区']),
    optional(row['机关']), optional(row['违法违规事实']), optional(row['处罚决定']),
    row['处罚对象'], optional(row['处罚依据']), optional(row['处罚金额']),
    amountYuan(row['处罚金额']), row['发布时间'], optional(row['合规风险点']),
    optional(row['处罚类型']), optional(row['处罚案由']), optional(row['处罚机关']),
    optional(row['处罚书url']), optional(row.update_time), row._seed_origin,
  ];
}

if (!rows.length) throw new Error('Seed CSV has no records.');
const keys = new Set();
const records = rows.map(row => {
  const values = valuesFor(row);
  if (keys.has(values[0])) throw new Error(`Duplicate source_key: ${values[0]}`);
  keys.add(values[0]);
  return values;
});

if (process.argv.includes('--check')) {
  const sectorCounts = rows.reduce((counts, row) => {
    counts[row['机构大类']] = (counts[row['机构大类']] || 0) + 1;
    return counts;
  }, {});
  console.log(JSON.stringify({ rows: records.length, columns: headers.length, sectorCounts,
    incrementalRows: rows.filter(row => row._seed_origin === 'incremental').length }));
  process.exit(0);
}

const pool = createPool();
if (!pool) throw new Error('Set DATABASE_URL before importing the seed.');

try {
  await migrate(pool);
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('SELECT pg_advisory_xact_lock(756139272)');
    const previousImport = await client.query(
      'SELECT content_hash FROM nfra_seed_imports WHERE name = $1', [importName]
    );
    const unchanged = previousImport.rows[0]?.content_hash === importHash;
    let changed = 0;
    for (let start = 0; start < (unchanged ? 0 : records.length); start += 250) {
      const batch = records.slice(start, start + 250);
      const params = batch.flat();
      const placeholders = batch.map((_, index) =>
        `(${columns.map((__, column) => `$${index * columns.length + column + 1}`).join(',')})`
      ).join(',');
      const updates = columns.filter(name => name !== 'source_key').map(name =>
        `${name} = EXCLUDED.${name}`
      ).join(',\n');
      const result = await client.query(`
        INSERT INTO nfra_penalties (${columns.join(',')}) VALUES ${placeholders}
        ON CONFLICT (source_key) DO UPDATE SET ${updates}, updated_at = now()
        WHERE nfra_penalties.content_hash IS DISTINCT FROM EXCLUDED.content_hash
          OR nfra_penalties.source_row_number IS DISTINCT FROM EXCLUDED.source_row_number
      `, params);
      changed += result.rowCount;
    }
    let deleted = 0;
    if (!unchanged && !process.env.SEED_FILE) {
      const incrementalKeys = rows.filter(row => row._seed_origin === 'incremental').map(row => row.source_key);
      const removed = await client.query(
        'DELETE FROM nfra_penalties WHERE seed_origin = $1 AND NOT (source_key = ANY($2::text[]))',
        ['incremental', incrementalKeys]
      );
      deleted = removed.rowCount;
    }
    if (!unchanged) {
      await client.query(`
        INSERT INTO nfra_seed_imports (name, content_hash) VALUES ($1, $2)
        ON CONFLICT (name) DO UPDATE SET content_hash = EXCLUDED.content_hash, imported_at = now()
      `, [importName, importHash]);
    }
    const total = await client.query('SELECT count(*)::int AS total FROM nfra_penalties');
    await client.query('COMMIT');
    console.log(JSON.stringify({ seedRows: records.length, insertedOrUpdated: changed,
      deleted, unchanged, databaseRows: total.rows[0].total }));
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
} finally {
  await pool.end();
}
