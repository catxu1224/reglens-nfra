const number = value => Number.isFinite(Number(value)) ? Number(value) : 0;
const rank = counts => [...counts].map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'zh-CN'));

function tally(rows, values) {
  const counts = new Map();
  for (const row of rows) {
    for (const value of new Set(values(row).filter(Boolean))) counts.set(value, (counts.get(value) || 0) + 1);
  }
  return rank(counts);
}

export function periodLabel(selectedMonths, rows) {
  const months = [...new Set(selectedMonths)].sort();
  if (months.length === 1) return `${months[0].slice(0, 4)}年${Number(months[0].slice(5))}月`;
  if (months.length === 3 && months.every(month => month.slice(0, 4) === months[0].slice(0, 4))) {
    const quarter = Math.ceil(Number(months[0].slice(5)) / 3);
    if (months.every((month, index) => Number(month.slice(5)) === (quarter - 1) * 3 + index + 1)) return `${months[0].slice(0, 4)}年第${quarter}季度`;
  }
  if (months.length === 12 && months.every((month, index) => month === `${months[0].slice(0, 4)}-${String(index + 1).padStart(2, '0')}`)) return `${months[0].slice(0, 4)}年`;
  const dates = months.length ? months : rows.map(row => row.published).filter(Boolean).sort();
  if (!dates.length) return '当前筛选范围';
  const first = dates[0].slice(0, 7), last = dates.at(-1).slice(0, 7);
  return first === last ? `${first.slice(0, 4)}年${Number(first.slice(5))}月` : `${first}—${last}${months.length ? `（已选${months.length}个月）` : ''}`;
}

export function buildReportModel(rows, context = {}) {
  const amount = rows.reduce((total, row) => total + number(row.amount), 0);
  const audience = tally(rows, row => [row.audience || '未识别']);
  const regions = tally(rows, row => [row.region || '未识别']);
  const institutions = tally(rows, row => [row.institutionType || '未识别']);
  const risks = tally(rows, row => row.riskTokens?.length ? row.riskTokens : [row.risk || '未识别']);
  const months = tally(rows, row => [row.published?.slice(0, 7)]).sort((a, b) => a.name.localeCompare(b.name));
  const fineKeys = new Set();
  const topFines = [...rows].filter(row => number(row.amount) > 0).sort((a, b) => number(b.amount) - number(a.amount)).filter(row => {
    const key = [row.decisionNo, row.url, row.company, row.person, row.amount].join('\u0001');
    if (fineKeys.has(key)) return false;
    fineKeys.add(key);
    return true;
  }).slice(0, 10);
  const laws = new Map();
  for (const row of rows) {
    for (const name of new Set(String(row.legal || '').match(/《[^》]{2,60}》/g) || [])) {
      const item = laws.get(name) || { name, count: 0, risks: new Map(), example: null };
      item.count++;
      for (const risk of new Set(row.riskTokens?.length ? row.riskTokens : [row.risk || '未识别'])) item.risks.set(risk, (item.risks.get(risk) || 0) + 1);
      if (!item.example && (row.violation || row.url)) item.example = { basis: row.legal, violation: row.violation, url: row.url };
      laws.set(name, item);
    }
  }
  const legalReferences = [...laws.values()].sort((a, b) => b.count - a.count).slice(0, 5).map(item => ({
    name: item.name, count: item.count, topRisk: rank(item.risks)[0]?.name || '未识别', example: item.example,
  }));
  const published = rows.map(row => row.published).filter(Boolean).sort();
  const topRisk = risks[0], topRegion = regions[0], topInstitution = institutions[0];
  return {
    count: rows.length, amount, audience, regions, institutions, risks, months, topFines, legalReferences,
    period: periodLabel(context.selectedMonths || [], rows),
    sector: context.sector || '全部机构',
    filters: context.filters || {},
    firstPublished: published[0] || '', lastPublished: published.at(-1) || '',
    generatedAt: context.generatedAt || new Date().toISOString(),
    insights: rows.length ? [
      `本期共收录${rows.length.toLocaleString('zh-CN')}条处罚记录，按记录汇总可解析罚款金额为${(amount / 1e4).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}万元。`,
      `${topRegion?.name || '未识别地区'}的记录数最多（${topRegion?.count || 0}条）；${topInstitution?.name || '未识别机构类型'}是最高频机构类型（${topInstitution?.count || 0}条）。`,
      `${topRisk?.name || '未识别风险点'}出现${topRisk?.count || 0}次，占本期记录的${Math.round((topRisk?.count || 0) / rows.length * 100)}%。一条记录可能涉及多个风险点。`,
    ] : [],
  };
}

export function aiInput(model) {
  return {
    period: model.period, sector: model.sector, count: model.count, amount: model.amount,
    audience: model.audience.slice(0, 5), regions: model.regions.slice(0, 5),
    institutions: model.institutions.slice(0, 5), risks: model.risks.slice(0, 5),
    legalReferences: model.legalReferences.map(item => ({
      name: item.name, count: item.count, topRisk: item.topRisk,
      example: { basis: String(item.example?.basis || '').slice(0, 220), violation: String(item.example?.violation || '').slice(0, 220) },
    })),
  };
}
