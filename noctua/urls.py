from django.urls import path
from noctua.core.api import api

urlpatterns = [
    path("api/", api.urls),
]
