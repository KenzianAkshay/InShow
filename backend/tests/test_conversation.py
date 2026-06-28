from app.conversation import detect_social, social_reply


def test_detect_greetings():
    for m in ["hi", "Hello!", "hey there", "good morning", "yo", "what's up?"]:
        assert detect_social(m) == "greeting", m


def test_detect_other_social():
    assert detect_social("thanks a lot") == "thanks"
    assert detect_social("how are you?") == "howareyou"
    assert detect_social("bye") == "farewell"
    assert detect_social("see you later") == "farewell"


def test_not_social_false_positives():
    # words that merely start with greeting letters must NOT be greetings
    assert detect_social("hide the storage") is None
    assert detect_social("history of the project") is None
    # real analytic requests are not small talk
    assert detect_social("how many exhibitors are there") is None
    assert detect_social("chart exhibitors by city") is None
    # long messages are treated as real requests
    assert detect_social("hi can you please chart exhibitors by city for me") is None
    assert detect_social("") is None


def test_social_reply_text():
    assert "Hello" in social_reply("hi")
    assert "welcome" in social_reply("thanks").lower()
    assert social_reply("chart it") is None
    # booth flavour invites booth details
    booth = social_reply("hello", booth=True)
    assert "booth" in booth.lower() or "stand" in booth.lower()
