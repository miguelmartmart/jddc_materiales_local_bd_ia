// interjddcia/config.py
import sys
import os

# Configuración de la aplicación
class Config:
    def __init__(self):
        self.ruta_archivos = os.path.join(os.getcwd(), 'backend', 'archivos')
        self.ruta_firmas = os.path.join(os.getcwd(), 'backend', 'firmas')
        self.periodo_actualizacion = 24  # Horas

    def get_ruta_archivos(self):
        return self.ruta_archivos

    def get_ruta_firmas(self):
        return self.ruta_firmas

    def get_periodo_actualizacion(self):
        return self.periodo_actualizacion

# Instancia de configuración
config = Config()