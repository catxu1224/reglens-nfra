import { aiInput, buildReportModel } from './report-core.mjs';

const $ = selector => document.querySelector(selector);
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const comma = value => Number(value || 0).toLocaleString('zh-CN');
const amountText = value => value >= 1e8 ? `${(value / 1e8).toFixed(2)}亿元` : `${(value / 1e4).toFixed(2)}万元`;
const excerpt = (value, limit = 170) => String(value || '未提供').trim().slice(0, limit) + (String(value || '').length > limit ? '…' : '');

function safeNoticeUrl(value) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && (url.hostname === 'nfra.gov.cn' || url.hostname.endsWith('.nfra.gov.cn')) ? url.href : '';
  } catch { return ''; }
}

function barChart(items, color, limit = 10) {
  const data = items.slice(0, limit), height = Math.max(80, data.length * 37 + 16), max = data[0]?.count || 1;
  if (!data.length) return '<p class="report-empty">该维度暂无数据。</p>';
  const bars = data.map((item, index) => {
    const y = index * 37 + 15, width = Math.max(2, item.count / max * 310);
    return `<g><title>${escape(item.name)}：${comma(item.count)}条</title><text x="0" y="${y + 13}" class="report-chart-label">${escape(item.name)}</text><rect x="208" y="${y}" width="310" height="19" rx="5" fill="#edf2ec"/><rect x="208" y="${y}" width="${width.toFixed(1)}" height="19" rx="5" fill="${color}"/><text x="530" y="${y + 14}" class="report-chart-value">${comma(item.count)}</text></g>`;
  }).join('');
  return `<svg class="report-bar-chart" viewBox="0 0 610 ${height}" role="img" aria-label="分布图">${bars}</svg>`;
}

function audienceChart(items) {
  const total = items.reduce((sum, item) => sum + item.count, 0), colors = ['#77aa54', '#e5b446', '#aebbb1'];
  if (!total) return '<p class="report-empty">暂无处罚对象数据。</p>';
  let offset = 0;
  const rings = items.map((item, index) => {
    const length = item.count / total * 100, current = offset;
    offset += length;
    return `<circle cx="92" cy="92" r="61" fill="none" stroke="${colors[index % colors.length]}" stroke-width="26" pathLength="100" stroke-dasharray="${length} ${100 - length}" stroke-dashoffset="${-current}" transform="rotate(-90 92 92)"><title>${escape(item.name)} ${comma(item.count)}条</title></circle>`;
  }).join('');
  const legend = items.map((item, index) => `<li><i style="background:${colors[index % colors.length]}"></i><span>${escape(item.name)}</span><strong>${comma(item.count)}条 · ${(item.count / total * 100).toFixed(1)}%</strong></li>`).join('');
  return `<div class="report-audience"><svg viewBox="0 0 184 184" role="img" aria-label="处罚对象分布环形图">${rings}<text x="92" y="88" text-anchor="middle" class="report-donut-total">${comma(total)}</text><text x="92" y="108" text-anchor="middle" class="report-donut-caption">条记录</text></svg><ul>${legend}</ul></div>`;
}

function fineCards(rows) {
  if (!rows.length) return '<p class="report-empty">本期没有可解析金额的处罚记录。</p>';
  return rows.map((row, index) => {
    const url = safeNoticeUrl(row.url);
    const party = row.audience === '个人' && row.person ? row.person : row.company || row.person || '未识别当事人';
    return `<article class="report-fine"><div class="report-fine-head"><span class="report-fine-num">${String(index + 1).padStart(2, '0')}</span><strong>${escape(party)}</strong><b>${amountText(Number(row.amount))}</b></div><div class="report-fine-meta">${escape(row.published || '日期未提供')} · ${escape(row.region || '地区未识别')} · ${escape(row.institutionType || '机构类型未识别')} · ${escape(row.decisionNo || '文号未提供')}</div><p><span>违法事实</span>${escape(excerpt(row.violation))}</p><p><span>处罚决定</span>${escape(excerpt(row.decision))}</p>${url ? `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">查看原处罚书 ↗</a>` : ''}</article>`;
  }).join('');
}

