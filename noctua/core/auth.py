from django.conf import settings
from ninja.security import HttpBearer


class BearerAuth(HttpBearer):
    def authenticate(self, request, token):
        if settings.NOCTUA_API_TOKEN and token == settings.NOCTUA_API_TOKEN:
            return token
        return None
