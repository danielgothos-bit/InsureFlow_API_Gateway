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

# Rutas restringidas por rol. El control fino por objeto (cada asegurado solo ve lo suyo,
# cada perito solo sus inspecciones) está en permisos.py.
ROLES_PERMITIDOS = {
    "analitica": {"agente", "admin"},
}

# Rutas que se pueden usar sin iniciar sesión (sitio público: cotizar y ver productos).
RUTAS_PUBLICAS = {
    ("POST", "polizas/cotizar"),
    ("GET", "polizas/productos"),
}

# Rutas internas que nunca se exponen hacia afuera.
BLOQUEADAS = {"eventos"}
