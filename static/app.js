const modal=document.getElementById('scan-modal');
let activeModule='';
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
document.querySelectorAll('[data-module]').forEach(btn=>btn.addEventListener('click',()=>{
 activeModule=btn.dataset.module; document.getElementById('modal-title').textContent=btn.dataset.title;
 const fields=(btn.dataset.fields||'target').split(','); const labels=[btn.dataset.label||'Domain name',btn.dataset.label2||'Second domain'];
 const examples={'phone':'+234 801 234 5678','ip':'8.8.8.8','individual-email':'security@example.com','breach':'security@example.com','cve':'Apache HTTP Server','compare':'example.com','port-scanner':'example.com'};
 document.getElementById('modal-fields').innerHTML=fields.map((f,i)=>{const ph=f==='ports'?'80,443,22,8080':(examples[activeModule]||(f==='second'?'example.org':'example.com'));const tel=activeModule==='phone'?' inputmode="tel" autocomplete="tel"':'';return `<label>${f==='ports'?'TCP ports (comma separated)':labels[i]||f}<input name="${f}" ${f==='ports'?'value="80,443,22,8080"':'placeholder="'+ph+'"'+tel} required></label>`}).join('');
 document.getElementById('auth-line').style.display=btn.dataset.auth==='yes'?'flex':'none';
 document.getElementById('authorized').checked=false;
 document.getElementById('scan-output').classList.add('hidden'); document.getElementById('scan-output').innerHTML='';
 modal.classList.remove('hidden');
}));
if(document.getElementById('modal-close')) document.getElementById('modal-close').onclick=()=>modal.classList.add('hidden');
if(modal) modal.addEventListener('click',e=>{if(e.target===modal)modal.classList.add('hidden')});
const form=document.getElementById('scan-form');
if(form) form.addEventListener('submit',async e=>{
 e.preventDefault(); const btn=document.getElementById('run-scan'); const out=document.getElementById('scan-output');
 if(document.getElementById('auth-line').style.display!=='none'&&!document.getElementById('authorized').checked){alert('Please confirm authorization first.');return;}
 const data=Object.fromEntries(new FormData(form).entries()); if(data.ports)data.ports=data.ports.split(',').map(x=>parseInt(x.trim(),10)).filter(Number.isFinite);
 data.authorized=document.getElementById('authorized').checked?'yes':'no';
 btn.disabled=true; btn.innerHTML='<span class="spinner"></span> Analysing...'; out.classList.remove('hidden'); out.innerHTML='<div class="loading-line">Collecting public intelligence signals…</div>';
 try{
  const r=await fetch('/scan/'+activeModule,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const j=await r.json();
  if(j.upgrade){out.innerHTML='<div class="result-error">Premium access is required. Close this panel and activate Premium from the dashboard.</div>';return;}
  if(!r.ok)throw new Error(j.error||'Scan failed');
  out.innerHTML='<div class="result-head"><b>Analysis complete</b><span class="risk">'+escapeHtml(j.result.risk||'INFO')+'</span></div><pre>'+escapeHtml(JSON.stringify(j.result,null,2))+'</pre><button type="button" class="btn secondary" id="copy-result">Copy report</button>';
  document.getElementById('copy-result').onclick=()=>navigator.clipboard.writeText(JSON.stringify(j.result,null,2));
 }catch(err){out.innerHTML='<div class="result-error">'+escapeHtml(err.message)+'</div>';}
 finally{btn.disabled=false;btn.innerHTML='Run analysis <b>↗</b>';}
});
document.querySelectorAll('.paystack-plan').forEach(pay=>pay.addEventListener('click',async()=>{
 const plan=pay.dataset.plan; const original=pay.textContent; pay.disabled=true; pay.textContent='Connecting to Paystack…';
 try{const r=await fetch('/payment/initialize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan})});const j=await r.json();if(!r.ok)throw new Error(j.error||'Payment initialization failed');window.location.href=j.url;}
 catch(e){alert(e.message);pay.disabled=false;pay.textContent=original;}
}));
