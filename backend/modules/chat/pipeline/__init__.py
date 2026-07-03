"""
pipeline/ — Pipeline modular de procesamiento de mensajes del chat.

Cada fase es un módulo independiente que puede activarse/desactivarse
desde config.json sin modificar código.

FASES DEL PIPELINE:
  phase0_safety.py    — Seguridad: protección BD + filtro ético/legal (determinista + IA)
  phase4_formatter.py — Formato: formateo determinista + narrativa IA opcional
  pipeline_config.py  — Configuración centralizada de todas las fases

═══════════════════════════════════════════════════════════════════════════════
PRINCIPIOS DE DESARROLLO DEVIA — OBLIGATORIOS EN TODO CÓDIGO NUEVO
(Fuente: bots/interjddcia/DEVIA.MD § "PRINCIPIOS DE DESARROLLO DEL PROYECTO")
═══════════════════════════════════════════════════════════════════════════════

1. ARQUITECTURA ORIENTADA A IA
   - Contexto mínimo y preciso: nunca enviar más tokens de los necesarios a la IA
   - Fallback gracioso: si la IA falla, el sistema sigue funcionando (degradado, no roto)
   - Autoaprendizaje: registrar qué funciona y qué no para mejorar el sistema
   - Trazabilidad total: cada llamada a la IA queda registrada (tokens, modelo, latencia)
   - Privacidad por diseño: datos sensibles de BD NUNCA salen a internet (PrivacyConfig)
   - Resiliencia multi-modelo: 189 modelos de fallback, nunca un punto único de fallo

2. CALIDAD DE CÓDIGO
   - Ficheros <= 500 líneas: si crece más, refactorizar en módulos
   - Una responsabilidad por clase/módulo (SRP — Single Responsibility Principle)
   - Constantes en ficheros dedicados: constants.py, settings.py — NUNCA literales en código
   - Tipos en todas las funciones: def foo(x: str) -> Dict[str, Any]:
   - Docstrings en todas las clases y métodos públicos
   - Sin imports circulares: dependencias siempre en una sola dirección
   - Sin magic numbers: todo valor numérico tiene nombre y está en constants.py

3. PATRONES DE DISEÑO APLICADOS
   - Singleton   → DeepIndexerService, ContextRetriever, MetadataManager
   - Factory     → DBFactory, AIFactory — abstracción de drivers
   - Strategy    → ModelFallbackOrchestrator — estrategia de fallback
   - Observer    → SSE (Server-Sent Events) — progreso en tiempo real
   - Repository  → MetadataManager — acceso a datos centralizado
   - Facade      → ChatService — fachada que orquesta todos los subsistemas
   - Template Method → SQLCorrector — flujo fijo con pasos variables

4. SEGURIDAD Y CIBERSEGURIDAD
   - Zero-trust para datos de BD: ningún dato de Firebird sale a internet
   - Validación de entrada: Pydantic en todos los endpoints (min_length, max_length, ge, le)
   - Sin SQL injection: parámetros siempre como tuplas, nunca f-strings en SQL
   - Columnas sensibles: PrivacyConfig.SENSITIVE_COLUMNS excluidas de muestras a IA
   - API keys en .env: nunca en el código, nunca en logs
   - Logs sin datos sensibles: los logs muestran estructura, no valores de columnas sensibles
   - CORS configurado: solo orígenes conocidos en producción
   - Timeouts en todas las llamadas HTTP: nunca esperar indefinidamente

5. MODULARIDAD Y ESTRUCTURA DE CARPETAS
   - Un módulo no importa de otro módulo directamente
   - Si necesita algo de otro módulo, lo hace a través de core/
   - Cada módulo tiene su router.py, service.py, constants.py y DEVIA.md

6. ESCALABILIDAD Y RENDIMIENTO
   - Índices en memoria: table_index, concept_index, db_graph cargados al arrancar
   - Búsqueda O(1): concept_index es un dict, no una lista que hay que recorrer
   - Batches configurables: batch_size en DeepIndexerService (1-20 tablas por batch)
   - SSE para procesos largos: nunca bloquear el cliente con un proceso de 30 minutos
   - Singleton para servicios pesados: no crear instancias nuevas en cada petición
   - Timeout en todas las llamadas: Qwen3 20s, Firebird 3 reintentos con backoff

7. ROBUSTEZ Y DETECCIÓN DE ERRORES
   - Try/except en todo acceso externo: BD, IA, ficheros, red
   - Errores tipados: nunca except Exception: pass sin log
   - Fallback en cascada: SIUO → db_metadata_optimized.json → esquema mínimo
   - Reintentos con backoff: SQL hasta 4 intentos, BD hasta 3 intentos
   - Logs estructurados: [MODULO][PASO] EMISOR → RECEPTOR: mensaje
   - Health check: GET /health siempre disponible, incluso si la BD falla

8. TRAZABILIDAD Y MEDICIÓN
   - Logs en cada paso crítico: conexión BD, llamada IA, SQL generado, resultado
   - Metadatos de contexto: cada respuesta incluye tablas usadas, tokens, fuente
   - Query log: siuo_query_log.json registra cada pregunta con keywords y tablas usadas
   - Feedback loop: endpoint POST /api/siuo/learning/feedback para marcar SQL correcto/incorrecto

9. AUTOAPRENDIZAJE Y MEJORA CONTINUA
   - El sistema registra keywords no mapeados frecuentes
   - POST /api/siuo/reload recarga índices en memoria sin reiniciar
   - Feedback confirma mejoras: SQL correcto/incorrecto persiste en siuo_query_log.json

10. USABILIDAD Y EXPERIENCIA DE DESARROLLO
    - DEVIA.md en cada módulo: documentación local de responsabilidad, flujo y dependencias
    - Comandos de diagnóstico: curl commands listos en DEVIA.MD § 10
    - Errores en JSON: nunca HTML de error, siempre {"detail": "mensaje claro"}
    - Swagger UI: http://localhost:8001/docs con todos los endpoints documentados
═══════════════════════════════════════════════════════════════════════════════
"""

from backend.modules.chat.pipeline.phase0_safety import (
    SafetyGuard,
    SafetyResult,
    RiskLevel,
    BlockReason,
    evaluate_deterministic,
)
from backend.modules.chat.pipeline.phase4_formatter import (
    ResponseFormatter,
    FormattedResult,
    ResultType,
    format_deterministic,
)
from backend.modules.chat.pipeline.pipeline_config import (
    get_pipeline_config,
    reload_pipeline_config,
    PipelineConfig,
    PhaseConfig,
)

__all__ = [
    # Phase 0 — Safety
    "SafetyGuard",
    "SafetyResult",
    "RiskLevel",
    "BlockReason",
    "evaluate_deterministic",
    # Phase 4 — Formatter
    "ResponseFormatter",
    "FormattedResult",
    "ResultType",
    "format_deterministic",
    # Config
    "get_pipeline_config",
    "reload_pipeline_config",
    "PipelineConfig",
    "PhaseConfig",
]
