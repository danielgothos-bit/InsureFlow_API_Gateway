from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from proxy.servicios import ServicioError, llamar

from .models import Usuario
from .serializers import LoginSerializer, RegistroClienteSerializer, UsuarioInternoSerializer, UsuarioSerializer


class EsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == Usuario.ADMIN)


def _error_servicio(exc):
    data = exc.data if isinstance(exc.data, dict) else {"code": "ERROR", "message": "No se pudo completar el registro."}
    return Response(data, status=exc.status if exc.status < 500 else status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(["POST"])
@permission_classes([AllowAny])
def registro(request):
    """Registro de clientes: crea la ficha en el microservicio de Asegurados y el usuario vinculado."""
    serializer = RegistroClienteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    datos = serializer.validated_data

    try:
        asegurado = llamar("POLICYHOLDER", "POST", "/api/v1/asegurados", json={
            k: datos.get(k, "") for k in ("nombre", "apellido", "national_id", "email", "telefono", "direccion")
        })
    except ServicioError as exc:
        return _error_servicio(exc)

    usuario = Usuario.objects.create_user(
        username=datos["email"], email=datos["email"], password=datos["password"],
        first_name=datos["nombre"], last_name=datos["apellido"],
        role=Usuario.ASEGURADO, id_asegurado=asegurado["id_asegurado"],
    )
    return Response(UsuarioSerializer(usuario).data, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


@api_view(["GET"])
def yo(request):
    return Response(UsuarioSerializer(request.user).data)


@api_view(["GET", "POST"])
@permission_classes([EsAdmin])
def usuarios(request):
    """Administración de usuarios internos (solo administrador)."""
    if request.method == "GET":
        qs = Usuario.objects.order_by("role", "username")
        if request.query_params.get("role"):
            qs = qs.filter(role=request.query_params["role"])
        return Response(UsuarioSerializer(qs, many=True).data)

    serializer = UsuarioInternoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    datos = dict(serializer.validated_data)
    especialidad, zona = datos.pop("especialidad", None), datos.pop("zona", "")

    with transaction.atomic():
        if datos["role"] == Usuario.PERITO:
            try:
                perito = llamar("ADJUSTER", "POST", "/api/v1/peritos", json={
                    "nombre": f"{datos.get('first_name', '')} {datos.get('last_name', '')}".strip() or datos["username"],
                    "especialidad": especialidad, "zona": zona or "General",
                })
            except ServicioError as exc:
                return _error_servicio(exc)
            datos["id_perito"] = perito["id_perito"]
        usuario = Usuario.objects.create_user(**datos)
    return Response(UsuarioSerializer(usuario).data, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes([EsAdmin])
def usuario_detalle(request, id):
    usuario = get_object_or_404(Usuario, id=id)
    if usuario == request.user and request.data.get("is_active") is False:
        return Response({"code": "CONFLICT", "message": "No puedes desactivar tu propia cuenta."}, status=status.HTTP_409_CONFLICT)
    if "is_active" in request.data:
        usuario.is_active = bool(request.data["is_active"])
    usuario.save()
    return Response(UsuarioSerializer(usuario).data)
