"""Debug del test 4.1 exactamente como lo hace el test."""
from collections import defaultdict
from backend.modules.db_explorer.context_retriever import ContextRetriever
from backend.modules.db_explorer.constants import PrivacyConfig

r = ContextRetriever()
r._table_index = {
    "CLIENTE": {
        "cat": "maestros",
        "desc": "Maestro de clientes",
        "n": 3200,
        "pk": ["CODCLI"],
        "cols_key": ["CODCLI", "NOMBRE", "CIUDAD", "PROVINCIA"],
        "related": ["DOCCAB"],
        "kw": ["cliente"]
    },
    "USUARIO": {
        "cat": "seguridad",
        "desc": "Usuarios del sistema",
        "n": 50,
        "pk": ["CODUSUARIO"],
        "cols_key": ["CODUSUARIO", "NOMBRE", "ROL"],
        "related": [],
        "kw": ["usuario"]
    }
}
r._concept_index = {
    "cliente": ["CLIENTE"],
    "usuario": ["USUARIO"],
}
r._graph_adj = defaultdict(set)
r._value_index = {}
r._loaded = True

ctx, meta = r.get_context("clientes de Madrid")
ctx_upper = ctx.upper()
sensibles = PrivacyConfig.SENSITIVE_COLUMNS
violaciones = [col for col in sensibles if col in ctx_upper]

print("Violaciones:", violaciones)
print("Meta:", meta)
print()
print("Contexto completo:")
print(repr(ctx))
