"""Diagnóstico: qué columna sensible aparece en el contexto del ContextRetriever."""
from backend.modules.db_explorer.context_retriever import ContextRetriever
from backend.modules.db_explorer.constants import PrivacyConfig

r = ContextRetriever()
ctx, meta = r.get_context("clientes de Madrid")
ctx_upper = ctx.upper()
sensibles = PrivacyConfig.SENSITIVE_COLUMNS

violaciones = [col for col in sensibles if col in ctx_upper]
print("Violaciones encontradas:", violaciones)
print()
print("Contexto completo:")
print(ctx)
print()
print("Meta:", meta)
