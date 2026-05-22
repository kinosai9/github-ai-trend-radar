from github_ai_trend_radar.push.pushplus import PushPlusConfig, send_pushplus


class FakeResponse:
    def __init__(self, status_code=200, text='{"code":200}'):
        self.status_code = status_code
        self.text = text
        self.ok = 200 <= status_code < 300


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_missing_token_skips_without_api_call():
    session = FakeSession(FakeResponse())

    result = send_pushplus(title="t", content="c", config=PushPlusConfig(token=""), session=session)

    assert result.skipped is True
    assert session.calls == []


def test_api_failure_returns_not_ok_by_default():
    session = FakeSession(FakeResponse(500, "server error"))

    result = send_pushplus(title="t", content="c", config=PushPlusConfig(token="token", retries=0), session=session)

    assert result.ok is False
    assert result.skipped is False
    assert "HTTP 500" in result.error


def test_success_sends_expected_payload():
    session = FakeSession(FakeResponse(200, "ok"))

    result = send_pushplus(
        title="title",
        content="<p>content</p>",
        config=PushPlusConfig(token="token", topic="topic", channel="channel", webhook="webhook"),
        session=session,
    )

    assert result.ok is True
    payload = session.calls[0][1]["json"]
    assert payload["token"] == "token"
    assert payload["template"] == "html"
    assert payload["topic"] == "topic"
    assert payload["channel"] == "channel"
    assert payload["webhook"] == "webhook"
