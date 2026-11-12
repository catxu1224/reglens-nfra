const rankingExpanded={institution:false,authority:false};
function renderInstitutionSummary(rows){
  const arr=countBy(rows,'institutionType');
  const button=document.getElementById('expandInstitutions');
  button.hidden=arr.length<=6;
  button.textContent=rankingExpanded.institution?'收起':'展开全部';
  button.setAttribute('aria-expanded',String(rankingExpanded.institution));
  const host=document.getElementById('institutionPie');
  if(!arr.length){host.innerHTML='<p class=\'subtitle\'>暂无匹配数据</p>';return}
  const shown=rankingExpanded.institution||arr.length<=6?arr:[...arr.slice(0,6),['其余类型',arr.slice(6).reduce((sum,[,count])=>sum+count,0)]];
  const total=arr.reduce((sum,[,count])=>sum+count,0);
  const palette=['#1d6a4d','#83a83d','#b7d650','#edc34b','#e9984b','#6ba69a','#83a9c3','#a38db8','#cfaa6a','#67a977','#d47767'];
  const color=(name,index)=>name==='其余类型'?'#cbd5ca':palette[index%palette.length];
  const cx=110,cy=110,radius=94;
  let angle=-Math.PI/2;
  const slices=shown.map(([name,count],index)=>{
    const sweep=count/total*Math.PI*2,start=angle;angle+=sweep;
    const fill=color(name,index),label=`${name}：${count} 条，占 ${(count/total*100).toFixed(1)}%`;
    if(shown.length===1)return `<circle cx='${cx}' cy='${cy}' r='${radius}' fill='${fill}'><title>${escapeHtml(label)}</title></circle>`;
    const x1=cx+radius*Math.cos(start),y1=cy+radius*Math.sin(start),x2=cx+radius*Math.cos(angle),y2=cy+radius*Math.sin(angle);
    return `<path d='M ${cx} ${cy} L ${x1.toFixed(3)} ${y1.toFixed(3)} A ${radius} ${radius} 0 ${sweep>Math.PI?1:0} 1 ${x2.toFixed(3)} ${y2.toFixed(3)} Z' fill='${fill}'><title>${escapeHtml(label)}</title></path>`;
  }).join('');
  const legend=shown.map(([name,count],index)=>`<div class='institution-pie-item'><i style='background:${color(name,index)}'></i><span title='${escapeHtml(name)}'>${escapeHtml(name)}</span><strong>${(count/total*100).toFixed(1)}%</strong><small>${count.toLocaleString()} 条</small></div>`).join('');
  host.innerHTML=`<div class='institution-pie-layout'><svg viewBox='0 0 220 220' role='img' aria-label='机构类型分布饼图，共 ${total} 条'>${slices}</svg><div class='institution-pie-legend'>${legend}</div></div>`;
}
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
