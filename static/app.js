async function cyberLordPrepareImage(file){
  if(!/^image\/(png|jpeg|webp)$/.test(file.type)||file.size>25*1024*1024)throw new Error("Use JPG, PNG or WEBP images up to 25 MB each.");
  let bitmap;try{bitmap=await createImageBitmap(file);}catch(e){throw new Error("This image could not be opened. Try JPG, PNG or WEBP.");}
  try{
    let scale=Math.min(1,4096/Math.max(bitmap.width,bitmap.height));
    const canvas=document.createElement("canvas");canvas.width=Math.max(1,Math.round(bitmap.width*scale));canvas.height=Math.max(1,Math.round(bitmap.height*scale));
    const ctx=canvas.getContext("2d");ctx.fillStyle="#ffffff";ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);
    let quality=0.9, blob=await new Promise(resolve=>canvas.toBlob(resolve,"image/jpeg",quality));
    while(blob&&blob.size>4500000&&quality>0.5){quality-=0.08;blob=await new Promise(resolve=>canvas.toBlob(resolve,"image/jpeg",quality));}
    if(!blob||blob.size>4500000)throw new Error("This image is too large to optimize. Try a smaller image.");
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(",")[1]);reader.onerror=reject;reader.readAsDataURL(blob);});
    return {mime_type:"image/jpeg",data};
  }finally{bitmap.close();}
}

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

