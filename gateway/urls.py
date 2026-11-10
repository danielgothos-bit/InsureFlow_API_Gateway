from django.urls import include, path, re_path

from comun.metricas import metricas
from proxy.views import ProxyView, health, health_servicios, sitio

urlpatterns = [
    path("health", health),
    path("metrics", metricas),
    path("health/servicios", health_servicios),
    path("", include("usuarios.urls")),
    # Todo lo demás bajo /api/v1/ se reenvía al microservicio correspondiente.
    path("api/v1/<path:ruta>", ProxyView.as_view()),
    # Frontend (SPA): inicio, cotizador, portal del cliente y portal de gestión.
    re_path(r"^(?!api/|health|metrics|static/|assets/)(?P<ruta>.*)$", sitio),
]
