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
    await assert.rejects(
      db.query(`INSERT INTO nfra_penalties (source_key, source_row_number, content_hash, institution_sector, published_date) VALUES ($1, 2, $2, '错误类别', '2024-01-02')`, ['c'.repeat(64), 'd'.repeat(64)]),
    );
  } finally {
    await db.close();
  }
});
