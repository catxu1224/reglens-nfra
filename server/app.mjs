import compression from 'compression';
import express from 'express';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { parse } from 'csv-parse/sync';
import { generateAiReport } from './report-ai.mjs';

const root = new URL('../', import.meta.url);
const publicFiles = [
  'index.html', 'app.js', 'ui-upgrade.js', 'trend-upgrade.js',
  'home-upgrade.js', 'regulator-tabs.js', 'risk-cloud.js',
  'report.js', 'report-core.mjs', 'report.css',
  'styles.css', 'overrides.css', 'data/china-provinces.json',
  'assets/reglens-logo.png',
];

export const PENALTIES_QUERY = `
  SELECT
    source_key AS "source_key",
    company AS "被处罚单位（公司）",
    branch AS "被处罚单位（分行）",
    person AS "被处罚个人",
    institution_type AS "机构类型",
    institution_sector AS "机构大类",
    decision_no AS "文号",
    region AS "地区",
    agency AS "机关",
    violation AS "违法违规事实",
    decision_text AS "处罚决定",
    penalty_subject AS "处罚对象",
    legal_basis AS "处罚依据",
    amount_raw AS "处罚金额",
    to_char(published_date, 'YYYY-MM-DD') AS "发布时间",
    risk_points AS "合规风险点",
    penalty_types AS "处罚类型",
    causes AS "处罚案由",
    penalty_authority AS "处罚机关",
    notice_url AS "处罚书url",
    source_update_time AS "update_time"
  FROM nfra_penalties
  ORDER BY published_date DESC, source_row_number
`;

export function createApp(pool) {
  const app = express();
  let pbocSeedRowsPromise;
  const pbocSeedRows = () => pbocSeedRowsPromise ||= readFile(new URL('../seeds/pboc_penalties.csv', import.meta.url), 'utf8')
    .then(text => parse(text, { bom: true, columns: true, skip_empty_lines: true }))
    .then(rows => rows.map(({ seed_row_number, ...row }) => row));
  let seedRowsPromise;
  const seedRows = () => {
    seedRowsPromise ||= Promise.all([
      readFile(new URL('../seeds/nfra_penalties.csv', import.meta.url), 'utf8'),
      readFile(new URL('../seeds/nfra_penalties_incremental.csv', import.meta.url), 'utf8'),
    ])
      .then(files => files.flatMap(text => parse(text, { bom: true, columns: true, skip_empty_lines: true })))
      .then(rows => rows.map(({ seed_row_number, ...row }) => row));
    return seedRowsPromise;
  };
  app.disable('x-powered-by');
  app.use(compression());
  app.use(express.json({ limit: '60kb' }));

  app.post('/api/report-insights', async (req, res) => {
    res.set('Cache-Control', 'no-store');
    try {
      const analysis = await generateAiReport(req.body || {});
      res.json({ analysis });
    } catch (error) {
      const reason = String(error.message || 'unknown');
      const invalid = ['invalid_provider', 'invalid_region', 'invalid_model', 'invalid_api_key', 'invalid_report', 'empty_report'].includes(reason);
      res.status(invalid ? 400 : 502).json({ error: /^(deepseek|qwen)_\d+$/.test(reason) ? reason : invalid ? reason : 'model_request_failed' });
    }
  });

  app.get('/api/health', async (_req, res) => {
    if (!pool) {
      try {
        return res.json({ status: 'seed_only', count: (await seedRows()).length });
      } catch {
        return res.status(503).json({ status: 'seed_unavailable' });
      }
    }
    try {
      await pool.query('SELECT 1');
      res.json({ status: 'ok' });
    } catch {
      res.status(503).json({ status: 'database_unavailable' });
    }
  });

  let pbocNoticeFieldsPromise;
  app.get('/api/pboc/coverage', async (_req, res) => {
    res.set('Cache-Control', 'no-store');
    try {
      const registry = JSON.parse(await readFile(new URL('../config/pboc_branches.json', import.meta.url), 'utf8'));
      const state = JSON.parse(await readFile(new URL('../seeds/pboc_crawl_state.json', import.meta.url), 'utf8'));
      res.json({ totalBranches: registry.branches.length, verifiedDirectories: registry.branches.filter(branch=>branch.status==='verified').length,
        parsedNotices: Object.keys(state.done).length, pendingTasks: state.queue.length,
        failedTasks: Object.keys(state.failures).length, updatedAt: state.updated_at,
        branches: Object.entries(state.coverage || {}).map(([name, value])=>({name,...value})) });
    } catch { res.status(503).json({ error: 'pboc_coverage_unavailable' }); }
  });

  app.get('/api/pboc/notice-fields', async (_req, res) => {
    res.set('Cache-Control', 'no-store');
    try {
      const fields = ['notice_url', 'decision_no', 'party_name', 'decision_date', 'disclosure_period', 'remarks'];
      pbocNoticeFieldsPromise ||= readFile(new URL('../seeds/pboc_notice_fields.json', import.meta.url), 'utf8').then(JSON.parse)
        .then(rows => rows.map(row => Object.fromEntries(fields.map(key => [key, row[key] || '']))));
      res.json({ rows: await pbocNoticeFieldsPromise });
    } catch {
      pbocNoticeFieldsPromise = undefined;
      res.status(503).json({ error: 'pboc_notice_fields_unavailable' });
    }
  });

  app.get('/api/penalties', async (req, res) => {
    const regulator = req.query.regulator || 'nfra';
    if (!['nfra', 'pboc'].includes(regulator)) return res.status(400).json({ error: 'invalid_regulator' });
    const selectedSeedRows = regulator === 'pboc' ? pbocSeedRows : seedRows;
    res.set('Cache-Control', 'no-store');
    if (!pool) {
      try {
        const rows = await selectedSeedRows();
        return res.json({ source: 'seed', count: rows.length, rows });
      } catch (error) {
        console.error('Seed read failed:', error);
        return res.status(503).json({ error: 'seed_unavailable' });
      }
    }
    try {
      const { rows } = await pool.query(regulator === 'pboc' ? PENALTIES_QUERY.replace('FROM nfra_penalties', 'FROM pboc_penalties') : PENALTIES_QUERY);
      res.json({ source: 'postgresql', count: rows.length, rows });
    } catch (error) {
      console.error('Penalty query failed:', error);
      res.status(503).json({ error: 'database_unavailable' });
    }
  });

  app.get('/', (_req, res) => res.sendFile(fileURLToPath(new URL('../index.html', import.meta.url))));
  for (const name of publicFiles) {
    app.get(`/${name}`, (_req, res) => res.sendFile(fileURLToPath(new URL(name, root))));
  }
  app.use((_req, res) => res.status(404).send('Not found'));
  return app;
}
