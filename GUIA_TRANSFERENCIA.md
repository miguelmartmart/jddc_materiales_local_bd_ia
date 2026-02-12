# Guía de Transferencia: Instalación en un Nuevo PC

Sigue estos pasos detallados para tener el proyecto funcionando al 100% en otro ordenador.

## 1. Requisitos Previos (Instalar en el nuevo PC)

1.  **Git**: [Descargar e instalar Git](https://git-scm.com/).
2.  **Python 3.10+**: Asegúrate de marcar "Add Python to PATH" durante la instalación.
3.  **Firebird 2.5/3.0**: Necesario para la base de datos `.fdb`.
4.  **LM Studio** (Opcional): Si quieres realizar análisis de imágenes localmente.

## 2. Paso a Paso: Clonar e Instalar

### A. Clonar el repositorio
Abre una terminal (PowerShell o CMD) y ejecuta:
```bash
git clone https://github.com/miguelmartmart/jddc_materiales_local_bd_ia.git
cd jddc_materiales_local_bd_ia
```

### B. Crear entorno virtual
```bash
python -m venv .venv
# Activar en Windows
.\.venv\Scripts\activate
```

### C. Instalar dependencias
```bash
pip install -r requirements.txt
```

## 3. Configuración del Entorno (.env)

El archivo `.env` NO está en GitHub por seguridad. Debes crearlo manualmente:

1.  Copia el archivo `.env.example` y cámbiale el nombre a `.env`.
2.  Abre el `.env` con un editor de texto y rellena tus claves API (OpenAI, Gemini, etc.).
3.  **IMPORTANTE (Base de Datos):** Cambia la ruta `DB_NAME` por la ruta donde pongas el archivo `.fdb` en el nuevo PC.

## 4. Transferencia de Archivos Manuales (NO están en GitHub)

Debido a su tamaño o privacidad, debes copiar estos archivos/carpetas desde el PC original mediante un USB o red local:

1.  **Base de Datos**: El archivo `.fdb` (ej: `2021.fdb`). Ponlo en una ruta conocida y actualiza el `.env`.
2.  **Configuraciones Locales**: Cualquier archivo `.json` o `.yaml` que hayas modificado y que esté en el `.gitignore`.
3.  **Carpeta `data/`**: Si tienes imágenes generadas o logs históricos que quieras conservar.

## 5. Ejecución

Para iniciar el sistema, puedes usar los scripts incluidos:
```powershell
.\start_system.bat
```
O manualmente:
```bash
python app.py
```

---
**Nota:** Si encuentras errores al iniciar, asegúrate de que el puerto `3050` (Firebird) esté abierto y el servicio Firebird esté corriendo.
