"""Topics learned by the daily trainer (train_daily.py).

Each entry is (keyword phrase, answer body) and is merged into the
built-in brain in cyberlord_ai.py at import time. The main persona
checks these after the built-in knowledge topics, so learned topics
fill gaps (questions that fell back to "I don't know") without
overriding existing knowledge. Never put secrets, personal data or
time-sensitive figures (prices, news) here; the trainer only adds
stable, general knowledge.
"""
LEARNED_TOPICS = [
]
