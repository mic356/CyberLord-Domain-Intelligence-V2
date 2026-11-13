// CyberLord Tutor voice: Web Speech API (speechSynthesis + SpeechRecognition) —
// free, built into phone and desktop browsers. No API key, no cost. Degrades
// silently when the browser has neither capability.
//
// ChatGPT-style voice bar: press and hold the mic to record, release to send.
// A quick tap puts the transcript in the input for editing instead of sending.
// Replies to a voice question are spoken aloud automatically.

(function () {
  "use strict";

  var LS = "cl-voice-replies";
  var voiceOn = false;
  try { voiceOn = localStorage.getItem(LS) === "1"; } catch (e) {}
  // True while the user is mid-hold on a mic button.
  var holding = false;

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

  // speak(text, force) — normally honors the voiceOn toggle; force bypasses it
  // (used for the hands-free reply after a voice question).
  function speak(text, force) {
    if (!ttsOK() || (!force && !voiceOn)) return;
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

  // Auto-speak new bot replies when voice replies are ON, or when the last
  // question was asked by voice. The composer marks bot bumps with
  // data-voice="auto" (voice question) before the reply is appended.
  function scan(root) {
    var scope = root || document;
    if (!scope.querySelectorAll) return;
    scope.querySelectorAll(".tutor-msg.bot, .cl-ai-message.bot, .chat-msg.bot").forEach(function (el) {
      if (el.dataset.voiceReady === "1") return;
      el.dataset.voiceReady = "1";
      var txt = el.textContent;
      if (el.dataset.voice === "auto") speak(txt, true);
      else if (voiceOn) speak(txt);
    });
  }

  // Mark the in-flight question as voice/typed on the form before submit.
  function markFormInput(form, wasVoice) {
    if (!form) return;
    form.dataset.voiceInput = wasVoice ? "voice" : "typed";
  }

  // When a composer submit fires, tag the next bot reply it appends. We do
  // this by flagging the form and post-processing appended nodes through the
  // observer: the observer already scans new bot nodes, so we only need the
  // form flag to survive until then. Store it per thread element.
  function flagNextBot(ctx, wasVoice) {
    if (!ctx) return;
    // ctx is the form; find its message list and set a pending flag.
    var list = ctx.parentNode && ctx.parentNode.querySelector(
      ".tutor-messages, .chat-thread, .cl-ai-thread");
    if (!list) list = ctx.closest("section, aside, div") &&
      ctx.closest("section, aside, div").querySelector(
        ".tutor-messages, .chat-thread, .cl-ai-thread");
    if (list) list.dataset.voicePending = wasVoice ? "voice" : "typed";
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

  // ---- tap-and-hold voice bar ----
  // Press (mousedown/touchstart) starts recording, release (mouseup/touchend)
  // stops; a short hold fills the input for editing, a longer hold sends.
  var HOLD_MS = 350; // under this, treat as a tap: fill input, do not send
  function bindMic(b) {
    if (!sttOK()) { b.style.display = "none"; return; }
    if (b.dataset.micBound === "1") return;
    b.dataset.micBound = "1";
    // Long-press must not bring up the context menu on mobile.
    b.addEventListener("contextmenu", function (e) { e.preventDefault(); });

    var rec = null, pressStart = 0, released = false, transcript = "", done = false, pointerIn = true;

    function setListening(on) {
      holding = !!on;
      b.classList.toggle("listening", !!on);
      b.classList.toggle("voice-holding", !!on);
      b.textContent = on ? "●" : "🎙";
      b.setAttribute("aria-label", on ? "Listening… release to send" : "Press and hold to talk");
      setBars(b, on);
      if (on && window.navigator && navigator.vibrate) { try { navigator.vibrate(20); } catch (e) {} }
    }
    function setBars(btn, on) {
      var bars;
      if (on) {
        bars = document.createElement("span");
        bars.className = "voice-bars";
        bars.setAttribute("aria-hidden", "true");
        for (var i = 0; i < 5; i++) bars.appendChild(document.createElement("i"));
        btn.insertAdjacentElement("afterend", bars);
      } else {
        var el = btn.nextElementSibling;
        if (el && el.classList && el.classList.contains("voice-bars")) el.remove();
        document.querySelectorAll(".voice-bars").forEach(function (x) { x.remove(); });
      }
    }
    function start() {
      var Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!Ctor) return;
      try {
        rec = new Ctor();
        rec.lang = "en-US";
        rec.interimResults = true;
        rec.maxAlternatives = 1;
        rec.continuous = true;
        transcript = ""; done = false; released = false;
        rec.onresult = function (ev) {
          var text = "";
          for (var i = 0; i < ev.results.length; i++) {
            if (ev.results[i] && ev.results[i][0]) text += ev.results[i][0].transcript;
          }
          transcript = (text || "").trim();
        };
        rec.onerror = function () {};
        rec.onend = function () {
          if (released) finish();
        };
        setListening(true);
        rec.start();
      } catch (e) { setListening(false); }
    }
    function stop() {
      if (rec && !done && !released) {
        released = true;
        try { rec.stop(); } catch (e) {}
        // Some browsers never fire onend after stop; finish after a beat.
        setTimeout(function () { if (!done) finish(); }, 800);
      } else if (!rec) {
        finish();
      }
    }
    function finish() {
      if (done) return;
      done = true;
      setListening(false);
      var text = transcript || "";
      rec = null;
      if (!text) return;
      var form = b.closest("form");
      var input = form ? form.querySelector("input[type='text'], input:not([type])") : null;
      var quick = (Date.now() - pressStart) < HOLD_MS;
      if (quick) {
        // Quick tap: park the transcript in the input for editing, no send.
        if (input) { input.value = text; input.focus(); }
        return;
      }
      if (input) input.value = text;
      markFormInput(form, true);
      flagNextBot(form, true);
      if (form) {
        if (form.requestSubmit) form.requestSubmit();
        else form.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    }

    function press(e) {
      if (e && e.cancelable) e.preventDefault();
      pressStart = Date.now();
      start();
    }
    function release() {
      if (rec || holding) stop();
    }
    b.addEventListener("mousedown", press);
    window.addEventListener("mouseup", release);
    b.addEventListener("touchstart", press, { passive: false });
    window.addEventListener("touchend", release);
    window.addEventListener("touchcancel", release);
    // Slide off the button with the pointer held: keep recording until release.
    document.addEventListener("mouseleave", function () { pointerIn = false; });
    // Keyboard: Enter or Space on the focused button records while held.
    b.addEventListener("keydown", function (e) {
      if ((e.key === "Enter" || e.key === " ") && !e.repeat) { e.preventDefault(); press(e); }
    });
    b.addEventListener("keyup", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); release(); }
    });
  }

  // Track typed vs voice submissions: a normal submit is typed unless the mic
  // already claimed it. The form's submit listener below runs before the
  // composer's own handler thanks to capture priority.
  function watchForms(scope) {
    var root = scope || document;
    if (!root.querySelectorAll) return;
    root.querySelectorAll("form").forEach(function (form) {
      if (form.dataset.voiceWatch === "1") return;
      form.dataset.voiceWatch = "1";
      form.addEventListener("submit", function () {
        if (form.dataset.voiceInput === "voice") return; // mic already flagged it
        form.dataset.voiceInput = "typed";
        flagNextBot(form, false);
      }, true);
      form.addEventListener("submit", function () {
        setTimeout(function () { form.dataset.voiceInput = ""; }, 0);
      });
    });
  }

  function wireComposers(scope) {
    if (!scope.querySelectorAll) return;
    scope.querySelectorAll("[data-voice-toggle]").forEach(bindToggle);
    scope.querySelectorAll("[data-mic-btn]").forEach(bindMic);
    watchForms(scope);
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
            // Claim the pending flag from the owning thread so a voice
            // question's reply is spoken even with the toggle off.
            var t = node.closest(".tutor-messages, .chat-thread, .cl-ai-thread");
            if (t && t.dataset.voicePending === "voice") node.dataset.voice = "auto";
            if (t) delete t.dataset.voicePending;
            scan(node.parentNode || document);
          } else if (node.querySelectorAll) {
            node.querySelectorAll(".tutor-msg.bot, .cl-ai-message.bot, .chat-msg.bot").forEach(function (el) {
              var t = el.closest(".tutor-messages, .chat-thread, .cl-ai-thread");
              if (t && t.dataset.voicePending === "voice") el.dataset.voice = "auto";
              if (t) delete t.dataset.voicePending;
            });
            scan(node);
          }
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  } catch (e) {}
})();