function lawCards(items, aiNotes = []) {
  if (!items.length) return '<p class="report-empty">本期处罚依据中没有可识别的《法规名称》。请查看原处罚书核对具体依据。</p>';
  return items.map(item => {
    const url = safeNoticeUrl(item.example?.url);
    const note = aiNotes.find(entry => entry.name === item.name)?.interpretation;
    return `<article class="report-law"><div class="report-law-head"><h4>${escape(item.name)}</h4><span>${comma(item.count)}条引用</span></div><p>本期引用该法规的记录，最高频合规风险点为<strong>${escape(item.topRisk)}</strong>。样本处罚事实：${escape(excerpt(item.example?.violation, 140))}</p><p class="report-law-basis">处罚依据摘录：${escape(excerpt(item.example?.basis, 160))}</p><p class="report-law-note">模型适用观察：${escape(note || '结合处罚事实核对相关业务流程和责任记录；具体条款适用应以法规原文和处罚决定为准。')}</p>${url ? `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">核对原处罚书 ↗</a>` : ''}</article>`;
  }).join('');
}

function filterDescription(filters) {
  const names = { institution: '机构类型', region: '地区', type: '处罚类型' };
  return Object.entries(names).map(([key, label]) => filters[key]?.length ? `${label}：${filters[key].join('、')}` : '').filter(Boolean);
}

function renderReport(model, ai = null, aiError = '') {
  const filters = filterDescription(model.filters), risks = model.risks.slice(0, 10);
  const dataSource = $('#sourceLabel').textContent;
  $('#reportBody').innerHTML = `<div class="report-cover"><p class="report-kicker">REGLENS · NFRA REGULATORY REVIEW</p><h2>${escape(model.period)}监管处罚分析报告</h2><p>国家金融监督管理总局 · ${escape(model.sector)} · 生成于 ${escape(new Date(model.generatedAt).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }))}</p></div>
    <div class="report-intro"><strong>报告范围</strong><span>${escape(model.firstPublished || '—')} 至 ${escape(model.lastPublished || '—')} · ${escape(dataSource)} · ${comma(model.count)} 条记录</span>${filters.length ? `<small>${escape(filters.join('；'))}</small>` : ''}</div>
    <section class="report-section"><div class="report-section-head"><span>01</span><h3>核心数据与本期观察</h3></div><div class="report-kpis"><div><small>处罚记录</small><strong>${comma(model.count)}</strong><span>条</span></div><div><small>罚款总额</small><strong>${amountText(model.amount)}</strong></div><div><small>单条平均</small><strong>${model.count ? amountText(model.amount / model.count) : '—'}</strong></div><div><small>涉及法规</small><strong>${comma(model.legalReferences.length)}</strong><span>项高频依据</span></div></div><div class="report-insights">${model.insights.map(text => `<p>${escape(text)}</p>`).join('') || '<p>当前筛选范围没有处罚记录。</p>'}</div></section>
    <section class="report-section report-ai-section"><div class="report-section-head"><span>AI</span><h3>模型分析与核查建议</h3></div>${ai ? `<p class="report-ai-summary">${escape(ai.summary)}</p><ol class="report-ai-list">${ai.recommendations.map(text => `<li>${escape(text)}</li>`).join('')}</ol>` : `<p class="report-ai-pending">${escape(aiError || '正在调用模型生成分析，请稍候…')}</p>`}</section>
    <section class="report-section"><div class="report-section-head"><span>02</span><h3>分布图表</h3></div><div class="report-chart-grid"><article class="report-chart-card"><h4>地区分布 <small>前十地区 · 按记录数</small></h4>${barChart(model.regions, '#85aa4a')}</article><article class="report-chart-card"><h4>被处罚对象 <small>机构 / 个人</small></h4>${audienceChart(model.audience)}</article><article class="report-chart-card"><h4>机构类型分布 <small>前十类型 · 按记录数</small></h4>${barChart(model.institutions, '#447b64')}</article><article class="report-chart-card"><h4>合规风险点 <small>前十风险点 · 可多标签</small></h4>${barChart(risks, '#d4a142')}</article></div></section>
    <section class="report-section"><div class="report-section-head"><span>03</span><h3>金额最高的十条处罚记录</h3></div><p class="report-section-note">按可解析罚款金额降序；相同当事人、文号及金额的重复记录仅展示一次。点击链接可核对原处罚书。</p><div class="report-fine-grid">${fineCards(model.topFines)}</div></section>
    <section class="report-section"><div class="report-section-head"><span>04</span><h3>法规依据与适用观察</h3></div><p class="report-section-note">从“处罚依据”字段提取法规名称，按引用记录数排序。以下观察基于本期处罚事实，未替代法规原文核验。</p><div class="report-law-grid">${lawCards(model.legalReferences, ai?.legalNotes)}</div></section>
    <section class="report-section report-method"><div class="report-section-head"><span>05</span><h3>统计口径</h3></div><p>来源：NFRA 行政处罚数据，按当前页面筛选条件统计。发布日期采用数据字段“发布时间”；页面生成时间不代表数据更新日。</p><p>条数以数据记录为单位，同一处罚书可能涉及多名当事人；金额为可解析“处罚金额”字段逐条相加，未对共同罚款或重复文书进行金额合并。合规风险点可多选，因此各项次数之和可能超过处罚记录数。</p><p>法规名称和处罚事实来自数据字段，建议通过原处罚书与官方现行法规文本复核。报告用于信息分析，不构成法律或合规意见。</p></section>`;
  $('#reportPrint').disabled = !ai;
  $('#reportStatus').textContent = ai ? `已生成 · ${comma(model.count)} 条记录 · ${model.period}` : aiError || `模型正在分析 ${comma(model.count)} 条记录…`;
}

