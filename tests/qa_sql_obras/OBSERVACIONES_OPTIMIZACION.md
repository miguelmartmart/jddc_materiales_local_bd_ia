# Observaciones y conclusiones — hacia una optimización de las fases del chat IA

> **Propósito:** este fichero acumula, con fecha, las observaciones y conclusiones concretas que van saliendo mientras se generan y (más adelante) se ejecutan los tests de `tests/qa_sql_obras/`. No es el registro de progreso (eso vive en `DEVIA.MD` de esta misma carpeta y cuenta "qué hice"); esto cuenta **"qué aprendí sobre las carencias del sistema"**, para poder proponer al final una optimización concreta de las fases del pipeline (`SemanticReasoningEngine` → IA genera SQL → `HallucinationGuard` → `FirebirdSQLNormalizer` → ejecución BD → `SQLCorrector` → interpretación) de forma que las respuestas del chat IA sean de ultra calidad.
>
> Cada observación debería, cuando sea posible, apuntar a **qué fase o módulo** tocaría cambiar. No se propone la optimización todavía — se recopila evidencia primero. Referenciado desde `bots/interjddcia/DEVIA.MD`.

---

## 17/07/2026 — Sesión 1 (durante la generación de tests del módulo SQL-02)

**1. El manual de usuario no llega nunca al modelo IA — solo el `KnowledgeStore` (hechos de BD) sí.**
El pipeline de construcción de prompt (`chat/DEVIA.MD` → `prompt_engineering.dynamic_injection`) solo inyecta: esquema de BD, análisis de imagen, fecha/hora, contexto de usuario. El `KnowledgeStore` (`chat/deep_analysis/knowledge_store.py`) aprende hechos **descubiertos empíricamente vía SQL** (columnas reales, distribuciones de TIPO, reglas de negocio inferidas de los datos) — pero nunca ingiere el manual de usuario (`MANUAL_SQL_OBRAS.md`), que contiene reglas de negocio explícitas que **no son deducibles solo mirando filas de la BD** (ver observación 5).
→ **Fase candidata a optimizar:** falta una fuente de conocimiento estático tipo RAG sobre el manual, complementaria al `KnowledgeStore` (que es dinámico/empírico). Sin esto, cualquier pregunta puramente procedimental ("¿cómo configuro X?", "¿qué significa el riesgo máximo de un cliente?") depende de que el modelo lo sepa de memoria general — riesgo de alucinación.

**2. Fiabilidad histórica de los modelos LAN es muy baja (según `jddcia_models.json` → campo `stats`).**
30B-ip: 9 éxitos / 955 fallos. 30B-mDNS: 731/975. 8B-ip: 61/597. 8B-mDNS: 0/589. Son contadores acumulados históricos (no reflejan necesariamente el estado actual), pero indican que la infraestructura LAN ha fallado la mayoría de las veces en producción.
→ **Fase candidata a optimizar:** `ModelFallbackOrchestrator` — antes de invertir en mejorar prompts/razonamiento, la disponibilidad de los modelos parece ser un cuello de botella mayor para la "calidad percibida" (una respuesta correcta que nunca llega no es ultra calidad). Merece la pena medir con los tests cuánto de la tasa de fallo es disponibilidad vs. calidad de respuesta real.

**3. Contexto de esta sesión (confirmado por el usuario, 17/07/2026): solo hay acceso al modelo 8B ahora mismo (30B no disponible); SÍ hay acceso tanto a BD real como a BD simulada.**
Dato relevante: el 8B tiene `context_limit=8192` (mayor que el 30B, `4096`) pero tier `"high"` vs `"elite"` del 30B — no es simplemente "el modelo pequeño y peor en todo".
→ **Aplicación práctica inmediata:** las tandas de tests que se generen mientras el 30B no esté disponible deben fijar `model_id=MODEL_8B` explícitamente (no dejarlo en fallback automático) para que el resultado sea atribuible de verdad al 8B — ver caveat ya documentado en `tests/qa_sql_obras/helpers.py`.

**4. Varias entidades maestras del manual no tienen tabla confirmada en el esquema simulado.**
Zonas, Estaciones de trabajo, Mensajes personalizados, Datos adicionales, Horario laboral, Tipos de dirección, Tipos de catálogos, Tipos de contactos, Rappels de venta/compra — ninguna tiene una tabla claramente identificable en `backend/modules/db_simulator/schema.py` (que el propio fichero marca como "esquema mínimo de fallback, ampliado con Firebird real en build-snapshot" para varias tablas auxiliares).
→ **Fase candidata a optimizar:** `HallucinationGuard` hará bien en bloquear SQL sobre estas entidades (correcto, evita alucinar), pero eso deja al usuario sin respuesta. Una respuesta "ultra calidad" debería, en ese caso, decir explícitamente qué no se puede consultar y por qué — no limitarse a fallar. Esto requiere que el guard/orquestador sepa distinguir "tabla no soportada" de "error genérico".

**5. Las reglas de negocio del manual son precisamente el tipo de conocimiento que el `KnowledgeStore` (empírico) no puede descubrir solo.**
Ejemplos concretos del módulo SQL-02: "las condiciones de FAMILIA solo aplican si el artículo no tiene condiciones específicas propias" (SQL-02-004), "la comisión por defecto del agente se aplica salvo que artículo/familia tenga una distinta" (SQL-02-002), "riesgo máximo bloquea operaciones, riesgo en curso es la deuda actual" (SQL-02-022) — son reglas de **precedencia/comportamiento de UI**, no patrones visibles con un `SELECT` sobre los datos. `Fase 4b` (aprendizaje del `KnowledgeStore`) nunca las va a "descubrir" porque no dejan huella estadística clara en la BD.
→ Refuerza la observación 1: hace falta una vía para que este tipo de regla, una vez extraída del manual, llegue al prompt o al `business_rules.json` del `KnowledgeStore` (que ya tiene el formato adecuado — ver `add_business_rule()` — solo falta la fuente).

---

## Pendiente de sintetizar

Aún no se propone una optimización concreta — se sigue recopilando evidencia con cada módulo del manual y cada tanda de tests ejecutada. Cuando haya suficiente cobertura (varios módulos + resultados reales de ejecución, no solo diseño), esta sección pasará a contener la propuesta priorizada de cambios por fase.
