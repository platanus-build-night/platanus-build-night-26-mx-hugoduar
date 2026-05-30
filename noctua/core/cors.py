from django.conf import settings
from django.http import HttpResponse


class CorsMiddleware:
    """Allow the local Next.js dev UI (and any configured origin) to call the API.

    Pure stdlib; no extra deps. Only meant for trusted dev/internal origins —
    `NOCTUA_CORS_ALLOWED_ORIGINS` should be an explicit allowlist, never `*`
    when the API uses bearer auth.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        configured = getattr(settings, "NOCTUA_CORS_ALLOWED_ORIGINS", None)
        if configured is None:
            configured = "http://localhost:3000,http://127.0.0.1:3000"
        self.allowed = {o.strip() for o in configured.split(",") if o.strip()}

    def __call__(self, request):
        origin = request.META.get("HTTP_ORIGIN")
        if request.method == "OPTIONS" and origin in self.allowed:
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)
        if origin in self.allowed:
            response["Access-Control-Allow-Origin"] = origin
            response["Vary"] = "Origin"
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response["Access-Control-Max-Age"] = "600"
        return response