// Academy exercise: show one question at a time while preserving all answers for submit.
(function(){
  document.querySelectorAll("[data-quiz-form]").forEach(form=>{
    const questions=[...form.querySelectorAll("[data-quiz-question]")];
    const dots=[...document.querySelectorAll("[data-quiz-dot]")];
    const prev=form.querySelector("[data-quiz-prev]");
    const next=form.querySelector("[data-quiz-next]");
    const submit=form.querySelector("[data-quiz-submit]");
    const status=document.querySelector("[data-quiz-status]");
    if(!questions.length) return;
    let index=0;
    function isAnswered(i){
      return Boolean(questions[i].querySelector("input[type='radio']:checked"));
    }
    function render(){
      questions.forEach((question,i)=>{ question.hidden=i!==index; });
      dots.forEach((dot,i)=>{
        dot.classList.toggle("answered",isAnswered(i));
        if(i===index) dot.setAttribute("aria-current","true");
        else dot.removeAttribute("aria-current");
      });
      prev.disabled=index===0;
      next.hidden=index===questions.length-1;
      submit.hidden=index!==questions.length-1;
      if(status) status.textContent="Question "+(index+1)+" of "+questions.length;
    }
    function go(i){ index=Math.max(0,Math.min(questions.length-1,i)); render(); }
    prev.addEventListener("click",()=>go(index-1));
    next.addEventListener("click",()=>go(index+1));
    dots.forEach(dot=>dot.addEventListener("click",()=>go(Number(dot.dataset.quizDot))));
    form.addEventListener("change",render);
    render();
  });
})();

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

  const linkify=(el)=>{
    // Escape-first: bubble() uses textContent, so re-scan and wrap URLs as links safely.
    const txt = el.textContent;
    if(!/https?:\/\//.test(txt)) return;
    el.textContent = "";
    txt.split(/(https?:\/\/[^\s)]+)/g).forEach(part=>{
      if(/^https?:\/\//.test(part)){
        const a=document.createElement("a");a.href=part;a.target="_blank";a.rel="noopener noreferrer";a.textContent=part;
        el.appendChild(a);
      } else {
        el.appendChild(document.createTextNode(part));
      }
    });
  };
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
    messagesEl.appendChild(el);if(role==="bot")linkify(el);scroll();return el;
  };
  const renderGeneratedMedia=(data, target)=>{
    (data.generated_files||[]).forEach(file=>{
      const wrap=document.createElement("div"),a=document.createElement("a");
      a.href="data:"+(file.mime_type||"application/octet-stream")+";base64,"+file.data;
      a.download=file.filename||"cyberlord-file";a.textContent="⬇ Download "+(file.filename||"file");
      a.className="cl-ai-image-download";wrap.appendChild(a);target.appendChild(wrap);
    });
    (data.generated_videos||[]).forEach(video=>{
      const wrap=document.createElement("div"),el=document.createElement("video");
      const src="data:"+(video.mime_type||"video/mp4")+";base64,"+video.data;
      el.controls=true;el.preload="metadata";el.src=src;el.style.width="100%";el.style.maxWidth="560px";el.style.borderRadius="12px";
      const dl=document.createElement("a");dl.href=src;dl.download=video.filename||"cyberlord-video.mp4";dl.textContent="Download video";dl.className="cl-ai-image-download";
      wrap.appendChild(el);wrap.appendChild(dl);target.appendChild(wrap);
    });
    if(data.file_generation_note) bubble(data.file_generation_note,"bot");
    if(data.video_generation_note) bubble(data.video_generation_note,"bot");
    if(data.video_generation_job_id) watchAgnesVideo(data.video_generation_job_id,target);
  };
  async function watchAgnesVideo(jobId,target){
    const status=bubble("Building your video…","bot");
    for(let attempt=0;attempt<1800;attempt++){
      try{
        const response=await fetch("/api/agnes-video/"+encodeURIComponent(jobId));
        const job=await response.json();
        if(!response.ok)throw new Error(job.error||"Could not read video status.");
        status.textContent=(job.message||"Building your video…")+" ("+(job.progress||0)+"%)";
        if(job.status==="completed"){
          const wrap=document.createElement("div"),video=document.createElement("video");
          video.controls=true;video.preload="metadata";video.src=job.preview_url;video.style.width="100%";video.style.maxWidth="560px";video.style.borderRadius="12px";
          const link=document.createElement("a");link.href=job.download_url;link.download="cyberlord-generated-video.mp4";link.textContent="Download video";link.className="cl-ai-image-download";
          wrap.appendChild(video);wrap.appendChild(link);target.appendChild(wrap);status.textContent="Your video is ready.";scroll();return;
        }
        if(job.status==="failed"){status.textContent="Video generation failed: "+(job.error||"Please try again.");return;}
      }catch(error){status.textContent=error.message||"Unable to check video progress.";return;}
      await new Promise(resolve=>setTimeout(resolve,2000));
    }
    status.textContent="Video generation is taking longer than expected. You can send the request again later.";
  }
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
  async function cyberLordJSON(url, body){const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw new Error(d.error||"Request failed.");return d;}
  function cyberLordPutPart(url, blob){return new Promise((resolve,reject)=>{const x=new XMLHttpRequest();x.open("PUT",url);x.onload=()=>{if(x.status>=200&&x.status<300){const etag=x.getResponseHeader("ETag");etag?resolve(etag):reject(new Error("Storage did not return an upload receipt. Check B2 CORS exposes ETag."));}else reject(new Error("File upload failed (HTTP "+x.status+")."));};x.onerror=()=>reject(new Error("Upload interrupted. Check your connection and try again."));x.send(blob);});}
  async function cyberLordLargeFile(file, question){
    const ext=(file.name.split(".").pop()||"").toLowerCase();const mime=file.type||({docx:"application/vnd.openxmlformats-officedocument.wordprocessingml.document",xlsx:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",pptx:"application/vnd.openxmlformats-officedocument.presentationml.presentation",txt:"text/plain",md:"text/markdown",csv:"text/csv"}[ext]||"application/octet-stream");
    const init=await cyberLordJSON("/api/large-upload/initiate",{filename:file.name,mime_type:mime,size:file.size});const parts=[];const count=Math.ceil(file.size/init.part_size);
    for(let i=0;i<count;i++){const signed=await cyberLordJSON("/api/large-upload/sign-part",{key:init.key,upload_id:init.upload_id,part_number:i+1});parts.push({PartNumber:i+1,ETag:await cyberLordPutPart(signed.url,file.slice(i*init.part_size,Math.min(file.size,(i+1)*init.part_size)))});}
    await cyberLordJSON("/api/large-upload/complete",{key:init.key,upload_id:init.upload_id,parts});return cyberLordJSON("/api/large-upload/analyse",{key:init.key,question:question||"Analyse this file carefully. Explain its important contents and limitations."});
  }
  async function cyberLordAttachment(file, question){
    const ext=(file.name.split(".").pop()||"").toLowerCase();
    if(file.type.startsWith("image/")){const image=await cyberLordPrepareImage(file);return {image};}
    if(file.type.startsWith("audio/") || ["mp3","wav","m4a","ogg"].includes(ext)){
      if(file.size>25*1024*1024)return cyberLordLargeFile(file,question||"Transcribe and analyse this audio.");
      const fd=new FormData();fd.append("audio",file,file.name);const r=await fetch("/api/super-mode/transcribe-audio",{method:"POST",body:fd});const d=await r.json();if(!r.ok)throw new Error(d.error||"Audio transcription failed.");return {text:"Voice note transcription ("+file.name+"):\n"+d.transcript};
    }
    if(["mp4","mov","webm","mpeg","mpg"].includes(ext)||file.size>20*1024*1024)return cyberLordLargeFile(file,question||"Analyse this video or file carefully and summarise the important content.");
    const fd=new FormData();fd.append("document",file,file.name);fd.append("question",question||"Read and analyse this file. Summarise its important contents.");const r=await fetch("/api/super-mode/analyse-document",{method:"POST",body:fd});const d=await r.json();if(!r.ok)throw new Error(d.error||"Document analysis failed.");return {text:"File analysis ("+file.name+"):\n"+(d.analysis||d.text||"")};
  }
  async function send(text, images, files){
    text=(text||"").trim(); images=images||[]; files=files||[];
    if(!text && !images.length && !files.length)return;
    if(!text)text=images.length?"Please analyse the attached picture and explain what you can see.":"Please analyse the attached file.";
    bubble(text,"user");history.push({role:"user",content:text,images:images});
    const pending=bubble("Searching CyberLord knowledge…","bot");
    const startTyping=()=>{const typing=document.createElement("span");typing.className="cl-ai-typing";typing.innerHTML="<span></span><span></span><span></span>";pending.textContent="";pending.appendChild(typing);};startTyping();
    await new Promise(resolve=>setTimeout(resolve,600));
    const submit=form.querySelector("button");submit.disabled=true;
    try{
      if(files.length){
        for(const file of files){pending.textContent="Reading "+file.name+"…";const result=await cyberLordAttachment(file,text);if(result.image){images.push(result.image);}else if(result.text){text+="\n\n"+result.text;history[history.length-1].content=text;}else if(result.analysis){text+="\n\nFile analysis ("+file.name+"):\n"+result.analysis;history[history.length-1].content=text;}}
      }
      const ytMatch=/\b(youtube|youtube video|video on youtube)\b/i.test(text);
      if(ytMatch){try{pending.textContent="Researching YouTube…";const yt=await cyberLordJSON("/api/super-mode/youtube",{query:text});pending.remove();const answer=yt.summary||((yt.items||[]).map(v=>v.title+" — "+v.channel+"\n"+v.url).join("\n\n"))||yt.message||"No YouTube results were returned.";bubble(answer,"bot");history.push({role:"assistant",content:answer});return;}catch(ytErr){bubble("YouTube research: "+ytErr.message,"bot");return;}}
      const res=await fetch("/api/ai-assistant",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({persona:"main",messages:history.slice(-12)})});
      const data=await res.json();
      pending.remove();
      if(!res.ok)throw new Error(data.error||"The assistant is temporarily unavailable.");
      bubble(data.reply,"bot");history.push({role:"assistant",content:data.reply});
      if(data.image_generation_note) bubble(data.image_generation_note,"bot");
      if(Array.isArray(data.generated_images)&&data.generated_images.length){
        data.generated_images.forEach(im=>{const wrap=document.createElement("div");const src="data:"+(im.mime_type||"image/png")+";base64,"+im.data;const el=document.createElement("img");el.alt="Generated by CyberLord";el.src=src;el.style.maxWidth="100%";el.style.borderRadius="12px";const dl=document.createElement("a");dl.href=src;dl.download="cyberlord-generated-image.png";dl.textContent="Download image";dl.className="cl-ai-image-download";wrap.appendChild(el);wrap.appendChild(dl);messagesEl.appendChild(wrap);});
      }
      renderGeneratedMedia(data,messagesEl);
      if(Array.isArray(data.images)&&data.images.length){
        const grid=document.createElement("div");grid.className="cl-ai-images";
        data.images.forEach(img=>{
          const a=document.createElement("a");a.href=img.url||"#";a.target="_blank";a.rel="noopener noreferrer";
          const im=document.createElement("img");im.src=img.thumb||img.url;im.alt=img.title||"image";im.loading="lazy";
          a.appendChild(im);grid.appendChild(a);
        });
        messagesEl.appendChild(grid);scroll();
      }
    }catch(err){pending.textContent=err.message||"Something went wrong. Please try again.";}
    finally{submit.disabled=false;scroll();}
  }
  const imageInput=document.getElementById("cl-ai-image");
  const attachBtn=document.getElementById("cl-ai-attach");
  let selectedFiles=[];
  if(attachBtn&&imageInput)attachBtn.addEventListener("click",()=>imageInput.click());
  if(imageInput)imageInput.addEventListener("change",()=>{selectedFiles=Array.from(imageInput.files||[]).slice(0,4);attachBtn.textContent=selectedFiles.length?"📎 "+selectedFiles.length:"📎";imageInput.value="";});
  form.addEventListener("submit",e=>{e.preventDefault();const value=input.value;input.value="";const files=selectedFiles;selectedFiles=[];if(attachBtn)attachBtn.textContent="📎";send(value,[],files);});
  const launchQuestion=new URLSearchParams(window.location.search).get("ask");
  if(launchQuestion){toggle(true);send(launchQuestion);window.history.replaceState({},document.title,window.location.pathname+window.location.hash);}
})();

