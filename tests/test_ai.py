# tests/test_ai.py — Lab 5, Task D: the failure policy is tested in CI, with NO key and
# NO network. httpx2.MockTransport plays the AI provider; we decide what it answers.
import httpx2
import pytest

from app import ai

OK_BODY = {"choices": [{"message": {"content": "A short summary."}, "finish_reason": "stop"}]}


def fake_provider(*statuses):
    """A client whose provider answers with the given status codes, in order."""
    calls = []

    def handler(request):
        calls.append(request)
        status = statuses[min(len(calls), len(statuses)) - 1]
        return httpx2.Response(status, json=OK_BODY if status == 200 else {"error": "x"})

    return httpx2.Client(transport=httpx2.MockTransport(handler)), calls


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")


def test_summary_ok_and_key_only_in_header():
    client, calls = fake_provider(200)
    assert ai.summarize_safe("some text", client) == "A short summary."
    assert calls[0].headers["authorization"] == "Bearer test-key-not-real"
    assert "test-key-not-real" not in str(calls[0].url)  # never in the URL


def test_429_is_retried_with_backoff():
    client, calls = fake_provider(429, 429, 200)
    waits = []
    assert ai.summarize_safe("text", client, sleep=waits.append) == "A short summary."
    assert len(calls) == 3
    assert waits == [1, 2]  # 1 s, then 2 s


def test_bad_key_is_not_retried():
    client, calls = fake_provider(403)
    with pytest.raises(ai.AIUnavailable):
        ai.summarize_safe("text", client, sleep=lambda s: None)
    assert len(calls) == 1  # a bad key never becomes good


def test_timeout_gives_up_cleanly():
    def handler(request):
        raise httpx2.ReadTimeout("slow", request=request)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    with pytest.raises(ai.AIUnavailable):
        ai.summarize_safe("text", client)


def test_empty_answer_is_a_failure():
    empty = {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}
    transport = httpx2.MockTransport(lambda r: httpx2.Response(200, json=empty))
    client = httpx2.Client(transport=transport)
    with pytest.raises(ai.AIUnavailable):
        ai.summarize_safe("text", client)


def test_missing_key_is_a_failure_not_a_crash(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(ai.AIUnavailable):
        ai.summarize_safe("text")


def test_input_is_capped():
    client, calls = fake_provider(200)
    ai.summarize_safe("x" * 50_000, client)
    assert len(calls[0].content) < 10_000
