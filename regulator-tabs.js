const regulatorButtons=[...document.querySelectorAll('.regulator-tabs button')];
function selectRegulator(name){
 if(name!=='safe' && name!==REGULATOR){const url=new URL(location.href);url.searchParams.set('regulator',name);url.searchParams.delete('case');location.assign(url);return}
 regulatorButtons.forEach(button=>{const active=button.dataset.regulator===name;button.classList.toggle('active',active);button.setAttribute('aria-selected',String(active))});
 document.getElementById('nfraWorkspace').hidden=name==='safe';document.getElementById('safePlaceholder').hidden=name!=='safe';document.querySelector('.sidebar nav').hidden=name==='safe';document.getElementById('pbocContext').hidden=name!=='pboc';
}
regulatorButtons.forEach(button=>button.addEventListener('click',()=>selectRegulator(button.dataset.regulator)));
selectRegulator(REGULATOR);

document.querySelectorAll('[data-regulator-label]').forEach(el=>el.textContent=REGULATOR.toUpperCase());

const allSectorsButton=document.querySelector('[data-sector="all"]');
allSectorsButton.hidden=REGULATOR!=='pboc';
if(REGULATOR==='pboc'){
 document.title='PBOC 人民银行处罚分析 · RegLens';
 document.querySelector('.topbar h1').textContent='人民银行监管处罚分析';
 document.querySelector('.topbar .subtitle').textContent='追踪反洗钱、支付结算与金融统计等领域的处罚事实和监管信号。';
}
document.getElementById('downloadFiltered').addEventListener('click',()=>document.getElementById('exportBtn').click());
let pbocFieldsPromise;
function renderPbocNoticeFields(record){
 const host=document.createElement('section');host.className='pboc-notice-fields drawer-quote';host.innerHTML='<b>人民银行公示信息</b><p role="status">正在读取公示字段…</p>';
 document.getElementById('drawerContent').append(host);
 pbocFieldsPromise ||= fetch('/api/pboc/notice-fields',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('公示信息读取失败');return r.json()}).catch(error=>{pbocFieldsPromise=null;throw error});
 pbocFieldsPromise.then(({rows})=>{
  const source=rows.find(row=>row.notice_url===record.url&&row.decision_no===record.decisionNo);
  host.innerHTML='<b>人民银行公示信息</b>'+ (source?'<dl>'+[['决定日期',source.decision_date],['公示期限',source.disclosure_period],['备注',source.remarks]].map(([label,value])=>`<div><dt>${label}</dt><dd>${escapeHtml(value||'原文未披露')}</dd></div>`).join('')+'</dl>':'<p>原文未提供对应的补充字段。</p>')+'<p class="pboc-field-note">决定日期与公告发布日期分别保留；统计使用公告发布日期。</p>';
 }).catch(()=>{host.innerHTML='<b>人民银行公示信息</b><p>补充字段暂时无法读取，请打开官方处罚书核对。</p>'});
}
document.getElementById('themeCards').addEventListener('click',event=>{
 const button=event.target.closest('[data-risk-field]');if(!button)return;
 const filterId={risk:'riskFilter',cause:'causeFilter',type:'penaltyTypeFilter'}[button.dataset.riskField];
 filterState[filterId].clear();filterState[filterId].add(button.dataset.riskValue);refreshFilters();apply();showView('details');
});
document.getElementById('caseGrid').addEventListener('click',event=>{const button=event.target.closest('[data-case-id]');if(button)openDrawer(button.dataset.caseId)});

if(REGULATOR==='pboc')fetch('/api/pboc/coverage',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error('coverage');return response.json()}).then(state=>{
 document.getElementById('pbocCoverageStatus').textContent=`分行处罚目录已核验 ${state.verifiedDirectories}/${state.totalBranches} · 已解析分行公告 ${state.parsedNotices} 篇 · 待处理 ${state.pendingTasks} 项 · 失败待复核 ${state.failedTasks} 项`;
}).catch(()=>{document.getElementById('pbocCoverageStatus').textContent='分行覆盖进度暂时无法读取；当前页面仅展示已成功采集的数据。'});
