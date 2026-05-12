"""
Configuración para PythonAnywhere (producción).
Importa todo de settings.py base y sobreescribe lo necesario.
"""
from .settings import *

# Cambia esto por tu usuario de PythonAnywhere
PYTHONANYWHERE_USER = 'TUUSUARIO'

ALLOWED_HOSTS = [
    f'{PYTHONANYWHERE_USER}.pythonanywhere.com',
]

DEBUG = False

# Archivos estáticos en PythonAnywhere
STATIC_ROOT = f'/home/{PYTHONANYWHERE_USER}/SimuladorCCFA/staticfiles'
