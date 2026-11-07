document.querySelectorAll(".scan-form").forEach(form=>{
 form.addEventListener("submit",async e=>{
  e.preventDefault(); const button=form.querySelector("button"), card=form.closest(".tool-card"), out=card.querySelector(".result");
  button.disabled=true; button.textContent="Checking…"; out.textContent="Running authorized check…";
  try{
   const response=await fetch("/scan/"+form.dataset.tool,{method:"POST",body:new FormData(form),headers:{"X-Requested-With":"fetch"}});
   const data=await response.json(); if(!response.ok) throw new Error(data.error||"Check failed");
   out.textContent=JSON.stringify(data.result,null,2);
  }catch(err){out.textContent="Error: "+err.message;}
  finally{button.disabled=false;button.textContent="Run check";}
 });
});
