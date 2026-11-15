document.querySelectorAll(".scan-form").forEach(form=>{
 form.addEventListener("submit",async e=>{
  e.preventDefault(); const button=form.querySelector("button"), card=form.closest(".tool-card"), out=card.querySelector(".result");
  button.disabled=true; button.textContent="Scanning…"; card.classList.add("scanning"); out.textContent="⏳ CyberLord is checking the target. Please wait…";
  try{
   const response=await fetch("/scan/"+form.dataset.tool,{method:"POST",body:new FormData(form),headers:{"X-Requested-With":"fetch"}});
   const data=await response.json(); if(!response.ok) throw new Error(data.error||"Check failed");
   out.textContent=JSON.stringify(data.result,null,2);
  }catch(err){out.textContent="Error: "+err.message;}
  finally{button.disabled=false;button.textContent="Run check";card.classList.remove("scanning");}
 });
});


// Theme toggle: bright (yesterday) is default, dark navy is opt-in. Stored in localStorage.
(function(){
  var root = document.documentElement;
  var btn = document.getElementById("theme-toggle");
  function sync(){
    var light = root.dataset.theme === "light";
    if (btn) btn.setAttribute("aria-pressed", String(light));
    try{
      var meta = document.getElementById("theme-color-meta");
      if (meta) meta.content = light ? "#f4f7fb" : "#0b1220";
    }catch(e){}
  }
  sync();
  if (btn) {
    btn.addEventListener("click", function(){
      var next = root.dataset.theme === "light" ? "dark" : "light";
      root.dataset.theme = next;
      try{ localStorage.setItem("cl-theme", next); }catch(e){}
      sync();
    });
  }
})();

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


// Scan progress markup + AI typing indicator (academy-upgrades).
document.querySelectorAll(".tool-card").forEach(card=>{
  const form=card.querySelector(".scan-form"); if(!form) return;
  const body=document.createElement("div");
  body.innerHTML='<div class="scan-progress" aria-hidden="true"></div><div class="scan-card-indicator"><span class="spinner" aria-hidden="true"></span>Scanning, please wait…</div>';
  form.after(body);
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
    // Reuse the live voice bubble so a spoken question already shown
    // as text before sending is not added twice.
    if (role === "user") {
      var pending = messagesEl.querySelector("[data-voice-pending='1']");
      if (pending && pending.textContent === text) {
        pending.removeAttribute("data-voice-pending");
        return pending;
      }
    }
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
  document.querySelectorAll("[data-ai-guide]").forEach(btn=>{
    btn.addEventListener("click",()=>{toggle(true);send(btn.dataset.aiGuide||btn.textContent);});
  });
  async function send(text){
    text=(text||"").trim();if(!text)return;
    bubble(text,"user");history.push({role:"user",content:text});
    const pending=bubble("Searching CyberLord knowledge…","bot");
    const startTyping=()=>{const typing=document.createElement("span");typing.className="cl-ai-typing";typing.innerHTML="<span></span><span></span><span></span>";pending.textContent="";pending.appendChild(typing);};startTyping();
    await new Promise(resolve=>setTimeout(resolve,600));
    const submit=form.querySelector("button");submit.disabled=true;
    try{
      const res=await fetch("/api/ai-assistant",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({persona:"main",messages:history.slice(-12)})});
      const data=await res.json();
      pending.remove();
      if(!res.ok)throw new Error(data.error||"The assistant is temporarily unavailable.");
      bubble(data.reply,"bot");history.push({role:"assistant",content:data.reply});
    }catch(err){pending.textContent=err.message||"Something went wrong. Please try again.";}
    finally{submit.disabled=false;scroll();}
  }
  form.addEventListener("submit",e=>{e.preventDefault();const value=input.value;input.value="";send(value);});
  const launchQuestion=new URLSearchParams(window.location.search).get("ask");
  if(launchQuestion){toggle(true);send(launchQuestion);window.history.replaceState({},document.title,window.location.pathname+window.location.hash);}
})();

// Academy tutor: per-lesson questions go to /api/ai-assistant with lesson_slug for context.
(function(){
  document.querySelectorAll(".tutor-form").forEach(form=>{
    const card=form.closest(".tutor-card"); if(!card) return;
    const slug=card.dataset.lesson||"";
    const box=card.querySelector(".tutor-messages");
    const input=form.querySelector("input");
    function add(text,role){
      // Reuse the live voice bubble so a spoken question already shown
      // as text before sending is not added twice.
      if (role === "user") {
        var pending = box.querySelector("[data-voice-pending='1']");
        if (pending && pending.textContent === text) {
          pending.removeAttribute("data-voice-pending");
          return pending;
        }
      }
      const el=document.createElement("div");
      el.className="tutor-msg "+role; el.textContent=text;
      box.appendChild(el); box.scrollTop=box.scrollHeight;
      return el;
    }
    form.addEventListener("submit",async e=>{
      e.preventDefault();
      const text=(input.value||"").trim(); if(!text) return;
      add(text,"user"); input.value="";
      const pending=add("Thinking…","bot");
      try{
        const res=await fetch("/api/ai-assistant",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({persona:"tutor",lesson_slug:slug,messages:[{role:"user",content:text}]})});
        const data=await res.json();
        pending.remove();
        if(!res.ok) throw new Error(data.error||"The tutor is temporarily unavailable.");
        add(data.reply,"bot");
      }catch(err){ pending.textContent=err.message||"Something went wrong. Please try again."; }
    });
  });
})();
