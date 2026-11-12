import assert from 'node:assert/strict';
import { test } from 'node:test';
import { aiInput, buildReportModel, periodLabel } from '../report-core.mjs';

test('report period labels distinguish year, quarter and month', () => {
  assert.equal(periodLabel(['2026-10'], []), '2026年10月');
  assert.equal(periodLabel(['2026-04', '2026-05', '2026-06'], []), '2026年第2季度');
  assert.equal(periodLabel(Array.from({ length: 12 }, (_, i) => `2025-${String(i + 1).padStart(2, '0')}`), []), '2025年');
});

test('report counts multi-label risks, ranks fines and cites only observed laws', () => {
  const rows = [
    { company: '甲银行', audience: '机构', institutionType: '城市商业银行', region: '北京市', riskTokens: ['信贷管理', '数据质量'], risk: '信贷管理、数据质量', amount: 1000000, published: '2026-10-02', decisionNo: '甲1', violation: '贷款管理不尽职', decision: '罚款', legal: '《中华人民共和国银行业监督管理法》第四十六条', url: 'https://www.nfra.gov.cn/a' },
    { company: '乙银行', audience: '个人', institutionType: '农村商业银行', region: '上海市', riskTokens: ['信贷管理'], risk: '信贷管理', amount: 500000, published: '2026-10-03', decisionNo: '乙1', violation: '贷后检查不到位', decision: '警告、罚款', legal: '《中华人民共和国银行业监督管理法》第四十八条', url: 'https://www.nfra.gov.cn/b' },
    { company: '乙银行', audience: '个人', institutionType: '农村商业银行', region: '上海市', riskTokens: ['信贷管理'], risk: '信贷管理', amount: 500000, published: '2026-10-03', decisionNo: '乙1', violation: '贷后检查不到位', decision: '警告、罚款', legal: '《中华人民共和国银行业监督管理法》第四十八条', url: 'https://www.nfra.gov.cn/b' },
  ];
  const report = buildReportModel(rows, { selectedMonths: ['2026-10'], sector: '银行' });
  assert.equal(report.count, 3);
  assert.equal(report.amount, 2000000);
  assert.deepEqual(report.risks.slice(0, 2).map(x => [x.name, x.count]), [['信贷管理', 3], ['数据质量', 1]]);
  assert.equal(report.topFines.length, 2);
  assert.equal(report.topFines[0].company, '甲银行');
  assert.equal(report.legalReferences[0].count, 3);
  assert.equal(report.legalReferences[0].topRisk, '信贷管理');
  assert.ok(!JSON.stringify(aiInput(report)).includes('甲银行'));
});

test('empty report has no invented insights or legal references', () => {
  const report = buildReportModel([], { selectedMonths: ['2026-11'] });
  assert.equal(report.count, 0);
  assert.deepEqual(report.insights, []);
  assert.deepEqual(report.legalReferences, []);
});
