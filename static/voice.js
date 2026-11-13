// CyberLord voice controls.
// Speech-to-text uses the browser Web Speech API (no API key or server cost).
// Tap the microphone once to start, then tap again to stop. The transcript is
// placed in the message field for review/editing; the user presses Send.
(function () {
  "use strict";

  var VOICE_PREF = "cl-voice-replies";
  var voiceOn = false;
  var activeRecognition = null;
  var activeButton = null;
  var finalTranscript = "";
  var interimTranscript = "";

  try { voiceOn = localStorage.getItem(VOICE_PREF) === "1"; } catch (e) {}

  function recognitionConstructor() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }
  function speechSynthesisAvailable() {
    return "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  }
  function getInput(button) {
    var form = button && button.closest("form");
    return form ? form.querySelector("input[type='text'], input:not([type]), textarea") : null;
  }
  function updateButton(button, listening) {
    if (!button) return;
    button.classList.toggle("listening", listening);
    button.setAttribute("aria-pressed", listening ? "true" : "false");
    button.textContent = listening ? "■" : "🎙";
    button.setAttribute("aria-label", listening ? "Stop voice recording" : "Start voice input");
    button.title = listening ? "Tap to stop recording" : "Tap to speak";
    if (listening) {
      var bars = document.createElement("span");
      bars.className = "voice-bars";
      bars.setAttribute("aria-hidden", "true");
      for (var i = 0; i < 5; i++) bars.appendChild(document.createElement("i"));
      button.insertAdjacentElement("afterend", bars);
    } else {
      var next = button.nextElementSibling;
      if (next && next.classList.contains("voice-bars")) next.remove();
    }
  }
  function showMessage(form, message) {
    var status = form && form.parentNode && form.parentNode.querySelector(".voice-status");
    if (!status && form) {
      status = document.createElement("small");
      status.className = "voice-status";
      status.setAttribute("role", "status");
      form.insertAdjacentElement("afterend", status);
    }
    if (status) status.textContent = message || "";
  }
  function finishRecognition(button, input, form) {
    if (button) updateButton(button, false);
    activeRecognition = null;
    activeButton = null;
    var transcript = (finalTranscript || interimTranscript || "").trim();
    if (input && transcript) {
      input.value = transcript;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.focus();
      showMessage(form, "Speech converted to text. Review it, then press Send.");
    } else if (form) {
      showMessage(form, "No speech was recognised. Please try again.");
    }
  }
  function startRecording(button) {
    var Ctor = recognitionConstructor();
    var input = getInput(button);
    var form = button.closest("form");
    if (!Ctor) {
      showMessage(form, "Voice input is not supported in this browser. Try Chrome on Android or desktop.");
      return;
    }
    if (!input) {
      showMessage(form, "The message input could not be found.");
      return;
    }
    try {
      var recognition = new Ctor();
      activeRecognition = recognition;
      activeButton = button;
      finalTranscript = "";
      interimTranscript = "";
      recognition.lang = "en-US";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      updateButton(button, true);
      showMessage(form, "Listening… tap the microphone again when you finish.");
      if (navigator.vibrate) { try { navigator.vibrate(20); } catch (e) {} }

      recognition.onresult = function (event) {
        interimTranscript = "";
        for (var i = event.resultIndex; i < event.results.length; i++) {
          var part = event.results[i][0] && event.results[i][0].transcript || "";
          if (event.results[i].isFinal) finalTranscript += part + " ";
          else interimTranscript += part;
        }
        var live = (finalTranscript + interimTranscript).trim();
        if (live) {
          input.value = live;
          input.dispatchEvent(new Event("input", { bubbles: true }));
        }
      };
      recognition.onerror = function (event) {
        var messages = {
          "not-allowed": "Microphone permission was denied. Allow microphone access in your browser settings.",
          "service-not-allowed": "The browser speech service is unavailable.",
          "no-speech": "No speech detected. Please try again.",
          "audio-capture": "No microphone was found. Check your device microphone."
        };
        showMessage(form, messages[event.error] || ("Voice input error: " + event.error));
      };
      recognition.onend = function () {
        if (activeRecognition === recognition) {
          finishRecognition(button, input, form);
        }
      };
      recognition.start();
    } catch (err) {
      updateButton(button, false);
      activeRecognition = null;
      activeButton = null;
      showMessage(form, "Could not start the microphone. Check browser permissions and try again.");
    }
  }
  function stopRecording() {
    if (!activeRecognition) return;
    var rec = activeRecognition;
    try { rec.stop(); } catch (e) {}
  }

  function bindMic(button) {
    if (button.dataset.voiceBound === "1") return;
    button.dataset.voiceBound = "1";
    button.addEventListener("click", function () {
      if (activeRecognition && activeButton === button) stopRecording();
      else {
        if (activeRecognition) stopRecording();
        startRecording(button);
      }
    });
  }

  function speak(text) {
    if (!voiceOn || !speechSynthesisAvailable()) return;
    try {
      window.speechSynthesis.cancel();
      var utterance = new SpeechSynthesisUtterance(String(text || "").replace(/\s+/g, " ").trim().slice(0, 900));
      utterance.lang = "en-US";
      utterance.rate = 1;
      window.speechSynthesis.speak(utterance);
    } catch (e) {}
  }
  function bindSpeaker(button) {
    if (button.dataset.voiceBound === "1") return;
    button.dataset.voiceBound = "1";
    button.addEventListener("click", function () {
      voiceOn = !voiceOn;
      try { localStorage.setItem(VOICE_PREF, voiceOn ? "1" : "0"); } catch (e) {}
      button.setAttribute("aria-pressed", voiceOn ? "true" : "false");
      button.classList.toggle("on", voiceOn);
      button.textContent = voiceOn ? "🔊" : "🔈";
      button.title = voiceOn ? "Voice replies on" : "Voice replies off";
      if (!voiceOn && speechSynthesisAvailable()) window.speechSynthesis.cancel();
    });
    button.setAttribute("aria-pressed", voiceOn ? "true" : "false");
    button.classList.toggle("on", voiceOn);
    button.textContent = voiceOn ? "🔊" : "🔈";
  }

  function scanReplies(root) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll(".cl-ai-message.bot, .tutor-msg.bot, .chat-msg.bot").forEach(function (node) {
      if (node.dataset.voiceScanned === "1") return;
      node.dataset.voiceScanned = "1";
      if (voiceOn) speak(node.textContent);
    });
  }
  function wire(root) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll("[data-mic-btn]").forEach(bindMic);
    root.querySelectorAll("[data-voice-toggle]").forEach(bindSpeaker);
  }

  wire(document);
  scanReplies(document);
  if (window.MutationObserver && document.body) {
    new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        mutation.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          wire(node);
          scanReplies(node);
        });
      });
    }).observe(document.body, { childList: true, subtree: true });
  }
})();
