import assert from 'node:assert/strict';
import { test } from 'node:test';
import { compactReport, generateAiReport } from '../server/report-ai.mjs';

const report = {
  period: '2026年10月', sector: '银行', count: 3, amount: 2000000,
  audience: [{ name: '机构', count: 2 }, { name: '个人', count: 1 }],
  regions: [{ name: '北京市', count: 2 }], institutions: [{ name: '城市商业银行', count: 2 }], risks: [{ name: '信贷管理', count: 3 }],
  legalReferences: [{ name: '《中华人民共和国银行业监督管理法》', count: 3, topRisk: '信贷管理', example: { basis: '《中华人民共和国银行业监督管理法》第四十六条', violation: '贷款管理不到位' } }],
  topFines: [{ person: '不应发送的姓名' }],
};

test('AI payload contains aggregate facts but omits top-fine identities', () => {
  const facts = compactReport(report);
  assert.equal(facts.count, 3);
  assert.equal(facts.legalReferences[0].name, '《中华人民共和国银行业监督管理法》');
  assert.ok(!JSON.stringify(facts).includes('不应发送的姓名'));
});

test('DeepSeek and Qwen use their own endpoints and per-request keys', async () => {
  let seen;
  const fakeFetch = async (url, options) => {
    seen = { url, options };
    return new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ summary: '本期信贷管理处罚较多。', recommendations: ['核对授信流程。'], legalNotes: [{ name: '《中华人民共和国银行业监督管理法》', interpretation: '本期与贷款管理事实关联。' }, { name: '《虚构法规》', interpretation: '不应显示' }] }) } }] }), { status: 200 });
  };
  const result = await generateAiReport({ provider: 'deepseek', model: 'deepseek-flash', apiKey: 'test-key-123', report }, fakeFetch);
  assert.equal(seen.url, 'https://api.deepseek.com/chat/completions');
  assert.equal(seen.options.headers.Authorization, 'Bearer test-key-123');
  assert.deepEqual(JSON.parse(seen.options.body).response_format, { type: 'json_object' });
  assert.deepEqual(JSON.parse(seen.options.body).thinking, { type: 'disabled' });
  assert.equal(result.summary, '本期信贷管理处罚较多。');
  assert.equal(result.legalNotes.length, 1);
  await generateAiReport({ provider: 'qwen', region: 'singapore', model: 'qwen-plus', apiKey: 'test-key-123', report }, fakeFetch);
  assert.equal(seen.url, 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions');
  assert.equal(JSON.parse(seen.options.body).thinking, undefined);
  await assert.rejects(generateAiReport({ provider: 'gpt', model: 'gpt-4.1', apiKey: 'test-key-123', report }, fakeFetch), /invalid_provider/);
  await assert.rejects(generateAiReport({ provider: 'qwen', region: 'invalid', model: 'qwen-plus', apiKey: 'test-key-123', report }, fakeFetch), /invalid_region/);
});
