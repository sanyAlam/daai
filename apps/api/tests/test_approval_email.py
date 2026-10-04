from __future__ import annotations

from app.approval_email import ResendApprovalEmailProvider


class _FakeResponse:
    status = 200

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_resend_provider_sets_required_headers(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        captured["request"] = req
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr("app.approval_email.urllib_request.urlopen", fake_urlopen)

    provider = ResendApprovalEmailProvider(
        api_key="test-resend-api-key",
        from_email="no-reply@example.com",
    )

    provider.send(
        recipient="approver@example.com",
        subject="Approval needed",
        body="Please review this action.",
    )

    request = captured["request"]
    assert request.get_header("Authorization") == "Bearer test-resend-api-key"
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("User-agent") == "DAAI-Console/0.1"
    assert captured["timeout"] == 10
