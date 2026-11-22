const regulatorButtons=[...document.querySelectorAll('.regulator-tabs button')];
function selectRegulator(name){
 if(name!=='safe' && name!==REGULATOR){const url=new URL(location.href);url.searchParams.set('regulator',name);url.searchParams.delete('case');location.assign(url);return}
 regulatorButtons.forEach(button=>{const active=button.dataset.regulator===name;button.classList.toggle('active',active);button.setAttribute('aria-selected',String(active))});
 document.getElementById('nfraWorkspace').hidden=name==='safe';document.getElementById('pbocPlaceholder').hidden=true;document.getElementById('safePlaceholder').hidden=name!=='safe';document.querySelector('.sidebar nav').hidden=name==='safe';
}
regulatorButtons.forEach(button=>button.addEventListener('click',()=>selectRegulator(button.dataset.regulator)));
selectRegulator(REGULATOR);

document.querySelectorAll('[data-regulator-label]').forEach(el=>el.textContent=REGULATOR.toUpperCase());
