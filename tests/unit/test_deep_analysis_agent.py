"""
test_deep_analysis_agent.py — Re-exportador de compatibilidad.

Este fichero existía con 2205 líneas y fue dividido en:
  - test_deep_analysis_1_core.py      (475)  TestDetectDepth..TestHelpers
  - test_deep_analysis_2_phases.py    (429)  TestPhase0..TestPhase3ResponseNone
  - test_deep_analysis_3_learn.py     (372)  TestPhase4bLearnAndPersist
  - test_deep_analysis_4_advanced.py  (306)  TestFixedSQLsEstadoPend..TestSIUOMetadataHelpers
  - test_deep_analysis_5_knowledge.py (361)  TestBuildWarnings..TestFixedSQLsEstadoPendVenCom
  - test_deep_analysis_6_knowledge2.py(255)  TestPhase2KnowledgeStoreCache..Persistence
  - test_deep_analysis_7_knowledge3.py(373)  TestPhase4bEstadoPendVenCom

pytest descubre automáticamente todos los ficheros test_*.py — no es necesario
importar nada aquí. Este fichero existe solo para compatibilidad con referencias
directas al módulo original.
"""

# Re-exportar todas las clases de test para compatibilidad con imports directos
from tests.unit.test_deep_analysis_1_core import (
    TestDetectDepth,
    TestTokenBudget,
    TestPhase1Fallback,
    TestPhase2Exploration,
    TestPhase3FixedSQLs,
    TestPhase4SIUOFeedback,
    TestEmergencyFallback,
    TestFullAnalysisMock,
    TestHelpers,
)
from tests.unit.test_deep_analysis_2_phases import (
    TestPhase0LanOptimize,
    TestBuildPhase3System,
    TestGetKnownPatternsText,
    TestPhase3ResponseNone,
)
from tests.unit.test_deep_analysis_3_learn import (
    TestPhase4bLearnAndPersist,
    TestFixedSQLsEstadoPend,
)
from tests.unit.test_deep_analysis_4_advanced import (
    TestSIUOMetadataHelpers,
)
from tests.unit.test_deep_analysis_5_knowledge import (
    TestBuildWarningsMarkdown,
    TestStripHtmlFromMarkdown,
    TestFixedSQLsEstadoPendVenCom,
)
from tests.unit.test_deep_analysis_6_knowledge2 import (
    TestPhase2KnowledgeStoreCache,
)
from tests.unit.test_deep_analysis_7_knowledge3 import (
    TestPhase2KnowledgeStorePersistence,
    TestPhase4bEstadoPendVenCom,
)

__all__ = [
    "TestDetectDepth", "TestTokenBudget", "TestPhase1Fallback",
    "TestPhase2Exploration", "TestPhase3FixedSQLs", "TestPhase4SIUOFeedback",
    "TestEmergencyFallback", "TestFullAnalysisMock", "TestHelpers",
    "TestPhase0LanOptimize", "TestBuildPhase3System", "TestGetKnownPatternsText",
    "TestPhase3ResponseNone", "TestPhase4bLearnAndPersist",
    "TestFixedSQLsEstadoPend", "TestSIUOMetadataHelpers",
    "TestBuildWarningsMarkdown", "TestStripHtmlFromMarkdown",
    "TestFixedSQLsEstadoPendVenCom",
    "TestPhase2KnowledgeStoreCache", "TestPhase2KnowledgeStorePersistence",
    "TestPhase4bEstadoPendVenCom",
]
