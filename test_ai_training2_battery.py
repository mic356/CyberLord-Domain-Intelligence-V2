#!/usr/bin/env python3
"""ai-training-2 battery: 150+ questions against the built-in brain (cyberlord_ai.answer)
plus the route-level helpers in app.py. Run: python3 test_ai_training2_battery.py [--tag NAME]

Checks classify each reply: OK (real answer), REDIRECT (tutor redirect), DONTKNOW,
OFFTOPIC-REDIR (tutor clever redirect), TIME-FAIL/WEATHER-FAIL/etc.
"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for k in ("GEMINI_API_KEY", "GROQ_API_KEY"):
    os.environ.pop(k, None)

import cyberlord_ai as ai

DONTKNOW = "honestly, i don't know"
REDIRECT = "that is one for the tutor"
TUTOR_REDIR = "nice question, i like the curiosity"

def classify(rep):
    low = (rep or "").lower()
    if "honestly, i don't know" in low or "i don't know that one" in low:
        return "DONTKNOW"
    if "that is one for the tutor" in low:
        return "REDIRECT"
    if "nice question, i like the curiosity" in low:
        return "TUTOR_REDIR"
    if "i couldn't reach" in low or "couldn't reach" in low:
        return "LIVE-UNREACHABLE"
    return "OK"

# (question, persona, expect) expect in: ok, redirect, dontknow, tutorredir, time, weather, news, images
CASES = []
def add(q, persona, expect):
    CASES.append((q, persona, expect))

# --- time (12) ---
for q in ["what time is it", "what's the time now", "current time please", "what is the time",
          "what day is it", "what date is today", "what is today's date", "tell me the time",
          "time is what now", "what's today's date", "current day and time", "what time is it now in lagos"]:
    add(q, "main", "time")

# --- weather (22) ---
for q in ["what's the weather in lagos today", "what is the weather today", "weather in lagos",
          "how is the weather in nigeria today", "will it rain in lagos today", "is it raining in abuja",
          "what's the temperature in lagos", "how hot is it in lagos today", "weather forecast for lagos",
          "what will the weather be like tomorrow in lagos", "is it sunny in lagos today",
          "weather in london today", "weather in abuja today", "weather in port harcourt",
          "weather in kano today", "weather in ibadan", "weather in calabar", "weather in jos today",
          "weather in maiduguri", "weather in nyc today", "weather in accra today", "weather in nairobi"]:
    add(q, "main", "weather")

# --- news (18) ---
for q in ["what's the latest news", "latest news in nigeria today", "top headlines today",
          "any news today", "what is happening in nigeria", "latest football news",
          "news headlines today", "what's in the news today", "breaking news today",
          "latest news in lagos", "world news today", "latest sports news", "nigeria news latest",
          "what happened today in nigeria", "latest tech news", "nigeria headlines",
          "any trending news", "news today"]:
    add(q, "main", "news")

# --- general knowledge (35) ---
for q in ["what is the capital of france", "who wrote hamlet", "what is photosynthesis",
          "how many continents are there", "what is the largest planet", "who painted the mona lisa",
          "what is the boiling point of water", "how many days are in a leap year",
          "what is the speed of light", "who was the first president of nigeria",
          "what is the currency of japan", "how tall is the eiffel tower",
          "what does DNA stand for", "what is the powerhouse of the cell",
          "who invented the telephone", "what is the main ingredient in guacamole",
          "how many sides does a hexagon have", "what gas do plants absorb",
          "what is the longest river in the world", "who discovered penicillin",
          "what is the capital of the usa", "what is 15 percent of 200",
          "how many minutes are in 3 hours", "what is the square root of 144",
          "what year did man land on the moon", "who wrote the nigerian national anthem",
          "what is the largest ocean on earth", "what language is spoken in brazil",
          "how many legs does a spider have", "what is the freezing point of water in celsius",
          "who is the richest man in the world currently", "what is the most spoken language in the world",
          "what is the chemical symbol for gold", "how many states are in nigeria",
          "what is the tallest mountain in africa"]:
    add(q, "main", "ok")

# --- how-to / advice (24) ---
for q in ["how do i bake a cake", "how do i boil yam", "how to tie a tie",
          "how can i improve my memory", "how do i learn python", "how to make money online",
          "how do i stay productive", "how to write a good cv", "how do i make jollof rice",
          "how to save money each month", "how do i start a business in nigeria",
          "how to learn the piano", "how do i improve my english", "how to cook fried rice",
          "how do i get a good night sleep", "how to take better photos with my phone",
          "how do i start exercising", "how to plan a birthday party",
          "how do i fix a flat tire", "how to change a car tire", "how do i learn to swim",
          "how to make homemade pizza", "how do i budget my salary", "how to grow a small business"]:
    add(q, "main", "ok")

# --- site pricing / CyberLord info (14) ---
for q in ["how much does pro cost", "what is the price of pro plus", "how much is pro",
          "cyberlord pricing", "what is cyberlord", "what does cyberlord do",
          "how much is pro plus", "tell me about cyberlord plans", "cyberlord free plan",
          "how do i pay for pro", "pro price", "cost of pro plus", "cyberlord features",
          "deep scan on cyberlord"]:
    add(q, "main", "ok")

# --- cyber redirect (20) ---
for q in ["what is nmap", "explain phishing to me", "how does sql injection work",
          "what is a vulnerability", "what is owasp top 10", "how to use wireshark",
          "what is malware", "what is ransomware", "explain social engineering",
          "what is a firewall", "how do i hack a system", "what is kali linux",
          "what is penetration testing", "what is a cve", "explain cryptography",
          "how does dns work", "what is tcp", "what is xss", "what is ddof attack",
          "what is a botnet"]:
    add(q, "main", "redirect")

# --- tutor off-topic / weather (8) ---
for q in ["what's the weather in lagos", "tell me a joke please", "what is the capital of france",
          "latest football scores", "how do i bake a cake", "what is the weather today",
          "who won the last match", "what's in the news today"]:
    add(q, "tutor", "tutorredir")

# --- images (12) ---
for q in ["show me pictures of lagos", "show me a picture of the eiffel tower",
          "show me images of cats", "pictures of paris please", "show me a picture of a lion",
          "find me pictures of dogs", "images of the eiffel tower please",
          "show me photos of lagos", "i want pictures of paris",
          "show me images of elephants", "pictures of mountains please", "show me a photo of a cat"]:
    add(q, "main", "images")

# --- typos (12) --- cyber typos redirect by the intact rule; weather/news/time OK; puctures -> images
for q in ["what is phising", "what is malwere", "how does phishng work",
          "what is ransomeware", "what is namp", "what is vurnerability"]:
    add(q, "main", "redirect")
for q in ["wether in lagos today", "wheather in abuja",
          "newz headlines today", "what time is ti now", "how much does pro costt"]:
    add(q, "main", "ok")
add("show me puctures of cats", "main", "images")

# --- small talk / misc (10) ---
for q in ["hi", "hello there", "good morning", "how are you", "thank you so much",
          "tell me a joke", "help me write an email", "what can you do",
          "who made you", "are you a robot"]:
    add(q, "main", "ok")

def main():
    tag = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--tag" else "run"
    answer = ai.answer
    results = []
    for q, persona, expect in CASES:
        lesson = {"slug": "test-lesson", "title": "Cybersecurity Foundations",
                  "desc": "Intro to cyber basics.", "content": ["cia triad"],
                  "questions": [{"question": "What is the CIA triad?", "choices": ["a", "b"], "answer": 0, "explain": "x"}]}
        rep = answer(q, [], persona=persona, lesson=lesson if persona == "tutor" else None)
        cls = classify(rep)
        low = rep.lower()
        ok = False
        detail = cls
        if expect == "ok":
            ok = cls == "OK" and len(rep) > 40
        elif expect == "redirect":
            ok = cls == "REDIRECT"
        elif expect == "tutorredir":
            ok = cls == "TUTOR_REDIR"
        elif expect == "time":
            ok = bool(re.search(r"\d{1,2}:\d{2}\s*(am|pm)", low)) and ("lagos" in low or "today" in low)
            detail = cls + ("+TIMEOK" if ok else "+TIMEFAIL")
        elif expect == "weather":
            ok = cls in ("OK",) and ("lagos" in low or "°c" in low or "weather" in low) and len(rep) > 30
            detail = cls + ("+WXOK" if ok else "+WXFAIL")
        elif expect == "news":
            ok = cls == "OK" and len(rep) > 40
            detail = cls + ("+NEWSOK" if ok else "+NEWSFAIL")
        elif expect == "images":
            ok = ("http" in low and ("wikimedia" in low or "wikipedia" in low or "upload.wikimedia" in low)) or ("see image" in low and "http" in low)
            detail = cls + ("+IMGOK" if ok else "+IMGFAIL")
        results.append({"q": q, "persona": persona, "expect": expect, "cls": cls, "ok": ok,
                        "reply": rep[:220]})
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    from collections import Counter
    by_expect = Counter((r["expect"], r["cls"]) for r in results)
    fails = [r for r in results if not r["ok"]]
    print(f"BATTERY {tag}: {passed}/{total} passed")
    print("by class:", dict(by_expect))
    print(f"FAILURES ({len(fails)}):")
    for f in fails:
        print(f"  [{f['expect']}/{f['cls']}] ({f['persona']}) {f['q']!r} -> {f['reply'][:140]!r}")
    json.dump(results, open(f"/tmp/battery_{tag}.json", "w"), indent=1)
    return 0

if __name__ == "__main__":
    sys.exit(main())
