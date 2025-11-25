from typing import Dict, Any, Optional

# AI Providers Configuration
AI_PROVIDERS = {
    "gemini": {
        "name": "Google Gemini",
        "model": "gemini-2.0-flash-exp", # Updated to a valid model or user preference
        "api_key_env": "GEMINI_API_KEY",
        "priority": 1,
        "capabilities": [
            "identificacion_material", "clasificacion", "extraccion_marca",
            "extraccion_modelo", "extraccion_atributos"
        ],
        "max_tokens": 8000,
        "temperature": 0.3,
        "description": "Google Gemini - Modelo flash optimizado"
    },
    "groq": {
        "name": "Groq",
        "model": "llama-3.3-70b-versatile",
        "api_key_env": "GROQ_API_KEY",
        "priority": 2,
        "capabilities": [
            "identificacion_material", "clasificacion", "extraccion_marca",
            "extraccion_modelo", "analisis_tecnico"
        ],
        "max_tokens": 4096,
        "temperature": 0.2,
        "description": "Groq - Modelo Llama optimizado"
    },
    "openai": {
        "name": "OpenAI",
        "model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
        "priority": 3,
        "capabilities": [
            "identificacion_material", "clasificacion", "extraccion_marca",
            "extraccion_modelo", "extraccion_atributos", "analisis_tecnico",
            "interpretacion_compleja"
        ],
        "max_tokens": 16000,
        "temperature": 0.1,
        "description": "OpenAI GPT-4o"
    }
}

# Task-Specific Prompts
PROMPTS = {
    "identificacion_material": {
        "system": """Eres un experto en identificación de materiales de construcción, climatización y fontanería.
Tu tarea es identificar el tipo de material principal a partir del nombre del artículo.

Responde SOLO con el tipo de material en formato JSON:
{
    "material_principal": "NOMBRE_MATERIAL",
    "confianza": "ALTA|MEDIA|BAJA",
    "razonamiento": "breve explicación"
}""",
        "user_template": "Identifica el material principal en: {nombre_articulo}"
    },
    "analisis_completo": {
        "system": """Eres un experto en análisis completo de materiales técnicos.
Analiza el artículo y proporciona:
1. Material Principal
2. Categoría, Subcategorías y Familia
3. Marca y Modelo
4. Atributos Técnicos
5. URLs de Verificación

Responde en formato JSON:
{
    "material_principal": "NOMBRE_IDENTIFICADOR",
    "categoria": "CATEGORIA",
    "subcategorias": ["NIVEL1", "NIVEL2"],
    "familia": "FAMILIA",
    "marca": "MARCA o null",
    "modelo": "MODELO o null",
    "atributos": {
        "diametro": "valor",
        "potencia": "valor"
    },
    "urls_verificacion": [],
    "confianza": "ALTA|MEDIA|BAJA"
}""",
        "user_template": "Analiza completamente este artículo: {nombre_articulo}"
    }
}

def get_provider_config(provider_name: str) -> Optional[Dict[str, Any]]:
    return AI_PROVIDERS.get(provider_name)

def get_prompt(task_name: str, **kwargs) -> Optional[Dict[str, str]]:
    config = PROMPTS.get(task_name)
    if not config:
        return None
    return {
        "system": config["system"],
        "user": config["user_template"].format(**kwargs)
    }
