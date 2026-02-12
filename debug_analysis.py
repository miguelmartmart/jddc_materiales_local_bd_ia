
import asyncio
import logging
from backend.modules.outlook.analysis_service import EmailAnalyzer
from backend.core.config.settings import settings

# Configure basic logging to console
logging.basicConfig(level=logging.INFO)

async def test_deep_analysis():
    print("--- STARTING TEST ---")
    analyzer = EmailAnalyzer()
    
    # Mock context
    context = """
    Asunto: Oferta de Proyecto Urgente
    Remitente: cliente@empresa.com
    Cuerpo: 
    Hola Miguel,
    Necesitamos entregar el proyecto antes del viernes 15 de enero.
    Por favor revisa el presupuesto adjunto y confírmame si puedes hacerlo.
    Saludos.
    """
    
    print("--- CALLING ANALYZE DEEPLY ---")
    try:
        result = await analyzer.analyze_deeply(context)
        print("\n--- RESULT ---")
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"\n--- ERROR ---\n{e}")

if __name__ == "__main__":
    asyncio.run(test_deep_analysis())
