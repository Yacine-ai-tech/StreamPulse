"""WebhookReceiver HMAC verification tests (pure, offline)."""
import hashlib
import hmac
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from connectors.webhook_receiver import WebhookReceiver  # noqa: E402


def _sign(payload: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def test_valid_signature_passes():
    payload, secret = b'{"metric":"revenue","value":100}', "topsecret"
    assert WebhookReceiver.verify_signature(payload, _sign(payload, secret), secret=secret)


def test_tampered_payload_fails():
    secret = "topsecret"
    sig = _sign(b'{"value":100}', secret)
    assert not WebhookReceiver.verify_signature(b'{"value":999}', sig, secret=secret)


def test_missing_signature_fails():
    assert not WebhookReceiver.verify_signature(b"x", "", secret="topsecret")