let aiConfig = { model: 'gpt-4.1', apiKey: '' };
let generating = false;
function openAiSettings(autoGenerate = false) {
  $('#aiModel').value = aiConfig.model;
  $('#aiKey').value = '';
  $('#aiKey').required = !aiConfig.apiKey;
  $('#aiSettings').dataset.autoGenerate = String(autoGenerate);
  $('#aiSettings').showModal();
  $('#aiKey').focus();
}

async function generateReport() {
  if (!aiConfig.apiKey) return openAiSettings(true);
  if (generating) return;
  const state = window.getReglensReportState?.();
  if (!state?.rows.length) { $('#reportStatus').textContent = '当前筛选范围没有处罚记录，请调整筛选条件。'; window.showView('report'); return; }
  const model = buildReportModel(state.rows, state);
  generating = true;
  $('#generateReport').disabled = true;
  $('#regenerateReport').disabled = true;
  renderReport(model);
  window.showView('report');
  window.scrollTo({ top: 0, behavior: 'smooth' });
  try {
    const response = await fetch('/api/report-insights', { method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: aiConfig.model, apiKey: aiConfig.apiKey, report: aiInput(model) }) });
    const payload = await response.json();
    if (!response.ok || !payload.analysis) throw new Error(payload.error || `HTTP ${response.status}`);
    renderReport(model, payload.analysis);
  } catch (error) {
    const reason = error.message === 'openai_401' ? 'API Key 无效或无权调用该模型。' : error.message === 'openai_429' ? '模型服务限流或额度不足。' : `模型生成失败（${error.message}）。请检查模型名称、Key 和网络后重试。`;
    renderReport(model, null, reason);
  } finally {
    generating = false;
    $('#generateReport').disabled = false;
    $('#regenerateReport').disabled = false;
  }
}

$('#generateReport').addEventListener('click', generateReport);
$('#regenerateReport').addEventListener('click', generateReport);
$('#reportPrint').addEventListener('click', () => window.print());
$('#openAiSettings').addEventListener('click', () => openAiSettings());
$('#closeAiSettings').addEventListener('click', () => $('#aiSettings').close());
$('#cancelAiSettings').addEventListener('click', () => $('#aiSettings').close());
$('#aiSettingsForm').addEventListener('submit', event => {
  event.preventDefault();
  aiConfig = { model: $('#aiModel').value.trim(), apiKey: $('#aiKey').value.trim() || aiConfig.apiKey };
  $('#aiKey').value = '';
  $('#aiSettings').close();
  $('#aiSettingsStatus').textContent = `已配置 ${aiConfig.model} · Key 仅在当前页面会话有效`;
  if ($('#aiSettings').dataset.autoGenerate === 'true') generateReport();
});
document.addEventListener('penalties:loaded', () => { $('#generateReport').disabled = false; });
if (['种子数据', 'PostgreSQL'].includes($('#sourceLabel').textContent)) $('#generateReport').disabled = false;
