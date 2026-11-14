"""100+ question battery for Cyber (main persona) after the brand + Toyota work.
Run: python3 test_brand_toyota.py [--tag x]
Covers brand questions, 40+ Toyota questions, and regression areas
(pricing, weather, news, time, cyber redirect, typos, general knowledge).
"""
import sys
import cyberlord_ai as ai

# Each case: (question, must_contain list [ALL must appear], must_not list [ANY forbidden])
CASES = [
    # ---- brand (9) ----
    ("who are you", ["Cyber"], []),
    ("what is your name", ["Cyber"], []),
    ("tell me about yourself", ["Cyber"], []),
    ("who made you", ["Nozomio", "Cyber"], ["I am CyberLord's built-in assistant"]),
    ("what can i call you", ["Cyber"], []),
    ("are you a robot", ["Cyber"], []),
    ("are you human", ["Cyber"], []),
    ("hello", [], []),
    ("what is this site", ["CyberLord"], []),
    ("what is cyberlord", ["CyberLord"], []),
    ("what plans does cyberlord have", ["6,300", "12,600"], []),
    ("how much does pro cost", ["6,300"], []),
    ("how much does pro plus cost", ["12,600"], []),
    ("what is the pro plus price", ["12,600"], []),
    ("what is the pro price", ["6,300"], []),
    # ---- Toyota (45) ----
    ("what is toyota", ["Toyota Motor Corporation", "1937"], []),
    ("when was toyota founded", ["1937", "Kiichiro"], []),
    ("who founded toyota", ["Kiichiro"], []),
    ("toyota headquarters", ["Toyota City"], []),
    ("what does toyota mean", ["Toyoda"], []),
    ("toyota history", ["1937"], []),
    ("what is toyota corolla", ["Corolla", "1966"], []),
    ("when did corolla come out", ["1966"], []),
    ("best selling car of all time corolla", ["50 million"], []),
    ("toyota corolla generations", ["E120"], []),
    ("toyota corolla engine", ["1.8"], []),
    ("tell me about corolla", ["Corolla", "1966"], []),
    ("toyota camry", ["Camry", "1982"], []),
    ("when did camry launch", ["1982"], []),
    ("toyota camry engine", ["2.5"], []),
    ("what about the camry", ["Camry"], []),
    ("toyota hilux", ["Hilux", "1968"], []),
    ("when did hilux start", ["1968"], []),
    ("toyota hilux generations", ["Vigo", "Revo"], []),
    ("toyota hilux engine", ["2.4"], []),
    ("toyota hilux towing capacity", ["3,500"], []),
    ("toyota land cruiser", ["1951"], []),
    ("when did land cruiser come out", ["1951"], []),
    ("toyota land cruiser 300 series", ["2021"], []),
    ("toyota land cruiser prado", ["Prado", "250"], []),
    ("is land cruiser same as prado", ["No"], []),
    ("toyota rav4", ["1994"], []),
    ("when did rav4 come out", ["1994"], []),
    ("toyota rav4 hybrid", ["2.5"], []),
    ("toyota yaris", ["1999"], []),
    ("toyota yaris cross", ["2020"], []),
    ("toyota supra", ["2019"], []),
    ("toyota supra mk4 2jz", ["2JZ"], []),
    ("toyota prius", ["1997"], []),
    ("when did prius come out", ["1997"], []),
    ("how does prius hybrid work", ["battery"], []),
    ("toyota hybrid system", ["Atkinson"], []),
    ("toyota tnga", ["TNGA-C", "TNGA-F"], []),
    ("what is tnga platform toyota", ["Toyota New Global Architecture"], []),
    ("toyota lexus", ["1989"], []),
    ("toyota fortuner", ["2005"], []),
    ("toyota hilux common problems", ["2KD"], []),
    ("toyota corolla common problems", ["oil-consumption"], []),
    ("toyota corolla cvt problems", ["CVT fluid"], []),
    ("toyota maintenance schedule", ["5,000"], []),
    ("how often change toyota engine oil", ["5,000"], []),
    ("toyota nigeria", ["Toyota Nigeria"], []),
    ("toyota cars in nigeria", ["tokunbo"], []),
    ("toyota tokunbo", ["VIN"], []),
    ("how to check toyota vin", ["17"], []),
    ("toyota recall check", ["recalls"], []),
    ("does toyota make electric cars", ["bZ4X"], []),
    ("toyota vs honda", ["Toyota wins"], []),
    ("toyota vs lexus reliability", ["Lexus"], []),
    ("toyota full hybrid vs mild hybrid", ["full hybrids"], []),
    ("toyota cvt", ["CVT"], []),
    ("toyota warranty", ["3 years"], []),
    ("toyota price in nigeria", ["I don't know"], []),
    ("toyota corolla price nigeria", ["I don't know"], []),
    ("toyota hilux price nigeria", ["I don't know"], []),
    ("best toyota car to buy in nigeria", ["Corolla"], []),
    ("toyota engine 2zz", ["1.8"], []),
    ("toyota reliable car", ["reliability"], []),
    # ---- regression: cyber redirect (main persona) ----
    ("what is phishing", ["Academy tutor"], []),
    ("how do i hack wifi", ["Academy tutor"], []),
    ("what is malware", ["Academy tutor"], []),
    ("how to secure my network", ["Academy tutor"], []),
    # ---- regression: time / weather / news / general ----
    ("what time is it", ["Lagos"], []),
    ("what is the date today", ["2026"], []),
    ("what is the weather in lagos", [], []),
    ("any news today", [], []),
    ("what is the capital of france", ["Paris"], []),
    ("how do i learn python", [], []),
    ("what is photosynthesis", ["plants"], []),
    ("how does the internet work", [], []),
    # ---- typos ----
    ("who are yuo", ["Cyber"], []),
    ("what is toytoa", [], []),
    ("tell me about corrola", ["Corolla"], []),
    ("how much is pro", ["6,300"], []),
]


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "run"
    passed, failed = 0, []
    for q, must, must_not in CASES:
        r = ai.answer(q, [], persona="main")
        ok = bool(r) and all(m.lower() in r.lower() for m in must) \
            and not any(b.lower() in r.lower() for b in must_not)
        if ok:
            passed += 1
        else:
            failed.append((q, r[:160]))
    print(f"[{tag}] {passed}/{len(CASES)} passed")
    for q, r in failed:
        print("FAIL:", q, "->", r)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
