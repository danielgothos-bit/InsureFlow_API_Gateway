from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ["id", "username", "email", "first_name", "last_name", "role", "id_asegurado", "id_perito",
                  "is_active", "date_joined"]
        read_only_fields = ["id", "date_joined"]


class RegistroClienteSerializer(serializers.Serializer):
    """Registro público de un cliente: crea su usuario (rol asegurado) y su ficha de asegurado."""

    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100)
    national_id = serializers.CharField(max_length=30)
    email = serializers.EmailField()
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True)
    direccion = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        if Usuario.objects.filter(email__iexact=value).exists() or Usuario.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este correo.")
        return value.lower()

    def validate_password(self, value):
        validate_password(value)
        return value


class UsuarioInternoSerializer(serializers.ModelSerializer):
    """Creación de usuarios internos por el administrador (gestor de seguros, perito, administrador)."""

    password = serializers.CharField(write_only=True)
    especialidad = serializers.ChoiceField(choices=["auto", "hogar", "vida"], required=False, write_only=True)
    zona = serializers.CharField(required=False, write_only=True)

    class Meta:
        model = Usuario
        fields = ["id", "username", "email", "first_name", "last_name", "role", "password", "especialidad", "zona", "id_perito"]
        read_only_fields = ["id", "id_perito"]

    def validate_role(self, value):
        if value == Usuario.ASEGURADO:
            raise serializers.ValidationError("Los clientes se registran desde el sitio público.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, data):
        if data.get("role") == Usuario.PERITO and not data.get("especialidad"):
            raise serializers.ValidationError({"especialidad": "Indica la especialidad del perito."})
        return data


class LoginSerializer(TokenObtainPairSerializer):
    """Permite entrar con el usuario o con el correo. El token incluye el rol."""

    def validate(self, attrs):
        login = attrs.get(self.username_field, "")
        usuario = Usuario.objects.filter(email__iexact=login).first()
        if usuario:
            attrs[self.username_field] = usuario.username
        return super().validate(attrs)

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
