// CyberLord Tutor voice: Web Speech API (speechSynthesis + SpeechRecognition) —
// free, built into phone and desktop browsers. No API key, no cost. Degrades
// silently when the browser has neither capability.

(function () {
  "use strict";

  var LS = "cl-voice-replies";
  var voiceOn = false;
  try { voiceOn = localStorage.getItem(LS) === "1"; } catch (e) {}

  function ttsOK() {
    try { return "speechSynthesis" in window && "SpeechSynthesisUtterance" in window; }
    catch (e) { return false; }
  }
  function sttOK() {
    try { return !!window.SpeechRecognition || !!window.webkitSpeechRecognition; }
    catch (e) { return false; }
  }
  if (!ttsOK() && !sttOK()) return;

  function pickEnglishVoice() {
    try {
      var voices = window.speechSynthesis.getVoices() || [];
      for (var i = 0; i < voices.length; i++) {
        if (voices[i] && /^en(-|_)/i.test(voices[i].lang || "")) return voices[i];
      }
      for (var j = 0; j < voices.length; j++) {
        if (voices[j] && /english/i.test(voices[j].name || "")) return voices[j];
      }
    } catch (e) {}
    return null;
  }
  if (ttsOK()) { try { window.speechSynthesis.onvoiceschanged = function () {}; } catch (e) {} }

  function speak(text) {
    if (!ttsOK() || !voiceOn) return;
    try {
      window.speechSynthesis.cancel();
      var clean = String(text || "").replace(/\s+/g, " ").trim().slice(0, 900);
      if (!clean) return;
      var utter = new SpeechSynthesisUtterance(clean);
      utter.lang = "en-US";
      utter.rate = 1.0;
      var voice = pickEnglishVoice();
      if (voice) utter.voice = voice;
      window.speechSynthesis.speak(utter);
    } catch (e) {}
  }
  function stopSpeak() { try { if (ttsOK()) window.speechSynthesis.cancel(); } catch (e) {} }

  // Auto-speak new bot replies when voice replies are ON.
  function scan(root) {
    var scope = root || document;
    if (!scope.querySelectorAll) return;
    scope.querySelectorAll(".tutor-msg.bot, .cl-ai-message.bot, .chat-msg.bot").forEach(function (el) {
      if (el.dataset.voiceReady === "1") return;
      el.dataset.voiceReady = "1";
      var txt = el.textContent;
      if (voiceOn) speak(txt);
    });
  }

  // ---- speaker toggle at the bottom of each composer ----
  function refreshToggles() {
    document.querySelectorAll("[data-voice-toggle]").forEach(function (b) {
      b.setAttribute("aria-pressed", voiceOn ? "true" : "false");
      b.classList.toggle("on", voiceOn);
      b.textContent = voiceOn ? "🔊" : "🔈";
    });
  }
  function bindToggle(b) {
    if (b.dataset.voiceBound === "1") return;
    b.dataset.voiceBound = "1";
    b.addEventListener("click", function () {
      voiceOn = !voiceOn;
      try { localStorage.setItem(LS, voiceOn ? "1" : "0"); } catch (e) {}
      refreshToggles();
      if (!voiceOn) stopSpeak();
    });
  }
  function bindMic(b) {
    if (!sttOK()) { b.style.display = "none"; return; }
    if (b.dataset.micBound === "1") return;
    b.dataset.micBound = "1";
    b.addEventListener("click", function () {
      var Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
      try {
        var rec = new Ctor();
        rec.lang = "en-US";
        rec.interimResults = false;
        rec.maxAlternatives = 1;
        b.textContent = "●";
        b.classList.add("listening");
        rec.onresult = function (ev) {
          var text = (ev.results[0][0].transcript || "").trim();
          b.textContent = "🎙"; b.classList.remove("listening");
          if (text) {
            var form = b.closest("form");
            var input = form ? form.querySelector("input[type='text'], input:not([type])") : null;
            if (input) { input.value = text; }
            if (form) {
              if (form.requestSubmit) form.requestSubmit();
              else form.dispatchEvent(new Event("submit", { cancelable: true }));
            }
          }
        };
        rec.onerror = rec.onend = function () { b.textContent = "🎙"; b.classList.remove("listening"); };
        rec.start();
      } catch (e) { b.textContent = "🎙"; b.classList.remove("listening"); }
    });
  }
  function wireComposers(scope) {
    if (!scope.querySelectorAll) return;
    scope.querySelectorAll("[data-voice-toggle]").forEach(bindToggle);
    scope.querySelectorAll("[data-mic-btn]").forEach(bindMic);
    refreshToggles();
  }
  wireComposers(document);

  scan(document);
  try {
    var observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        m.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          wireComposers(node);
          if (node.matches && node.matches(".tutor-msg.bot, .cl-ai-message.bot, .chat-msg.bot")) {
            scan(node.parentNode || document);
          } else if (node.querySelectorAll) {
            scan(node);
          }
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  } catch (e) {}
})();
