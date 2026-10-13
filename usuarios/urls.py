from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("api/v1/auth/registro", views.registro),
    path("api/v1/auth/login", views.LoginView.as_view()),
    path("api/v1/auth/refresh", TokenRefreshView.as_view()),
    path("api/v1/auth/me", views.yo),
    path("api/v1/auth/usuarios", views.usuarios),
    path("api/v1/auth/usuarios/<uuid:id>", views.usuario_detalle),
]
