# DEVIA - Sistema de Gestión e Inteligencia Artificial

Sistema genérico de gestión de bases de datos con integración de IA para consultas en lenguaje natural.

## 🚀 Características

- **Chat IA**: Consulta tu base de datos en lenguaje natural
- **Múltiples Modelos IA**: Soporte para Groq, OpenRouter, Google Gemini, OpenAI
- **Sistema de Proveedores**: Arquitectura modular que separa proveedores reales de esquemas de API
- **Gestión de Artículos**: CRUD completo con análisis de IA
- **Sistema de Metadatos Inteligente**: Optimización automática de esquemas para IA
- **Constantes Centralizadas**: Single source of truth para toda la configuración
- **Arquitectura Modular**: Fácilmente extensible a diferentes bases de datos
- **Seguridad**: API keys en variables de entorno, nunca en el código
- **API Empleados**: Endpoint `GET /api/employees-real` con jerarquía departamental (CODPADRE/ORDEN)
- **Tests automatizados**: Suite pytest con 38 tests (100% passing)

## 📋 Requisitos

- Python 3.10+
- Firebird 2.5+ (o compatible)
- API Keys para los modelos de IA que desees usar

## 🔧 Instalación

### 1. Clona el repositorio:
```bash
git clone https://github.com/miguelmartmart/jddc_materiales_local_bd_ia.git
cd jddc_materiales_local_bd_ia
```

### 2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

### 3. Configura las variables de entorno:

Crea un archivo `.env` en la raíz del proyecto (copia desde `.env.example`):

```bash
copy .env.example .env
```

Edita `.env` y añade tus API keys:

```env
# AI API Keys
GROQ_API_KEY=tu_api_key_de_groq
OPENROUTER_API_KEY=tu_api_key_de_openrouter
GEMINI_API_KEY=tu_api_key_de_gemini
OPENAI_API_KEY=tu_api_key_de_openai

# Database Configuration
DB_HOST=localhost
DB_PORT=3050
DB_NAME=ruta/a/tu/base.fdb
DB_USER=SYSDBA
DB_PASSWORD=masterkey
```

### 4. Configura la conexión a tu base de datos:

Edita `frontend/assets/js/core/constants.js` y actualiza `DB_CONFIG`:

```javascript
export const DB_CONFIG = {
    HOST: 'tu_host',
    PORT: 3050,
    DATABASE: 'C:\\ruta\\a\\tu\\database.fdb',
    USERNAME: 'SYSDBA',
    PASSWORD: 'masterkey'
};
```

### 5. (Opcional) Genera metadatos de tu base de datos:

```bash
python backend/scripts/extract_db_metadata.py
```

Esto creará archivos JSON optimizados con la estructura de tu BD.

## 🎯 Uso

### Iniciar el sistema:

**Windows:**
```bash
.\start_system.bat
```

**Manual:**
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

Accede a:
- **Frontend**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

## 🏗️ Arquitectura

```
backend/
├── core/
│   ├── abstract/      # Interfaces y clases base
│   ├── config/        # Configuración y metadatos
│   ├── factory/       # Factories para DB e IA
│   └── utils/         # Utilidades (constants, encoding)
├── drivers/
│   ├── ai/            # Drivers de IA (Gemini, OpenAI-compatible)
│   └── db/            # Drivers de BD (Firebird, etc.)
├── modules/
│   ├── articles/      # Gestión de artículos
│   ├── chat/          # Chat con IA
│   ├── models/        # Gestión de modelos IA
│   └── prompts/       # Gestión de prompts
└── main.py            # Punto de entrada

frontend/
├── assets/
│   ├── css/           # Estilos
│   └── js/
│       ├── core/      # Framework (app.js, constants.js)
│       └── modules/   # Módulos por pantalla
└── index.html         # SPA
```

## 🔑 Sistema de Proveedores de IA

El sistema separa **proveedores reales** de **esquemas de API**:

- **Groq**: Modelos Llama y Mixtral ultra-rápidos
- **OpenRouter**: Acceso a Claude, GPT-4, DeepSeek, Qwen, etc.
- **Google Gemini**: Modelos nativos de Google
- **OpenAI**: GPT models directos

Configuración en `backend/core/config/ai_providers_config.json`

## 📊 Sistema de Metadatos

- **Extracción automática**: Script que analiza tu BD Firebird
- **Optimización para IA**: Solo envía información relevante
- **Categorización inteligente**: Clasifica tablas automáticamente
- **Ahorro de tokens**: ~90% menos tokens enviados a la IA

## 🛡️ Seguridad

- ✅ API keys en `.env` (nunca en el código)
- ✅ `.gitignore` configurado para secretos
- ✅ Validación de consultas SQL (solo SELECT)
- ✅ Límites automáticos en consultas (FIRST 100)

## 🧪 Tests

El proyecto incluye una suite de tests automatizados con **pytest**.

### Ejecutar tests

```bash
# Desde la raíz del proyecto interjddcia
pushd "C:\...\interjddcia"
.venv\Scripts\python.exe -m pytest backend/tests --rootdir=. -v
```

### Resultado actual

```
38 passed, 1 warning in 1.13s
```

### Estructura de tests

```
backend/tests/
├── __init__.py
└── modules/
    └── employees/
        ├── test_service.py   # 25 tests: _map_row_to_employee + EmployeesService
        └── test_router.py    # 13 tests: GET /api/employees-real
```

### Configuración

- **`pytest.ini`**: testpaths, pythonpath, verbosidad
- **`conftest.py`**: sys.path + env vars mínimas para entornos sin `.env`

---

## 🔌 API Empleados

### `GET /api/employees-real`

Expone la tabla `RECURSO` de Firebird con jerarquía departamental.

**Respuesta:**
```json
{
  "employees": [
    {
      "code": 14,
      "fullName": "GARCIA GIL, ADRIAN",
      "nif": "48510320P",
      "nss": "301056457317",
      "email": null,
      "phone": "601107251",
      "position": null,
      "parentCode": 2,
      "departmentOrder": 14
    }
  ]
}
```

| Campo             | Origen Firebird | Descripción                        |
|-------------------|-----------------|------------------------------------|
| `code`            | `CODIGO`        | ID único del registro              |
| `fullName`        | `DESCRIPCION`   | Nombre del empleado/departamento   |
| `parentCode`      | `CODPADRE`      | Código del departamento padre      |
| `departmentOrder` | `ORDEN`         | Orden de visualización             |

Integración con el Portal de Empleados (NestJS):
```bash
RESOURCES_SERVICE_URL=http://localhost:8001/api
```

---

## 📚 Documentación

Consulta [DEVIA.MD](DEVIA.MD) para documentación técnica completa:
- Arquitectura detallada
- Patrones de diseño
- Guías de desarrollo
- Sistema de metadatos
- Extensibilidad

## 🤝 Contribuir

Las contribuciones son bienvenidas:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo licencia MIT.

## 👤 Autor

Miguel Martínez - [@miguelmartmart](https://github.com/miguelmartmart)

## 🙏 Agradecimientos

- Google Gemini por el modelo de IA
- Groq por la inferencia ultra-rápida
- OpenRouter por el acceso a múltiples modelos
- Firebird por la base de datos robusta
