"""
Tabla de enrutamiento del API Gateway: primer segmento de la ruta -> microservicio.

La URL de cada microservicio se configura con <SERVICIO>_SERVICE_URL, por ejemplo
CLAIMS_SERVICE_URL=https://claims-service-xxxx.onrender.com
"""
RUTAS = {
    "asegurados": "POLICYHOLDER",
    "polizas": "POLICY",
    "siniestros": "CLAIMS",
    "peritos": "ADJUSTER",
    "inspecciones": "ADJUSTER",
    "pagos": "PAYMENT",
    "documentos": "DOCUMENT",
    "notificaciones": "NOTIFICATION",
    "analitica": "ANALYTICS",
}

# Rutas restringidas por rol (las demás las puede usar cualquier usuario autenticado).
ROLES_PERMITIDOS = {
    "analitica": {"agente", "admin"},
    "peritos": {"agente", "perito", "admin"},
    "inspecciones": {"agente", "perito", "admin"},
}

# Rutas internas que nunca se exponen hacia afuera.
BLOQUEADAS = {"eventos"}
