import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { PGlite } from '@electric-sql/pglite';
import { PENALTIES_QUERY } from '../server/app.mjs';

test('PostgreSQL schema accepts a penalty and serves the frontend field names', async () => {
  const db = new PGlite();
  try {
    const migration = await readFile(new URL('../migrations/001_create_nfra_penalties.sql', import.meta.url), 'utf8');
    await db.exec(migration);
    await db.exec(await readFile(new URL('../migrations/002_track_seed_import.sql', import.meta.url), 'utf8'));
    await db.query(`
      INSERT INTO nfra_penalties
        (source_key, source_row_number, content_hash, company, person, institution_type,
         institution_sector, penalty_subject, published_date, amount_raw, amount_yuan)
      VALUES ($1, 1, $2, '示例银行', '张某', '城市商业银行', '银行', '个人', '2024-01-02', '50000', 50000)
    `, ['a'.repeat(64), 'b'.repeat(64)]);
    const result = await db.query(PENALTIES_QUERY);
    assert.equal(result.rows.length, 1);
    assert.equal(result.rows[0]['被处罚单位（公司）'], '示例银行');
    assert.equal(result.rows[0]['被处罚个人'], '张某');
    assert.equal(result.rows[0]['机构大类'], '银行');
    assert.equal(result.rows[0]['发布时间'], '2024-01-02');
    const origin = await db.query('SELECT seed_origin FROM nfra_penalties WHERE source_key = $1', ['a'.repeat(64)]);
    assert.equal(origin.rows[0].seed_origin, 'snapshot');
    await assert.rejects(
      db.query(`INSERT INTO nfra_penalties (source_key, source_row_number, content_hash, institution_sector, published_date) VALUES ($1, 2, $2, '错误类别', '2024-01-02')`, ['c'.repeat(64), 'd'.repeat(64)]),
    );
  } finally {
    await db.close();
  }
});

test('PBOC schema stores the shared seed and remains separate from NFRA', async () => {
  const { parse } = await import('csv-parse/sync');
  const db = new PGlite();
  try {
    for (const name of ['001_create_nfra_penalties.sql', '002_track_seed_import.sql', '004_pboc_penalties.sql']) {
      await db.exec(await readFile(new URL(`../migrations/${name}`, import.meta.url), 'utf8'));
    }
    const rows = parse(await readFile(new URL('../seeds/pboc_penalties.csv', import.meta.url), 'utf8'), { bom: true, columns: true });
    for (const row of rows) await db.query(`INSERT INTO pboc_penalties
      (source_key,source_row_number,content_hash,company,person,institution_sector,penalty_subject,published_date,amount_raw)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)`, [row.source_key,Number(row.seed_row_number),'a'.repeat(64),row['被处罚单位（公司）'],row['被处罚个人'],row['机构大类'],row['处罚对象'],row['发布时间'],row['处罚金额']]);
    const result = await db.query(PENALTIES_QUERY.replace('FROM nfra_penalties','FROM pboc_penalties'));
    assert.equal(result.rows.length, rows.length);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM nfra_penalties')).rows[0].n, 0);
    assert.equal(result.rows[0]['发布时间'], rows.map(row=>row['发布时间']).sort().at(-1));
    await assert.rejects(db.query('INSERT INTO pboc_penalties SELECT * FROM pboc_penalties LIMIT 1'));
  } finally { await db.close(); }
});
