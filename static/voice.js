// CyberLord Tutor voice: Web Speech API (speechSynthesis) — free, built into
// phone and desktop browsers. No API key, no cost. If the browser does not
// support it, every speaker button stays hidden (silent degrade).

(function () {
  "use strict";

  function supported() {
    try {
      return "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
    } catch (e) {
      return false;
    }
  }

  if (!supported()) return; // degrade silently: no buttons, no errors

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

  // Voices often load asynchronously; refresh the pick when they arrive.
  try {
    window.speechSynthesis.onvoiceschanged = function () {};
  } catch (e) {}

  function speak(text, btn) {
    try {
      window.speechSynthesis.cancel();
      var clean = String(text || "").replace(/\s+/g, " ").trim().slice(0, 900);
      if (!clean) return;
      var utter = new SpeechSynthesisUtterance(clean);
      utter.lang = "en-US";
      utter.rate = 1.0;
      var voice = pickEnglishVoice();
      if (voice) utter.voice = voice;
      if (btn) {
        btn.textContent = "⏹ Stop";
        utter.onend = utter.onerror = function () {
          btn.textContent = "🔊 Listen";
        };
      }
      window.speechSynthesis.speak(utter);
    } catch (e) {
      if (btn) btn.textContent = "🔊 Listen";
    }
  }

  function makeButton(messageEl) {
    if (!messageEl || messageEl.dataset.voiceReady === "1") return;
    messageEl.dataset.voiceReady = "1";
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "speak-btn";
    btn.textContent = "🔊 Listen";
    btn.setAttribute("aria-label", "Listen to this answer");
    btn.addEventListener("click", function () {
      if (window.speechSynthesis.speaking) {
        try { window.speechSynthesis.cancel(); } catch (e) {}
        btn.textContent = "🔊 Listen";
      } else {
        speak(messageEl.textContent.replace(/🔊 Listen|⏹ Stop/g, ""), btn);
      }
    });
    messageEl.appendChild(btn);
  }

  function scan(root) {
    var scope = root || document;
    if (!scope.querySelectorAll) return;
    scope.querySelectorAll(".tutor-msg.bot, .cl-ai-message.bot, .chat-msg.bot").forEach(function (el) {
      makeButton(el);
    });
  }

  // Attach buttons to replies that already exist, and to future replies.
  scan(document);
  try {
    var observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        m.addedNodes.forEach(function (node) {
          if (node.nodeType === 1) {
            if (node.matches && node.matches(".tutor-msg.bot, .cl-ai-message.bot, .chat-msg.bot")) {
              makeButton(node);
            } else if (node.querySelectorAll) {
              scan(node);
            }
          }
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  } catch (e) {}
})();
