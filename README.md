# DEVIA - Sistema de Gestión e Inteligencia Artificial

Sistema genérico de gestión de bases de datos con integración de IA para consultas en lenguaje natural.

## 🚀 Características

- **Chat IA**: Consulta tu base de datos en lenguaje natural
- **Múltiples Modelos IA**: Soporte para Groq, OpenRouter, Google Gemini
- **Gestión de Artículos**: CRUD completo con análisis de IA
- **Sistema de Metadatos**: Optimización automática de esquemas para IA
- **Arquitectura Modular**: Fácilmente extensible a diferentes bases de datos

## 📋 Requisitos

- Python 3.10+
- Firebird 2.5+ (o compatible)
- API Keys para los modelos de IA que desees usar

## 🔧 Instalación

1. Clona el repositorio:
```bash
git clone https://github.com/miguelmartmart/jddc_materiales_local_bd_ia.git
cd jddc_materiales_local_bd_ia
```

2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

3. Configura las variables de entorno en `.env`:
```env
GROQ_API_KEY=tu_api_key_aqui
OPENROUTER_API_KEY=tu_api_key_aqui
GEMINI_API_KEY=tu_api_key_aqui
```

4. Configura la conexión a tu base de datos en `frontend/assets/js/core/constants.js`

## 🎯 Uso

### Iniciar el sistema:
```bash
.\start_system.bat
```

O manualmente:
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

Accede a:
- **Frontend**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

## 📚 Documentación

Consulta [DEVIA.MD](DEVIA.MD) para documentación técnica completa.

## 🏗️ Arquitectura

```
backend/
├── core/           # Núcleo del sistema
├── drivers/        # Drivers de BD e IA
├── modules/        # Módulos de negocio
└── main.py         # Punto de entrada

frontend/
├── assets/         # CSS, JS, recursos
└── index.html      # SPA
```

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor:
1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo licencia MIT.

## 👤 Autor

Miguel Martínez - [@miguelmartmart](https://github.com/miguelmartmart)
