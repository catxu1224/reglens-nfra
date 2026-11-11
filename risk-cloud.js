function renderRiskCloud(rows){
  const host=document.getElementById('riskCloud');
  const counts=new Map();
  for(const row of rows){
    for(const risk of new Set(tokens(row.risk))){
      if(!risk||risk==='未识别')continue;
      counts.set(risk,(counts.get(risk)||0)+1);
    }
  }
  const items=[...counts].sort((a,b)=>b[1]-a[1]).slice(0,20);
  if(!items.length){host.innerHTML='<p class="cloud-empty">当前范围暂无已识别的合规风险点</p>';return}
  const max=items[0][1],min=items[items.length-1][1];
  // Alternate larger and smaller words to fill the available space naturally.
  const arranged=[];let left=0,right=items.length-1;
  while(left<=right){arranged.push(items[left++]);if(left<=right)arranged.push(items[right--])}
  const colors=['#176b4d','#2e7652','#6a8e36','#a58d33','#367f74'];
  host.innerHTML=arranged.map(([name,count],i)=>{
    const strength=max===min?0.55:Math.log1p(count-min)/Math.log1p(max-min);
    const size=Math.round(12+strength*14);
    const tilt=i%9===4?-5:i%11===7?5:0;
    return `<button class="cloud-word" type="button" data-risk="${escapeHtml(name)}" style="--word-size:${size}px;--word-color:${colors[i%colors.length]};--word-tilt:${tilt}deg" title="${escapeHtml(name)}：${count} 条">${escapeHtml(name)}</button>`;
  }).join('');
  host.querySelectorAll('.cloud-word').forEach(word=>word.addEventListener('click',()=>{
    const name=word.dataset.risk;
    filterState.riskFilter.clear();filterState.riskFilter.add(name);
    buildFilter('riskFilter',TAXONOMY.risk);
    showView('details');applyDetail();
  }));
}
