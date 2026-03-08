import hashlib
import hmac
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from conductor.adapters.linear.signature import verify_linear_signature
from conductor.api.webhook import app


def make_signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ------------------------------------------------------------------
# Pure function tests
# ------------------------------------------------------------------


def test_valid_signature_returns_true():
    body = b'{"action": "create"}'
    secret = "my-secret"
    sig = make_signature(body, secret)
    assert verify_linear_signature(body, sig, secret) is True


def test_tampered_body_returns_false():
    body = b'{"action": "create"}'
    secret = "my-secret"
    sig = make_signature(body, secret)
    assert verify_linear_signature(b'{"action": "delete"}', sig, secret) is False


def test_wrong_secret_returns_false():
    body = b'{"action": "create"}'
    sig = make_signature(body, "correct-secret")
    assert verify_linear_signature(body, sig, "wrong-secret") is False


def test_empty_body_valid():
    body = b""
    secret = "s"
    sig = make_signature(body, secret)
    assert verify_linear_signature(body, sig, secret) is True


# ------------------------------------------------------------------
# Integration tests via FastAPI TestClient
# ------------------------------------------------------------------


def test_linear_webhook_rejects_missing_signature():
    with patch("conductor.api.webhook.settings") as mock_settings:
        mock_settings.linear_webhook_secret = "my-secret"
        client = TestClient(app)
        resp = client.post("/webhook/linear", json={"action": "create"})
    assert resp.status_code == 401
    assert "Missing" in resp.json()["detail"]


def test_linear_webhook_rejects_bad_signature():
    with patch("conductor.api.webhook.settings") as mock_settings:
        mock_settings.linear_webhook_secret = "my-secret"
        client = TestClient(app)
        resp = client.post(
            "/webhook/linear",
            json={"action": "create"},
            headers={"Linear-Signature": "deadbeef"},
        )
    assert resp.status_code == 401
    assert "Invalid" in resp.json()["detail"]


def test_linear_webhook_accepts_valid_signature():
    secret = "my-secret"
    payload = {"action": "create"}
    body = json.dumps(payload).encode()
    sig = make_signature(body, secret)

    with patch("conductor.api.webhook.settings") as mock_settings:
        mock_settings.linear_webhook_secret = secret
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/webhook/linear",
            content=body,
            headers={"Content-Type": "application/json", "Linear-Signature": sig},
        )
    # 404 because no adapter registered — but signature passed
    assert resp.status_code == 404


def test_linear_webhook_skips_verification_when_no_secret():
    with patch("conductor.api.webhook.settings") as mock_settings:
        mock_settings.linear_webhook_secret = ""
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/webhook/linear", json={"action": "create"})
    # 404 because no adapter registered — but no 401
    assert resp.status_code == 404
