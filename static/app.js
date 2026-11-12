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


// CyberLord AI support chat: conversations are sent to the authenticated Flask backend.
(()=>{
  const panel=document.getElementById("cl-ai-panel");
  const open=document.getElementById("cl-ai-open");
  const close=document.getElementById("cl-ai-close");
  const form=document.getElementById("cl-ai-form");
  const input=document.getElementById("cl-ai-input");
  const messagesEl=document.getElementById("cl-ai-messages");
  if(!panel||!open||!form)return;
  const history=[];
  const scroll=()=>{messagesEl.scrollTop=messagesEl.scrollHeight};
  const bubble=(text,role)=>{
    const el=document.createElement("div");
    el.className="cl-ai-message "+role;
    el.textContent=text;
    messagesEl.appendChild(el);scroll();return el;
  };
  const toggle=(show)=>{
    panel.hidden=!show;open.setAttribute("aria-expanded",String(show));
    if(show)input.focus();
  };
  open.addEventListener("click",()=>toggle(panel.hidden));
  close.addEventListener("click",()=>toggle(false));
  document.querySelectorAll(".cl-ai-options button").forEach(btn=>{
    btn.addEventListener("click",()=>send(btn.dataset.question||btn.textContent));
  });
  async function send(text){
    text=(text||"").trim();if(!text)return;
    bubble(text,"user");history.push({role:"user",content:text});
    const pending=bubble("Searching CyberLord knowledge…","bot");
    const submit=form.querySelector("button");submit.disabled=true;
    try{
      const res=await fetch("/api/ai-assistant",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({messages:history.slice(-12)})});
      const data=await res.json();
      pending.remove();
      if(!res.ok)throw new Error(data.error||"The assistant is temporarily unavailable.");
      bubble(data.reply,"bot");history.push({role:"assistant",content:data.reply});
    }catch(err){pending.textContent=err.message||"Something went wrong. Please try again.";}
    finally{submit.disabled=false;scroll();}
  }
  form.addEventListener("submit",e=>{e.preventDefault();const value=input.value;input.value="";send(value);});
})();
