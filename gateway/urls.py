from django.urls import include, path

from proxy.views import ProxyView, health, health_servicios, inicio

urlpatterns = [
    path("", inicio),
    path("health", health),
    path("health/servicios", health_servicios),
    path("", include("usuarios.urls")),
    # Todo lo demás bajo /api/v1/ se reenvía al microservicio correspondiente.
    path("api/v1/<path:ruta>", ProxyView.as_view()),
]
