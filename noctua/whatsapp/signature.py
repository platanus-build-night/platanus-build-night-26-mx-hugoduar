import hashlib
import hmac


def verify(raw_body: bytes, header_value: str, secret: str) -> bool:
    if not header_value or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_value)