// Academy tutor: per-lesson questions go to /api/ai-assistant with lesson_slug for context.
(function(){
  document.querySelectorAll(".tutor-form").forEach(form=>{
    const card=form.closest(".tutor-card"); if(!card) return;
    const slug=card.dataset.lesson||"";
    const box=card.querySelector(".tutor-messages");
    const input=form.querySelector('input[type="text"]');
    const imageInput=form.querySelector(".tutor-image-input");
    const attachBtn=form.querySelector(".tutor-image-attach");
    let selectedImages=[];
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
    function renderGeneratedMedia(data,target){
      (data.generated_files||[]).forEach(file=>{const a=document.createElement("a");a.href="data:"+(file.mime_type||"application/octet-stream")+";base64,"+file.data;a.download=file.filename||"cyberlord-file";a.textContent="⬇ Download "+(file.filename||"file");a.className="cl-ai-image-download";target.appendChild(a);});
      (data.generated_videos||[]).forEach(video=>{const wrap=document.createElement("div"),el=document.createElement("video"),src="data:"+(video.mime_type||"video/mp4")+";base64,"+video.data;el.controls=true;el.preload="metadata";el.src=src;el.style.width="100%";el.style.maxWidth="560px";el.style.borderRadius="12px";const a=document.createElement("a");a.href=src;a.download=video.filename||"cyberlord-video.mp4";a.textContent="Download video";a.className="cl-ai-image-download";wrap.appendChild(el);wrap.appendChild(a);target.appendChild(wrap);});
      if(data.file_generation_note)add(data.file_generation_note,"bot");if(data.video_generation_note)add(data.video_generation_note,"bot");
      if(data.video_generation_job_id)watchTutorAgnesVideo(data.video_generation_job_id,target);
    }
    async function watchTutorAgnesVideo(jobId,target){
      const status=add("Building your video…","bot");
      for(let attempt=0;attempt<1800;attempt++){
        try{
          const response=await fetch("/api/agnes-video/"+encodeURIComponent(jobId));const job=await response.json();
          if(!response.ok)throw new Error(job.error||"Could not read video status.");
          status.textContent=(job.message||"Building your video…")+" ("+(job.progress||0)+"%)";
          if(job.status==="completed"){
            const wrap=document.createElement("div"),video=document.createElement("video");video.controls=true;video.preload="metadata";video.src=job.preview_url;video.style.width="100%";video.style.maxWidth="560px";video.style.borderRadius="12px";
            const link=document.createElement("a");link.href=job.download_url;link.download="cyberlord-generated-video.mp4";link.textContent="Download video";link.className="cl-ai-image-download";wrap.appendChild(video);wrap.appendChild(link);target.appendChild(wrap);status.textContent="Your video is ready.";return;
          }
          if(job.status==="failed"){status.textContent="Video generation failed: "+(job.error||"Please try again.");return;}
        }catch(error){status.textContent=error.message||"Unable to check video progress.";return;}
        await new Promise(resolve=>setTimeout(resolve,2000));
      }
      status.textContent="Video generation is taking longer than expected.";
    }
    function readSelected(files){
      return Promise.all(Array.from(files||[]).slice(0,4).map(file=>{
        return cyberLordPrepareImage(file);
      }));
    }
    if(attachBtn&&imageInput){
      attachBtn.addEventListener("click",()=>imageInput.click());
      imageInput.addEventListener("change",async()=>{try{selectedImages=await readSelected(imageInput.files);attachBtn.textContent="📎 "+selectedImages.length;}catch(err){alert(err.message);selectedImages=[];}imageInput.value="";});
    }
    form.addEventListener("submit",async e=>{
      e.preventDefault();
      let text=(input.value||"").trim();const images=selectedImages;selectedImages=[];if(attachBtn)attachBtn.textContent="📎 Image";
      if(!text&&!images.length) return;
      if(!text)text="Please analyse the attached picture and explain what you can see.";
      add(text,"user"); input.value="";
      const pending=add("Thinking…","bot");
      try{
        const res=await fetch("/api/ai-assistant",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({persona:"tutor",lesson_slug:slug,messages:[{role:"user",content:text,images:images}]})});
        const data=await res.json();
        pending.remove();
        if(!res.ok){
          if(res.status===429){
            var lock=card.querySelector(".tutor-lock")||document.getElementById("tutor-lock");
            if(lock) lock.hidden=false;
            input.disabled=true; form.querySelector("button[type=submit]").disabled=true;
          }
          throw new Error(data.error||"The tutor is temporarily unavailable.");
        }
        add(data.reply,"bot");
        if(data.image_generation_note) add(data.image_generation_note,"bot");
        if(Array.isArray(data.generated_images)) data.generated_images.forEach(im=>{const wrap=document.createElement("div"),src="data:"+(im.mime_type||"image/png")+";base64,"+im.data,pic=document.createElement("img");pic.src=src;pic.alt="Generated by CyberLord Tutor";pic.style.maxWidth="100%";pic.style.borderRadius="12px";const dl=document.createElement("a");dl.href=src;dl.download="cyberlord-tutor-image.png";dl.textContent="Download image";dl.className="cl-ai-image-download";wrap.appendChild(pic);wrap.appendChild(dl);box.appendChild(wrap);});
        renderGeneratedMedia(data,box);
      }catch(err){ pending.textContent=err.message||"Something went wrong. Please try again."; }
    });
  });
})();
