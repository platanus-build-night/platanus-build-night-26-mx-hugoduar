import hashlib
import hmac
from noctua.whatsapp.signature import verify


SECRET = "test-secret"
BODY = b'{"hello": "world"}'
EXPECTED = hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()


def test_verify_accepts_matching_signature():
    assert verify(BODY, EXPECTED, SECRET) is True


def test_verify_rejects_tampered_body():
    tampered = BODY + b" "
    assert verify(tampered, EXPECTED, SECRET) is False


def test_verify_rejects_bad_signature():
    assert verify(BODY, "deadbeef", SECRET) is False


def test_verify_rejects_empty_header():
    assert verify(BODY, "", SECRET) is False


def test_verify_rejects_empty_secret():
    assert verify(BODY, EXPECTED, "") is False
