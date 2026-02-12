import sys
import os
from pathlib import Path

# Add project root to sys.path to allow imports from backend.core
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Ensure .env exists for pydantic settings
import shutil
env_path = Path(".env")
parent_env_path = project_root / ".env"

if not env_path.exists():
    if parent_env_path.exists():
        print(f"Copying .env from {parent_env_path} to {env_path}")
        shutil.copy(parent_env_path, env_path)
    else:
        print(f"Warning: .env not found in {env_path} or {parent_env_path}")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
import logging

# Import existing AI components
try:
    from backend.core.factory.ai_factory import AIFactory
    from backend.core.config.model_manager import ModelManager
    from backend.core.abstract.ai import AIConfig
    from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
except ImportError as e:
    print(f"Error importing backend modules: {e}")
    print(f"Sys path: {sys.path}")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DesktopBackend")

app = FastAPI(title="AI Code Lab Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateRequest(BaseModel):
    prompt: str
    messages: Optional[List[Dict[str, str]]] = None
    code_context: Optional[str] = None
    model_id: Optional[str] = None
    project_path: Optional[str] = None
    system_prompt: Optional[str] = None

class ModelListResponse(BaseModel):
    models: List[Dict[str, Any]]

@app.get("/api/models", response_model=ModelListResponse)
async def list_models():
    try:
        manager = ModelManager()
        models = manager.list_models()
        # Filter enabled models
        enabled = [m for m in models if m.get('enabled', False)]
        return {"models": enabled}
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/models/refresh")
async def refresh_models():
    """
    Connects to APIs (Google, OpenAI, Anthropic...), downloads real model lists,
    updates configuration files (google.json, open_models.json), and returns status.
    """
    try:
        logger.info("Starting model refresh/discovery process...")
        manager = ModelManager()
        results = []

        # 1. Google Gemini Discovery
        # Attempt to load google.json
        google_path = project_root / "backend/core/config/models/google.json"
        if google_path.exists():
            try:
                import json
                with open(google_path, 'r') as f:
                    google_config = json.load(f)
                
                # Check for API Key
                api_key = None
                # Assuming simple structure or list. Usually it's a list of models.
                # If it's a list, find one with an api_key
                if isinstance(google_config, list):
                    for m in google_config:
                        if m.get('api_key'):
                            api_key = m.get('api_key')
                            break
                
                if api_key:
                    try:
                        import google.generativeai as genai
                        genai.configure(api_key=api_key)
                        real_models = list(genai.list_models())
                        gemini_models = [m for m in real_models if 'generateContent' in m.supported_generation_methods]
                        
                        logger.info(f"Found {len(gemini_models)} Google models")
                        
                        # Update config logic here...
                        # For now, we will just log success and maybe update description or mark enabled
                        results.append(f"Google: Found {len(gemini_models)} models via API.")
                    except ImportError:
                        results.append("Google: google-generativeai package not installed.")
                    except Exception as ge:
                        results.append(f"Google: API Error - {str(ge)}")
                else:
                    results.append("Google: No API Key found in config.")
            except Exception as e:
                results.append(f"Google: Config error - {str(e)}")

        # 2. OpenAI Discovery
        openai_path = project_root / "backend/core/config/models/openai.json"
        if openai_path.exists():
             try:
                import json
                with open(openai_path, 'r') as f:
                    openai_config = json.load(f)
                
                api_key = None
                if isinstance(openai_config, list):
                    for m in openai_config:
                        if m.get('api_key'):
                            api_key = m.get('api_key')
                            break
                
                if api_key:
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=api_key)
                        models_page = client.models.list()
                        # Just count them or check for specific ones like gpt-4o
                        gpt_models = [m.id for m in models_page.data if 'gpt' in m.id]
                        results.append(f"OpenAI: Found {len(gpt_models)} GPT models via API.")
                    except ImportError:
                        results.append("OpenAI: openai package not installed.")
                    except Exception as oe:
                        results.append(f"OpenAI: API Error - {str(oe)}")
                else:
                    results.append("OpenAI: No API Key found.")

             except Exception as e:
                 results.append(f"OpenAI: Config error - {str(e)}")

        # 3. Reload Manager to ensure fresh state
        # manager.reload() # If such method exists, or just next call will read files
        
        return {"message": " | ".join(results)}

    except Exception as e:
        logger.error(f"Error refreshing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def try_specific_model(model_id: str, prompt: str, system_prompt: str) -> Optional[str]:
    """Try to generate with a specific model, return None if fails."""
    try:
        manager = ModelManager()
        models = manager.list_models()
        model_config = next((m for m in models if m.get('id') == model_id), None)
        
        if not model_config:
            logger.warning(f"Model {model_id} not found in configuration")
            return None
            
        if not model_config.get('enabled'):
            logger.warning(f"Model {model_id} is disabled")
            return None

        api_key = model_config.get('api_key')
        if not api_key:
            logger.warning(f"No API key for model {model_id}")
            return None
            
        provider_name = model_config.get('provider')
        if not provider_name and 'schema' in model_config:
            provider_name = model_config['schema']
            
        logger.info(f"Attempting to use specific model: {model_config.get('name')} ({provider_name})")
        
        provider = AIFactory.get_provider(provider_name)
        
        ai_config_params = {
            'api_key': api_key,
            'model': model_config['model_id']
        }
        if model_config.get('base_url'):
            ai_config_params['base_url'] = model_config['base_url']
        if model_config.get('headers'):
            ai_config_params['headers'] = model_config['headers']
            
        provider.configure(AIConfig(**ai_config_params))
        
        return await provider.generate_text(prompt, system_instruction=system_prompt)
    except Exception as e:
        logger.error(f"Specific model {model_id} failed: {e}")
        return None

@app.post("/api/generate")
async def generate_code(request: GenerateRequest):
    try:
        logger.info(f"Received generation request. Model: {request.model_id or 'Auto'}")
        
        # Determine base folder name
        base_folder = "." # Default to current directory to avoid creating intermediate folders
        existing_folders = []
        if request.project_path:
            # Extract last folder name from path (handle Windows/Unix separators)
            import os
            # If project_path is provided, we use its basename, OR we can just use "." if we want to work RELATIVE to that path.
            # But the AI needs to know the "Project Name" for context.
            # Let's use the basename for display/context, but tell AI to use relative paths if possible.
            base_folder = os.path.basename(os.path.normpath(request.project_path))
            
            # List immediate subdirectories for context
            try:
                with os.scandir(request.project_path) as entries:
                    existing_folders = [entry.name for entry in entries if entry.is_dir() and not entry.name.startswith('.')]
            except Exception as e:
                logger.warning(f"Could not list directories in {request.project_path}: {e}")
        
        # Construct default system prompt if not provided
        if not request.system_prompt:
            folders_context = ", ".join(existing_folders) if existing_folders else "(Ninguna detectada)"
            logger.info(f"Context folders detected: {folders_context}")
            
            # Determine path prefix for instructions
            path_prefix = base_folder if base_folder != "." else "[RAIZ]"
            
            request.system_prompt = (
                f"Eres un compañero de programación Senior (AI Pair Programmer). Tu misión es colaborar con el usuario en el proyecto '{base_folder}'.\n\n"
                f"**PERSONALIDAD Y TONO**:\n"
                f"1. **AMIGABLE Y DIRECTO**: Háblale al usuario de 'tú'. Sé cercano pero profesional. Evita formalismos excesivos.\n"
                f"2. **PROACTIVO**: No solo respondas, propón la mejor forma de avanzar.\n"
                f"3. **FACILITADOR**: Tu objetivo es que el usuario tenga que escribir lo menos posible. Automatiza los comandos.\n\n"

                f"**REGLAS CRÍTICAS DE RESPUESTA**:\n"
                f"1. **PROHIBIDO** repetir código o explicaciones anteriores.\n"
                f"2. **CÓDIGO COMPLETO**: Genera siempre código funcional. Usa `// carpeta/archivo.ext` al inicio de cada bloque.\n"
                f"3. **CARPETAS**: No crees carpetas intermedias redundantes. Si '{base_folder}' es la raíz, úsala.\n"
                f"4. **SIN INPUT INTERACTIVO**: La terminal integrada NO soporta `input()`. Usa `sys.argv` o `argparse` para recibir parámetros.\n"
                f"   - MAL: `folder = input('Dime la carpeta: ')`\n"
                f"   - BIEN: `folder = sys.argv[1] if len(sys.argv) > 1 else '.'`\n"
                f"   - MEJOR: Pregunta al usuario en el chat qué carpeta quiere, y luego genera el comando con la ruta: `python script.py \"C:/Ruta\"`.\n\n"
                "**SEGUIMIENTO DE INSTRUCCIONES DEL USUARIO (OBLIGATORIO)**:\n"
                "- Si el usuario dice cosas como 'haz que...', 'modifica...', 'cambia...', 'ahora quiero que...', 'además quiero que...':\n"
                "  1. Trátalo como un NUEVO REQUISITO ESTRICTO, no como un simple comentario.\n"
                "  2. Resume en 1 frase qué cambio funcional te está pidiendo.\n"
                "  3. ACTUALIZA el código para cumplir ese nuevo requisito en la misma respuesta.\n"
                "  4. Explica explícitamente qué has cambiado y en qué fichero (1-2 frases).\n"
                "  5. No repitas simplemente que 'todo está bien' si la nueva petición no está reflejada en el código.\n"
                "- Ejemplo: si el usuario dice 'haz que el programa pida la ruta a escanear', debes:\n"
                "  - Ajustar el script para que lea la ruta (por argumentos o configuración) de forma clara para el usuario.\n"
                "  - Indicar: 'He actualizado el script para que solicite la ruta de escaneo de la siguiente forma: ...'.\n\n"
                "**REGLAS DE USABILIDAD DE RUTAS (OBLIGATORIAS)**:\n"
                "- NUNCA generes scripts que solo muestren mensajes como 'Por favor, proporciona una ruta de escaneo como argumento.' cuando no se pasa ninguna ruta.\n"
                "- TODO script que acepte una ruta debe poder ejecutarse SIN argumentos usando una ruta por defecto segura (por ejemplo `.` o una carpeta concreta del proyecto).\n"
                "- Usa siempre el patrón: `folder = sys.argv[1] if len(sys.argv) > 1 else '.'` (o similar) para combinar ruta por argumento + ruta por defecto.\n"
                "- Cuando sugieras 'probar con otras rutas', 'probar en otra carpeta' o similar, DEBES incluir SIEMPRE botones `[[NEXT_ACTION:...]]` de tipo `run_command` con rutas concretas:\n"
                "  - Uno con la ruta por defecto.\n"
                "  - Al menos uno con una ruta de ejemplo real de Windows (por ejemplo `C:/Users/migue/Documents` o `C:/Users/migue/Downloads`).\n"
                "- Si has creado un script como `// cibrseg/detectores_malware.py`, los botones de ejemplo pueden ser:\n"
                "  - `[[NEXT_ACTION:{\"type\":\"run_command\",\"content\":\"python cibrseg/detectores_malware.py\",\"label\":\"Escanear ruta por defecto\"}]]`\n"
                "  - `[[NEXT_ACTION:{\"type\":\"run_command\",\"content\":\"python cibrseg/detectores_malware.py \\\"C:/Users/migue/Downloads\\\"\",\"label\":\"Escanear Descargas\"}]]`\n\n"

                f"**FASE 0: CONTEXTO**\n"
                f"Carpetas existentes: [{folders_context}]\n\n"
                
                "**ESTRUCTURA DE RESPUESTA OBLIGATORIA**:\n"
                "1. **ESTADO**: Paso [X] de [Total].\n"
                "2. **EXPLICACIÓN**: Breve y directa (1 frase).\n"
                "3. **ACCIÓN (CÓDIGO REAL)**:\n"
                "   - Si creas o modificas un archivo SIEMPRE debes incluir un bloque de código COMPLETO con la PRIMERA línea indicando la ruta exacta del archivo.\n"
                "   - **FORMATO ESTRICTO OBLIGATORIO**:\n"
                "     ```[lenguaje]\n"
                f"     // {path_prefix}/[RUTA_ARCHIVO.ext]\n"
                "     [CÓDIGO]\n"
                "     ```\n"
                "   - ⚠️ **ADVERTENCIA CRÍTICA**: JAMÁS escribas ` ```// ruta... `. SIEMPRE escribe el lenguaje (ej. `python`), pulsa ENTER, y luego la ruta.\n"
                "   - NUNCA uses nombres genéricos sin extensión como `monitor_resources` a secas; usa siempre `carpeta/monitor_resources.py`.\n\n"
                "**LENGUAJE Y TIEMPOS VERBALES (CRÍTICO)**:\n"
                "- Si vas a crear una carpeta o archivo en este paso (mediante código), NO digas 'he creado la carpeta'. Di 'se creará la carpeta' o 'el código creará la carpeta'.\n"
                "- Solo usa pasado ('he creado') si estás seguro de que la acción YA ocurrió en un paso ANTERIOR.\n"
                "- Como regla general: Describe lo que HACE el código que acabas de generar, no lo que ya ha pasado.\n\n"
                "**IMPORTANTE: GENERACIÓN DE BOTONES (OBLIGATORIO)**:\n"
                "Para que aparezca un botón en la interfaz, DEBES incluir el código JSON específico. Este código JSON será OCULTO al usuario, así que asegúrate de explicar en el texto qué debe hacer.\n"
                "Usa el formato JSON estricto `[[NEXT_ACTION:{...}]]` al final de tu respuesta:\n\n"
                "1. **Ejecutar Pasos** (Solo si el archivo existe o lo acabas de crear EN ESTA MISMA RESPUESTA):\n"
                "   - El campo `content` DEBE usar exactamente la ruta del archivo que has puesto en la primera línea del bloque de código.\n"
                "   - EJEMPLO: si arriba usaste `// cibrseg/detectores_malware.py`, entonces:\n"
                "     `[[NEXT_ACTION:{\"type\":\"run_command\",\"content\":\"python cibrseg/detectores_malware.py\",\"label\":\"Ejecutar Pasos\"}]]`\n"
                "2. **Abrir HTML**:\n"
                "   `[[NEXT_ACTION:{\"type\":\"browser\",\"content\":\"carpeta/index.html\",\"label\":\"Abrir en Navegador\"}]]`\n"
                "3. **Siguiente Paso (Instrucción)**:\n"
                "   `[[NEXT_ACTION:{\"type\":\"chat_message\",\"content\":\"Instrucción para el siguiente paso\",\"label\":\"Continuar\"}]]`\n\n"
                "**MANEJO DE ERRORES (MÁXIMA PRIORIDAD)**:\n"
                "- Si recibes un mensaje `[SYSTEM] ❌ CRITICAL EXECUTION FAILURE`, `SUCCESS_FLAG: False` o `Success: False`:\n"
                "  1. DETÉN tu plan actual. NO sigas con el siguiente paso.\n"
                "  2. NO digas '¡Perfecto!', 'Genial' ni nada que implique éxito.\n"
                "  3. LEE con atención el bloque `ERROR_TYPE` y `ERROR_OUTPUT` si están presentes.\n"
                "  4. SI `ERROR_TYPE: USER_CANCELLED`:\n"
                "     - Explica claramente que la ejecución se canceló desde el diálogo de confirmación, no por un fallo del código.\n"
                "     - NO modifiques el código solo por eso.\n"
                "     - Ofrece SIEMPRE un botón `[[NEXT_ACTION:{\"type\":\"run_command\",...}]]` para volver a ejecutar el mismo comando.\n"
                "  5. SI `ERROR_TYPE: EXECUTION_ERROR` o no se especifica tipo:\n"
                "     - Analiza el error y corrige el código.\n"
                "     - Vuelve a dar el bloque COMPLETO del archivo corregido.\n"
                "     - Indica explícitamente qué has cambiado (1-2 frases) y en qué fichero.\n"
                "     - Termina SIEMPRE con un botón `run_command` para volver a ejecutar el script corregido.\n"
                "     - Si el MISMO error se repite varias veces (por ejemplo, varios `IndentationError` iguales), CAMBIA DE ESTRATEGIA:\n"
                "       · Ajusta la sangría de forma explícita (sin tabulaciones al principio del archivo, `import` siempre en la columna 0).\n"
                "       · Evita volver a mandar exactamente el mismo código que ya ha fallado.\n"
                "       · Si es un error de indentación, asegúrate de que la primera línea no tiene ningún espacio ni tabulación delante.\n\n"
                "**VERIFICACIÓN Y ROBUSTEZ**:\n"
                "- Si generas código para un archivo, ASEGÚRATE de incluir el bloque de código correcto.\n"
                "- Si pides ejecutar un comando, asegúrate de que los archivos necesarios existen o los acabas de generar.\n"
                "- **REVISA EL OUTPUT**: Si el resultado de la ejecución contiene 'Error' o 'Exception' (incluso si dice Success: True), TU TAREA NO HA TERMINADO. Debes corregirlo inmediatamente.\n"
                "- NO digas 'Dale al botón' si no has incluido la etiqueta `[[NEXT_ACTION:...]]`.\n"
                "- Mensaje final: '¡Listo! Dale al botón de abajo para [acción].'\n"
            )

        # Construct full prompt including history if available
        full_prompt = ""
        
        if request.messages:
            # Format history as text for models that don't support chat natively yet
            # (or for simplicity with the current orchestrator)
            for msg in request.messages:
                role = msg.get("role", "user").upper()
                content = msg.get("content", "")
                full_prompt += f"{role}: {content}\n\n"
            
            full_prompt += f"USER: {request.prompt}\n\n"
            # Force small models to follow the summary instruction by injecting it into the user prompt
            full_prompt += "\n\n**INSTRUCCIÓN MAESTRA FINAL (CRÍTICA)**:\n"
            full_prompt += "1. Genera TODO el código solicitado primero.\n"
            full_prompt += "2. AL FINAL, añade obligatoriamente:\n"
            full_prompt += "   '## Resumen'\n"
            full_prompt += "   (Breve frase de lo hecho)\n"
            full_prompt += "   '## Próximos Pasos'\n"
            full_prompt += "   (Qué debe hacer el usuario ahora)\n"
            full_prompt += "   [[NEXT_ACTION:{\"type\":\"...\",\"content\":\"...\"}]]\n"
            full_prompt += "   (Rellena el JSON con la acción real: run_command, open_file, etc)\n"
            full_prompt += "ASSISTANT:"
        else:
            full_prompt = request.prompt
            full_prompt += "\n\n**IMPORTANTE**: 1. Genera el CÓDIGO. 2. Añade sección '## Resumen y Próximos Pasos' al final. 3. Añade `[[NEXT_ACTION:{...}]]` al final."

        if request.code_context:
            full_prompt += f"\n\nContext:\n```\n{request.code_context}\n```"
        
        response = None
        
        # 1. Try requested model if specified
        used_model = request.model_id
        if request.model_id:
            response = await try_specific_model(request.model_id, full_prompt, request.system_prompt)
            if response:
                logger.info(f"Successfully generated with requested model {request.model_id}")
            else:
                logger.warning(f"Requested model {request.model_id} failed or unavailable. Falling back to orchestrator.")
        
        # 2. Fallback to orchestrator if needed
        if not response:
            logger.info("Starting robust model fallback strategy...")
            orchestrator = ModelFallbackOrchestrator()
            
            def feedback_handler(msg):
                logger.info(f"[Orchestrator]: {msg}")
                
            response, used_model = await orchestrator.execute_with_fallback(
                system_prompt=request.system_prompt,
                user_message=full_prompt,
                feedback_callback=feedback_handler,
                preferred_model_id=request.model_id
            )
            
            if response:
                logger.info(f"Orchestrator succeeded with model: {used_model}")
            
        if not response:
            raise HTTPException(status_code=500, detail="Unable to generate code. All available AI models failed.")
            
        return {"response": response, "model": used_model}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in generate_code: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8002))
    uvicorn.run(app, host="127.0.0.1", port=port)
