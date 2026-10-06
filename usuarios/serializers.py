from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ["id", "username", "email", "first_name", "last_name", "role", "id_asegurado", "id_perito"]
        read_only_fields = ["id"]


class RegistroSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Usuario
        fields = ["id", "username", "email", "password", "first_name", "last_name", "role", "id_asegurado", "id_perito"]
        read_only_fields = ["id"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_role(self, value):
        # Solo un administrador puede crear agentes, peritos u otros administradores.
        usuario = self.context["request"].user
        es_admin = getattr(usuario, "is_authenticated", False) and usuario.role == Usuario.ADMIN
        if value != Usuario.ASEGURADO and not es_admin:
            raise serializers.ValidationError("Solo un administrador puede asignar ese rol.")
        return value

    def create(self, validated_data):
        return Usuario.objects.create_user(**validated_data)


class LoginSerializer(TokenObtainPairSerializer):
    """El token incluye el rol y los vínculos del usuario."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["username"] = user.username
        if user.id_asegurado:
            token["id_asegurado"] = str(user.id_asegurado)
        if user.id_perito:
            token["id_perito"] = str(user.id_perito)
        return token
