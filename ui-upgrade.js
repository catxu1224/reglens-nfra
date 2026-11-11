// Ordered taxonomy and interactive filters for the local penalty dashboard.
const TAXONOMY={
 institutionType:'大型商业银行 股份制商业银行 城市商业银行 农村商业银行 农村信用联社 外资法人银行 外国银行分行 村镇银行 民营银行 政策性银行 多边开发银行 企业集团财务公司 理财子公司 信托公司 金融租赁公司 汽车金融公司 消费金融公司 金融资产管理公司 金融资产投资公司 证券业金融机构 保险业金融机构 金融控股公司 其他 未识别'.split(' '),
 region:'北京市 天津市 上海市 重庆市 河北省 山西省 辽宁省 吉林省 黑龙江省 江苏省 浙江省 安徽省 福建省 江西省 山东省 河南省 湖北省 湖南省 广东省 海南省 四川省 贵州省 云南省 陕西省 甘肃省 青海省 台湾省 内蒙古自治区 广西壮族自治区 西藏自治区 宁夏回族自治区 新疆维吾尔自治区 香港特别行政区 澳门特别行政区 境外 未识别'.split(' '),
 risk:'员工行为与案防 信贷管理 审慎交易 不良资产处置 票据业务 消费者权益保护 同业业务 风险管理 配合监管 存款业务 投资交易业务 银行卡业务 内控合规 运营管理 担保承诺 理财业务 反洗钱 分支机构管理 统计报送 数据治理 数据质量 信息科技 外包管理 保险业务管理 保险中介业务 支付结算业务 公司治理 关联交易 信息披露 财务会计管理 市场营销与销售管理 资产负债管理 保险销售与中介 保险产品与费率 保险承保与理赔 保险财务与费用 保险机构与许可证管理 利益输送与不正当竞争 代客操作 保险销售与消费者权益保护 保险产品、条款与费率管理 保险中介与销售人员管理 财务报告与费用真实性 业务许可与机构运营管理 关联交易与利益输送 客户资料与信息真实性 账户与资金使用管理 资产收购与股权投资管理 保险核保与理赔管理 绩效考核与培训管理 资金套取与费用管理 未识别'.split(' '),
 type:'警告 罚款 责令整改 纪律处分 取消任职资格 没收违法所得 禁止从业 暂停或限制业务 其他 未识别'.split(' '),
 cause:'流程管理不到位|业务制度不完善|员工行为管理不到位|贷款/授信管理不到位|贷款三查不尽职|贷前调查不尽职|贷后管理不到位|贷款未按约定用途使用/用途不合规|违反审慎经营规则|数据质量管理不到位|违规发放贷款|贷款资金被挪用|贷款资金违规流入房地产市场/土地储备领域|未按照规定报送大额交易报告或者可疑交易报告|向监管机构提供虚假/隐瞒重要事实的资料|未按照规定履行客户身份识别义务|监管标准化数据报送不合规|案防落实不到位|保险销售或中介业务违规|消费者权益保护不到位|反洗钱管理不到位|内控合规管理不到位|统计报送不真实或不完整|财务会计资料不真实|员工行为违规|信息科技管理不到位|公司治理或关联交易不规范|支付结算或银行卡业务违规|投资交易或资金运用违规|同业业务违规|未按规定办理行政许可、备案或报告|违法事实未披露|个人任职或履职责任|其他未具体说明|其他|未识别'.split('|')
};
const FILTER_IDS={periodFilter:'published',institutionFilter:'institutionType',regionFilter:'region',penaltyTypeFilter:'type',riskFilter:'risk',causeFilter:'cause'};
const filterState=Object.fromEntries(Object.keys(FILTER_IDS).map(id=>[id,new Set()]));
const BANK_INSTITUTIONS=new Set('大型商业银行 股份制商业银行 城市商业银行 农村商业银行 农村信用联社 外资法人银行 外国银行分行 村镇银行 民营银行 政策性银行 多边开发银行'.split(' '));
let activeSector='bank';
function sectorForInstitution(type){return BANK_INSTITUTIONS.has(type)?'银行':type==='保险业金融机构'?'保险':'其他'}
function sectorInstitutionOptions(){const label={bank:'银行',insurance:'保险',other:'其他'}[activeSector];return TAXONOMY.institutionType.filter(type=>sectorForInstitution(type)===label)}
function syncSectorButtons(){document.querySelectorAll('.sector-switch button').forEach(button=>{const active=button.dataset.sector===activeSector;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active))})}
function tokens(value){let text=String(value||'');const protectedNames=Object.values(TAXONOMY).flat().filter(name=>/[、,，;；]/.test(name)).sort((a,b)=>b.length-a.length);const slots=[];for(const name of protectedNames){if(text.includes(name)){const index=slots.push(name)-1;text=text.replaceAll(name,`\uE000${index}\uE001`)}}return text.split(/[、,，;；]/).map(x=>x.replace(/\uE000(\d+)\uE001/g,(_,i)=>slots[Number(i)]).trim()).filter(Boolean)}
function canonicalRegion(value){const s=String(value||'');if(!s||s==='其他/未识别'||s==='未识别')return '未识别';if(s==='境外')return s;return TAXONOMY.region.find(x=>shortProvince(x)===shortProvince(s))||'未识别'}
function canonicalInstitution(value){const s=String(value||'');if(TAXONOMY.institutionType.includes(s))return s;const map={'证券及资管':'证券业金融机构','保险':'保险业金融机构','信托':'信托公司','非银金融':'其他','银行':'其他'};return map[s]||'未识别'}
function canonicalType(value){const s=String(value||'').replaceAll('责令改正','责令整改').replaceAll('撤销任职资格','取消任职资格').replace(/禁止一定期限内从事银行业工作/g,'禁止从业').replace(/责令停止部分业务|暂停业务/g,'暂停或限制业务');return tokens(s).map(x=>TAXONOMY.type.includes(x)?x:'其他').join('、')||'未识别'}
function canonicalRisk(value){return tokens(value).map(x=>TAXONOMY.risk.includes(x)?x:({'消费者保护':'消费者权益保护','统计报送、监管配合':'统计报送','信贷管理与审慎经营':'信贷管理'}[x]||'未识别')).join('、')||'未识别'}
function canonicalCause(value){return tokens(value).map(x=>TAXONOMY.cause.includes(x)?x:({'贷款三查不到位':'贷款三查不尽职','审慎经营不到位':'违反审慎经营规则'}[x]||'其他')).join('、')||'未识别'}
function standardizeRows(){records.forEach(r=>{r.institutionType=canonicalInstitution(r.institutionType);r.sector=['银行','保险','其他'].includes(r.sector)?r.sector:sectorForInstitution(r.institutionType);r.region=canonicalRegion(r.region);r.type=canonicalType(r.type);r.risk=canonicalRisk(r.risk);r.cause=canonicalCause(r.cause)})}
function buildFilter(id,options){
  const host=document.getElementById(id),picked=filterState[id];
  const labels={periodFilter:'全部时间',institutionFilter:'全部机构',regionFilter:'全部地区',penaltyTypeFilter:'全部类型',riskFilter:'全部风险点',causeFilter:'全部案由'};
  const lines=id==='periodFilter'?buildPeriodOptions(options,picked):options.map(v=>`<label class="multi-option"><input type="checkbox" data-leaf value="${escapeHtml(v)}" ${picked.has(v)?'checked':''}><span>${escapeHtml(v)}</span></label>`).join('');
  host.innerHTML=`<button type="button" class="multi-trigger" aria-expanded="false">${picked.size?`已选 ${picked.size} 项`:labels[id]}<span>⌄</span></button><div class="multi-menu"><div class="multi-actions"><button type="button" data-action="all">全部</button><button type="button" data-action="clear">清空</button></div><div class="multi-options">${lines}</div></div>`;
  syncPeriods(host);
  host.querySelector('.multi-trigger').addEventListener('click',()=>{
    document.querySelectorAll('.multi-filter.open').forEach(x=>{if(x!==host){x.classList.remove('open');x.querySelector('.multi-trigger').setAttribute('aria-expanded','false')}});
    host.classList.toggle('open');host.querySelector('.multi-trigger').setAttribute('aria-expanded',host.classList.contains('open'));
  });
  host.querySelector('.multi-menu').addEventListener('click',e=>{
    const action=e.target.closest('[data-action]')?.dataset.action;if(!action)return;
    host.querySelectorAll('input[data-leaf]').forEach(x=>{x.checked=action==='all';action==='all'?picked.add(x.value):picked.delete(x.value)});
    syncPeriods(host);updateFilter(id);
  });
  host.querySelector('.multi-menu').addEventListener('change',e=>{
    const input=e.target;
    if(input.matches('[data-group-year]')){
      host.querySelectorAll(`input[data-leaf][data-year="${input.dataset.groupYear}"]`).forEach(x=>{x.checked=input.checked;input.checked?picked.add(x.value):picked.delete(x.value)});
    }else if(input.matches('[data-group-quarter]')){
      host.querySelectorAll(`input[data-leaf][data-quarter="${input.dataset.groupQuarter}"]`).forEach(x=>{x.checked=input.checked;input.checked?picked.add(x.value):picked.delete(x.value)});
    }else if(input.matches('[data-leaf]')){input.checked?picked.add(input.value):picked.delete(input.value)}
    syncPeriods(host);updateFilter(id);
  });
}
function buildPeriodOptions(options,picked){
  const years=[...new Set(options.map(x=>x.slice(0,4)))].sort((a,b)=>b.localeCompare(a));
  return years.map(year=>{
    const quarters=[1,2,3,4].map(q=>{
      const months=options.filter(month=>month.startsWith(year)&&Math.ceil(Number(month.slice(5))/3)===q);
      if(!months.length)return '';
      const quarter=`${year}-Q${q}`;
      return `<div class="quarter-group"><label class="multi-option quarter-option"><input type="checkbox" data-group-quarter="${quarter}"><strong>第 ${q} 季度</strong></label><div class="month-grid">${months.map(month=>`<label class="multi-option"><input type="checkbox" data-leaf data-year="${year}" data-quarter="${quarter}" value="${month}" ${picked.has(month)?'checked':''}><span>${Number(month.slice(5))} 月</span></label>`).join('')}</div></div>`;
    }).join('');
    return `<div class="year-group"><label class="multi-option year-option"><input type="checkbox" data-group-year="${year}"><strong>${year} 年</strong></label>${quarters}</div>`;
  }).join('');
}
function syncPeriods(host){
  host.querySelectorAll('input[data-group-quarter],input[data-group-year]').forEach(x=>{
    const kind=x.dataset.groupQuarter?'quarter':'year',value=x.dataset.groupQuarter||x.dataset.groupYear;
    const children=[...host.querySelectorAll(`input[data-leaf][data-${kind}="${value}"]`)];
    x.checked=children.length>0&&children.every(child=>child.checked);
    x.indeterminate=children.some(child=>child.checked)&&!x.checked;
  });
}
function updateFilter(id){
  const host=document.getElementById(id),size=filterState[id].size;
  host.querySelector('.multi-trigger').firstChild.textContent=size?`已选 ${size} 项`:{periodFilter:'全部时间',institutionFilter:'全部机构',regionFilter:'全部地区',penaltyTypeFilter:'全部类型',riskFilter:'全部风险点',causeFilter:'全部案由'}[id];
  if(id==='riskFilter'||id==='causeFilter')applyDetail();else apply();
}
function refreshFilters(){
  standardizeRows();
  const end=todayChina().slice(0,7),months=[];
  for(let year=Number(DATA_START.slice(0,4));year<=Number(end.slice(0,4));year++)for(let month=1;month<=12;month++){
    const key=`${year}-${String(month).padStart(2,'0')}`;
    if(key>=DATA_START.slice(0,7)&&key<=end)months.push(key);
  }
  buildFilter('periodFilter',months);
  for(const [id,key] of Object.entries(FILTER_IDS)){if(id!=='periodFilter')buildFilter(id,id==='institutionFilter'?sectorInstitutionOptions():TAXONOMY[key]||[])}
  const max=records.map(r=>r.published).filter(Boolean).sort().pop()||'—';
  document.getElementById('asOfLabel').textContent=`共 ${records.length.toLocaleString()} 条 · 更新至 ${max}`;
}
function matches(id,value){const selected=filterState[id];return !selected.size||tokens(value).some(v=>selected.has(v))}
function selectedRows(){return records.filter(r=>r.sector==={bank:'银行',insurance:'保险',other:'其他'}[activeSector]&&matches('periodFilter',r.published.slice(0,7))&&matches('institutionFilter',r.institutionType)&&matches('regionFilter',r.region)&&matches('penaltyTypeFilter',r.type))}
function applyDetail(){const q=(document.getElementById('detailSearch').value||'').toLowerCase();detailFiltered=filtered.filter(r=>matches('riskFilter',r.risk)&&matches('causeFilter',r.cause)&&(!q||r.search.includes(q)||`${r.company} ${r.branch} ${r.person} ${r.audience} ${r.institutionType} ${r.region} ${r.risk} ${r.cause} ${r.type} ${r.authority}`.toLowerCase().includes(q)));detailPage=1;renderDetailTable()}
function shapePoints(geometry){if(!geometry)return[];const polys=geometry.type==='Polygon'?[geometry.coordinates]:geometry.coordinates;return polys.flatMap(poly=>poly.flatMap(ring=>ring))}
function renderMap(rows){const map=document.getElementById('chinaMap');if(!geoFeatures.length){map.innerHTML='<p class="map-loading">正在加载省级地图…</p>';return}const stats=new Map();for(const r of rows){const key=canonicalRegion(r.region),s=stats.get(key)||{count:0,amount:0,companies:new Map(),risks:new Map()};s.count++;s.amount+=r.amount;s.companies.set(r.company,(s.companies.get(r.company)||0)+1);tokens(r.risk).forEach(x=>s.risks.set(x,(s.risks.get(x)||0)+1));stats.set(key,s)}const max=Math.max(1,...[...stats.values()].map(x=>x.count)),top=[...stats].sort((a,b)=>b[1].count-a[1].count)[0];document.getElementById('mapTopLabel').textContent=top?`最高：${top[0]} ${top[1].count} 条`:'';const featurePoints=geoFeatures.flatMap(f=>shapePoints(f.geometry)).filter(p=>Array.isArray(p)&&Number.isFinite(p[0])&&Number.isFinite(p[1]));const minLon=Math.min(...featurePoints.map(p=>p[0])),maxLon=Math.max(...featurePoints.map(p=>p[0])),minLat=Math.min(...featurePoints.map(p=>p[1])),maxLat=Math.max(...featurePoints.map(p=>p[1]));const W=100,H=72,project=([lon,lat])=>[3+(lon-minLon)/(maxLon-minLon)*94,2+(maxLat-lat)/(maxLat-minLat)*68];const shapes=geoFeatures.map(f=>{const name=f.properties?.name||'南海诸岛',key=canonicalRegion(name),s=stats.get(key),value=s?.count||0,ratio=value/max,color=!value?'#29343a':ratio>.6?'#df3b32':ratio>.25?'#f28d19':'#f5c52a';return `<g class="map-region" data-region="${escapeHtml(key)}" tabindex="0" aria-label="${escapeHtml(name)} ${value} 条"><path d="${geoPath(f.geometry,project)}" fill="${color}" stroke="#151f22" stroke-width=".18" fill-rule="evenodd"></path><title>${escapeHtml(name)}：${value} 条，${money(s?.amount||0)}</title></g>`}).join('');map.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="中国省级行政区域处罚热力图">${shapes}</svg><div class="map-key"><span><i></i>低</span><span><i></i>中</span><span><i></i>高</span><span><i></i>无数据</span></div><div class="map-tooltip" hidden></div>`;const tooltip=map.querySelector('.map-tooltip');const show=(el)=>{const key=el.dataset.region,s=stats.get(key),first=m=>[...m].sort((a,b)=>b[1]-a[1])[0]?.[0]||'—';tooltip.innerHTML=`<strong>${escapeHtml(key)}</strong><dl><div><dt>处罚条数</dt><dd>${s?.count||0} 条</dd></div><div><dt>处罚总金额</dt><dd>${money(s?.amount||0)}</dd></div><div><dt>处罚最多的单位</dt><dd>${escapeHtml(s?first(s.companies):'—')}</dd></div><div><dt>主要合规风险点</dt><dd>${escapeHtml(s?first(s.risks):'—')}</dd></div></dl>`;tooltip.hidden=false};map.querySelectorAll('.map-region').forEach(el=>{el.addEventListener('mouseenter',()=>show(el));el.addEventListener('focus',()=>show(el));el.addEventListener('mouseleave',()=>tooltip.hidden=true);el.addEventListener('blur',()=>tooltip.hidden=true);el.addEventListener('click',()=>{filterState.regionFilter.clear();filterState.regionFilter.add(el.dataset.region);buildFilter('regionFilter',TAXONOMY.region);apply()})})}
const renderMapBase=renderMap;
renderMap=function(rows){renderMapBase(rows);const colors={'#f5c52a':'#c5d34b','#f28d19':'#f5c52a','#df3b32':'#ed5934','#29343a':'#bdc8c2'};document.querySelectorAll('#chinaMap .map-region path').forEach(path=>{const color=colors[path.getAttribute('fill')];if(color)path.setAttribute('fill',color)});const low=document.querySelector('#chinaMap .map-key span:first-child');if(low)low.innerHTML='<i></i>低风险'};
document.addEventListener('click',e=>{if(!e.target.closest('.multi-filter'))document.querySelectorAll('.multi-filter.open').forEach(x=>{x.classList.remove('open');x.querySelector('.multi-trigger').setAttribute('aria-expanded','false')})});
document.querySelectorAll('.sector-switch button').forEach(button=>button.addEventListener('click',()=>{const next=button.dataset.sector;if(next===activeSector)return;activeSector=next;filterState.institutionFilter.clear();syncSectorButtons();buildFilter('institutionFilter',sectorInstitutionOptions());apply()}));
document.getElementById('resetBtn').addEventListener('click',()=>{Object.values(filterState).forEach(s=>s.clear());activeSector='bank';syncSectorButtons();refreshFilters();document.getElementById('detailSearch').value='';apply()});
