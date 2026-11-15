// CyberLord voice input and spoken replies.
// Speech playback fires ONLY when the user clicks a soundbar / Listen
// control. Nothing on this page speaks on load, on message render, or
// on arrival of a reply. There is no autoplay path.
(function () {
  "use strict";

  var activeRecognition = null;
  var activeButton = null;
  var activeForm = null;
  var activeInput = null;
  var finalTranscript = "";
  var interimTranscript = "";
  var recognitionError = "";
  var manuallyStopped = false;

  function recognitionConstructor() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }
  function speechSynthesisAvailable() {
    return "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  }
  function getInput(button) {
    var form = button && button.closest("form");
    return form ? form.querySelector("input:not([type='submit']):not([type='button']), textarea") : null;
  }
  function statusNode(form) {
    if (!form) return null;
    var parent = form.parentNode || form;
    var status = parent.querySelector(":scope > .voice-status");
    if (!status) {
      status = document.createElement("small");
      status.className = "voice-status";
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      parent.insertBefore(status, form.nextSibling);
    }
    return status;
  }
  function showMessage(form, message) {
    var status = statusNode(form);
    if (status) status.textContent = message || "";
  }
  function setButton(button, listening) {
    if (!button) return;
    button.classList.toggle("listening", listening);
    button.setAttribute("aria-pressed", listening ? "true" : "false");
    button.textContent = listening ? "■" : "🎙";
    button.setAttribute("aria-label", listening ? "Stop voice recording" : "Start voice input");
    button.title = listening ? "Tap to stop recording" : "Tap to start voice input";
  }
  function clearActive() {
    setButton(activeButton, false);
    activeRecognition = null;
    activeButton = null;
    activeForm = null;
    activeInput = null;
  }
  function finishRecognition(recognition) {
    if (recognition !== activeRecognition) return;
    var form = activeForm;
    var input = activeInput;
    var transcript = (finalTranscript + " " + interimTranscript).trim();
    var error = recognitionError;
    clearActive();

    if (error) {
      showMessage(form, error);
      return;
    }
    if (transcript && input) {
      input.value = transcript;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      showMessage(form, "Speech converted to text. Review it, then press Send.");
    } else if (manuallyStopped) {
      showMessage(form, "Recording stopped, but no words were captured. Check microphone access and try again.");
    } else {
      showMessage(form, "No speech was detected. Tap the microphone, wait for Listening, then speak clearly.");
    }
  }
  function startRecording(button) {
    var Ctor = recognitionConstructor();
    var form = button.closest("form");
    var input = getInput(button);
    if (!window.isSecureContext) {
      showMessage(form, "Voice input requires a secure HTTPS connection. Open the HTTPS version of CyberLord.");
      return;
    }
    if (!Ctor) {
      showMessage(form, "This browser does not support speech recognition. Open CyberLord in Google Chrome and try again.");
      return;
    }
    if (!input) {
      showMessage(form, "Could not find the message box for voice input. Reload the page and try again.");
      return;
    }

    var recognition;
    try {
      recognition = new Ctor();
      activeRecognition = recognition;
      activeButton = button;
      activeForm = form;
      activeInput = input;
      finalTranscript = "";
      interimTranscript = "";
      recognitionError = "";
      manuallyStopped = false;

      recognition.lang = "en-NG";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      setButton(button, true);
      showMessage(form, "Starting microphone…");
      recognition.onstart = function () {
        if (activeRecognition === recognition) showMessage(form, "Listening… speak now. Tap the microphone again to stop.");
      };
      recognition.onresult = function (event) {
        if (activeRecognition !== recognition) return;
        interimTranscript = "";
        for (var i = event.resultIndex; i < event.results.length; i++) {
          var result = event.results[i];
          var phrase = result[0] ? result[0].transcript : "";
          if (result.isFinal) finalTranscript += phrase + " ";
          else interimTranscript += phrase;
        }
        var liveText = (finalTranscript + " " + interimTranscript).trim();
        if (liveText) {
          input.value = liveText;
          input.dispatchEvent(new Event("input", { bubbles: true }));
          showMessage(form, "Hearing you… tap the microphone again when finished.");
        }
      };
      recognition.onerror = function (event) {
        var errors = {
          "not-allowed": "Microphone permission is blocked. Allow microphone access for Chrome and this website.",
          "service-not-allowed": "The browser's speech-recognition service is unavailable. Try again in Google Chrome.",
          "no-speech": "No speech was detected. Check that the microphone is allowed, then try speaking again.",
          "audio-capture": "The browser cannot access a microphone. Check your phone's microphone permission.",
          "network": "Speech recognition could not connect to the browser's speech service. Check your internet connection and try again.",
          "aborted": "Recording was cancelled."
        };
        recognitionError = errors[event.error] || ("Speech recognition error: " + (event.error || "unknown error") + ".");
        if (activeRecognition === recognition) showMessage(form, recognitionError);
      };
      recognition.onend = function () { finishRecognition(recognition); };
      recognition.start();
    } catch (err) {
      if (recognition && activeRecognition === recognition) clearActive();
      else setButton(button, false);
      var reason = err && err.name === "NotAllowedError"
        ? "Microphone permission was denied. Allow microphone access in Chrome settings."
        : "The microphone could not start. Check site microphone permission, then reload CyberLord.";
      showMessage(form, reason);
    }
  }
  function stopRecording() {
    if (!activeRecognition) return;
    manuallyStopped = true;
    showMessage(activeForm, "Stopping recording…");
    try { activeRecognition.stop(); }
    catch (e) { finishRecognition(activeRecognition); }
  }
  function bindMic(button) {
    if (button.dataset.voiceBound === "1") return;
    button.dataset.voiceBound = "1";
    button.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      if (activeRecognition && activeButton === button) stopRecording();
      else {
        if (activeRecognition) stopRecording();
        startRecording(button);
      }
    });
  }
  // Playback only: reads the tapped message when the Listen / soundbar
  // control is clicked. Called from the click handler below and from
  // nothing else in this file.
  function speak(text) {
    if (!speechSynthesisAvailable()) return;
    try {
      window.speechSynthesis.cancel();
      var utterance = new SpeechSynthesisUtterance(String(text || "").replace(/\s+/g, " ").trim().slice(0, 900));
      utterance.lang = "en-US";
      utterance.rate = 1;
      window.speechSynthesis.speak(utterance);
    } catch (e) {}
  }
  function stopSpeech() {
    if (speechSynthesisAvailable()) {
      try { window.speechSynthesis.cancel(); } catch (e) {}
    }
  }
  // The soundbar control is a Listen button for the latest AI reply in
  // the same panel. Clicking it reads that reply aloud. Nothing speaks
  // until it is clicked, and there is no toggle that turns speech on
  // for future messages.
  function bindSpeaker(button) {
    if (button.dataset.voiceBound === "1") return;
    button.dataset.voiceBound = "1";
    button.addEventListener("click", function (event) {
      event.preventDefault();
      if (speechSynthesisAvailable() && window.speechSynthesis.speaking) {
        stopSpeech();
        return;
      }
      var root = button.closest("section, aside, div") || document;
      var nodes = root.querySelectorAll(".cl-ai-message.bot, .tutor-msg.bot, .chat-msg.bot");
      var target = null;
      for (var i = nodes.length - 1; i >= 0; i--) {
        var text = (nodes[i].textContent || "").trim();
        if (text && text !== "Thinking…" && text !== "Searching CyberLord knowledge…") { target = text; break; }
      }
      if (target) speak(target);
    });
    button.setAttribute("aria-pressed", "false");
  }
  function wire(root) {
    if (!root || !root.querySelectorAll) return;
    if (root.matches && root.matches("[data-mic-btn]")) bindMic(root);
    if (root.matches && root.matches("[data-voice-toggle]")) bindSpeaker(root);
    root.querySelectorAll("[data-mic-btn]").forEach(bindMic);
    root.querySelectorAll("[data-voice-toggle]").forEach(bindSpeaker);
  }
  // Wire controls on load only. No reply scanning, no greeting playback,
  // no speech on render.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { wire(document); });
  } else {
    wire(document);
  }
  if (window.MutationObserver && document.body) {
    new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        mutation.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          wire(node);
        });
      });
    }).observe(document.body, { childList: true, subtree: true });
  }
})();
