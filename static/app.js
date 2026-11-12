document.querySelectorAll(".scan-form").forEach(form=>{
 form.addEventListener("submit",async e=>{
  e.preventDefault(); const button=form.querySelector("button"), card=form.closest(".tool-card"), out=card.querySelector(".result");
  button.disabled=true; button.textContent="Scanning…"; out.textContent="⏳ CyberLord is checking the target. Please wait…";
  try{
   const response=await fetch("/scan/"+form.dataset.tool,{method:"POST",body:new FormData(form),headers:{"X-Requested-With":"fetch"}});
   const data=await response.json(); if(!response.ok) throw new Error(data.error||"Check failed");
   out.textContent=JSON.stringify(data.result,null,2);
  }catch(err){out.textContent="Error: "+err.message;}
  finally{button.disabled=false;button.textContent="Run check";}
 });
});


// Keep the dashboard compact while allowing users to expand their full scan history.
const historyToggle=document.getElementById("history-toggle");
if(historyToggle){
 historyToggle.addEventListener("click",()=>{
  const expanded=historyToggle.getAttribute("aria-expanded")==="true";
  document.querySelectorAll(".history-extra").forEach(row=>row.hidden=expanded);
  historyToggle.setAttribute("aria-expanded",String(!expanded));
  historyToggle.textContent=expanded?`See all ${document.querySelectorAll(".history-item").length} activities`:"Show less";
 });
}


// Expand/collapse the full tool catalogue while keeping the dashboard compact.
const toolsToggle=document.getElementById("tools-toggle");
if(toolsToggle){
  toolsToggle.addEventListener("click",()=>{
    const expanded=toolsToggle.getAttribute("aria-expanded")==="true";
    document.querySelectorAll(".tool-extra").forEach(card=>card.hidden=expanded);
    toolsToggle.setAttribute("aria-expanded",String(!expanded));
    toolsToggle.textContent=expanded
      ? `See all ${document.querySelectorAll(".tool-card").length} tools`
      : "Show fewer tools";
  });
}

// Copy public payment destinations and bank account numbers with a clear confirmation.
document.querySelectorAll(".copy-value").forEach(button=>{
  button.addEventListener("click",async()=>{
    const value=button.dataset.copy||"";
    const original=button.textContent;
    try{
      await navigator.clipboard.writeText(value);
      button.textContent="Copied";
      setTimeout(()=>button.textContent=original,1400);
    }catch(error){
      button.textContent="Copy unavailable";
      setTimeout(()=>button.textContent=original,1600);
    }
  });
});
