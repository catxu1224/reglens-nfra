import assert from 'node:assert/strict';
import { once } from 'node:events';
import { test } from 'node:test';
import { createApp, PENALTIES_QUERY } from '../server/app.mjs';

test('API serves database rows and does not expose seed files', async () => {
  const queries = [];
  const pool = {
    async query(sql) {
      queries.push(sql);
      if (sql === 'SELECT 1') return { rows: [{ '?column?': 1 }] };
      return { rows: [{
        source_key: 'a'.repeat(64),
        '被处罚单位（公司）': '示例银行',
        '被处罚个人': '张某',
        '机构大类': '银行',
        '处罚对象': '个人',
        '发布时间': '2024-01-02',
      }] };
    },
  };
  const server = createApp(pool).listen(0, '127.0.0.1');
  await once(server, 'listening');
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const health = await fetch(`${base}/api/health`);
    assert.equal(health.status, 200);
    const response = await fetch(`${base}/api/penalties`);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('cache-control'), 'no-store');
    const payload = await response.json();
    assert.equal(payload.count, 1);
    assert.equal(payload.source, 'postgresql');
    assert.equal(payload.rows[0]['机构大类'], '银行');
    assert.equal(payload.rows[0]['处罚对象'], '个人');
    assert(queries.includes(PENALTIES_QUERY));
    assert.equal((await fetch(`${base}/`)).status, 200);
    assert.equal((await fetch(`${base}/data/china-provinces.json`)).status, 200);
    assert.equal((await fetch(`${base}/seeds/nfra_penalties.csv`)).status, 404);
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
});

test('API serves the seed snapshot when the database is not configured', async () => {
  const server = createApp(null).listen(0, '127.0.0.1');
  await once(server, 'listening');
  try {
    const response = await fetch(`http://127.0.0.1:${server.address().port}/api/penalties`);
    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.source, 'seed');
    assert.equal(payload.count, 22054);
    assert.equal(payload.rows[0]['机构大类'] !== undefined, true);
    const health = await fetch(`http://127.0.0.1:${server.address().port}/api/health`);
    assert.equal((await health.json()).status, 'seed_only');
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
});
