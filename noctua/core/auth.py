import hmac

from django.conf import settings
from ninja.security import HttpBearer


class BearerAuth(HttpBearer):
    def authenticate(self, request, token):
        configured = settings.NOCTUA_API_TOKEN
        if not configured:
            return None
        # Encode to bytes for compare_digest (and to dodge any unicode weirdness).
        if hmac.compare_digest(token.encode("utf-8"), configured.encode("utf-8")):
            return token
        return None
