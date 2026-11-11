const rankingExpanded={institution:false,authority:false};
function renderInstitutionSummary(rows){const arr=countBy(rows,'institutionType');renderBars('#institutionBars',arr,rankingExpanded.institution?arr.length:6);const button=document.getElementById('expandInstitutions');button.hidden=arr.length<=6;button.textContent=rankingExpanded.institution?'收起':'展开全部';button.setAttribute('aria-expanded',String(rankingExpanded.institution))}
function renderAuthoritySummary(rows){const arr=countBy(rows,'authority');const shown=rankingExpanded.authority?arr:arr.slice(0,8);document.getElementById('authorityRank').innerHTML=shown.map(([name,count],i)=>`<div class="rank-row"><span class="rank-number">${String(i+1).padStart(2,'0')}</span><span class="rank-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span><span class="rank-value">${count} 条</span></div>`).join('')||'<p class="subtitle">暂无匹配数据</p>';const button=document.getElementById('expandAuthorities');button.hidden=arr.length<=8;button.textContent=rankingExpanded.authority?'收起':'展开全部';button.setAttribute('aria-expanded',String(rankingExpanded.authority))}
function audienceOf(row){return row.audience==='机构'||row.audience==='个人'?row.audience:'未识别'}
function renderAudienceCounts(rows){
  const counts={机构:0,个人:0,未识别:0};
  rows.forEach(row=>counts[audienceOf(row)]++);
  document.getElementById('institutionCount').textContent=counts.机构.toLocaleString();
  document.getElementById('personCount').textContent=counts.个人.toLocaleString();
  document.getElementById('audienceUnknown').textContent=counts.未识别?`未识别 ${counts.未识别.toLocaleString()} 条`:'';
}
document.getElementById('expandInstitutions').addEventListener('click',()=>{rankingExpanded.institution=!rankingExpanded.institution;renderInstitutionSummary(filtered)});
document.getElementById('expandAuthorities').addEventListener('click',()=>{rankingExpanded.authority=!rankingExpanded.authority;renderAuthoritySummary(filtered)});
