(function () {
  "use strict";
  const card = document.querySelector(".academy-live-quiz");
  if (!card) return;
  const slug = card.dataset.lessonSlug;
  const generateBtn = card.querySelector("[data-generate-quiz]");
  const form = card.querySelector("[data-live-quiz-form]");
  const questionsBox = card.querySelector("[data-live-quiz-questions]");
  const status = card.querySelector(".live-quiz-status");
  const results = card.querySelector("[data-live-quiz-results]");
  let quizId = null;
  let busy = false;

  function message(text, kind) {
    status.textContent = text;
    status.className = "live-quiz-status" + (kind ? " " + kind : "");
  }
  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, ch => ({
      "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
    }[ch]));
  }
  async function post(url, payload) {
    const response = await fetch(url, {
      method:"POST", credentials:"same-origin",
      headers:{"Content-Type":"application/json","X-Requested-With":"XMLHttpRequest"},
      body:JSON.stringify(payload)
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.error || "The request could not be completed.");
    return data;
  }
  generateBtn.addEventListener("click", async () => {
    if (busy) return;
    busy = true; generateBtn.disabled = true;
    form.hidden = true; results.innerHTML = "";
    message("Preparing questions from this lesson…", "working");
    try {
      const data = await post("/api/academy/quiz/generate", {lesson_slug:slug});
      quizId = data.quiz_id;
      questionsBox.innerHTML = data.questions.map((q, i) => `
        <fieldset class="live-quiz-question">
          <legend>Q${i+1}. ${escapeHtml(q.question)}</legend>
          ${q.choices.map((choice, j) => `
            <label class="quiz-choice">
              <input type="radio" name="answer_${i}" value="${j}" required>
              <span>${escapeHtml(choice)}</span>
            </label>`).join("")}
        </fieldset>`).join("");
      form.hidden = false;
      message(data.message + " · " + data.questions.length + " questions.", "success");
      generateBtn.textContent = "Generate another set ↻";
    } catch (err) {
      message(err.message, "error");
    } finally {
      busy = false; generateBtn.disabled = false;
    }
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (busy || !quizId) return;
    const answers = [];
    for (let i = 0; i < questionsBox.querySelectorAll("fieldset").length; i++) {
      const picked = form.querySelector(`input[name="answer_${i}"]:checked`);
      if (!picked) { message("Please answer every question before submitting.", "error"); return; }
      answers.push(Number(picked.value));
    }
    busy = true;
    form.querySelector('button[type="submit"]').disabled = true;
    message("Marking your assessment and saving your progress…", "working");
    try {
      const data = await post("/api/academy/quiz/submit", {quiz_id:quizId, answers});
      const feedback = data.feedback.map((item, i) => `
        <div class="quiz-result ${item.correct ? "correct" : "incorrect"}">
          <strong>Question ${i+1}: ${item.correct ? "Correct" : "Not quite — here's the right answer"}</strong>
          ${item.correct ? "" : `<p class="quiz-correct-answer"><b>Correct answer:</b> ${escapeHtml(item.correct_answer || "Review the lesson notes")}</p>`}
          <p>${escapeHtml(item.explain || (item.correct ? "Good work." : "Review the lesson notes and try again."))}</p>
        </div>`).join("");
      results.innerHTML = `<div class="live-score"><strong>${data.score}%</strong><span>${data.correct}/${data.total} correct · Best score ${data.best_score}%</span>
        <p>${data.completed ? "Lesson completed. Excellent work." : "Keep practising. Review the explanations and generate another question set."}</p></div>${feedback}`;
      message("Assessment complete. Your progress has been saved.", "success");
      quizId = null;
      form.hidden = true;
    } catch (err) {
      message(err.message, "error");
    } finally {
      busy = false;
      const submit = form.querySelector('button[type="submit"]');
      if (submit) submit.disabled = false;
    }
  });
})();