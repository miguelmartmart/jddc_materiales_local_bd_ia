"""
pipeline_config.py — Configuración centralizada del pipeline de chat.

PRINCIPIOS DEVIA:
  - ÚNICA FUENTE DE VERDAD para todos los parámetros del pipeline
  - Sin hardcoding en los módulos de fase
  - Activación/desactivación de fases por config
  - Cargado desde config.json si existe, con defaults seguros

Estructura de config.json (sección "pipeline"):
  {
    "pipeline": {
      "phase0_safety": { "enabled": true, "use_ai": true, "ai_timeout_s": 5 },
      "phase4_formatter": { "enabled": true, "use_ai": true, "ai_timeout_s": 8 }
    }
  }
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ── Ruta al config.json del módulo chat ──────────────────────────────────────
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")


@dataclass
class PhaseConfig:
    """Configuración de una fase del pipeline."""
    enabled: bool = True        # Si False, la fase se salta completamente
    use_ai: bool = True         # Si False, solo usa lógica determinista
    ai_timeout_s: int = 5       # Timeout para llamadas IA en esta fase
    log_level: str = "INFO"     # Nivel de log para esta fase


@dataclass
class PipelineConfig:
    """Configuración completa del pipeline de chat."""
    phase0_safety: PhaseConfig = field(default_factory=lambda: PhaseConfig(
        enabled=True, use_ai=True, ai_timeout_s=5
    ))
    phase4_formatter: PhaseConfig = field(default_factory=lambda: PhaseConfig(
        enabled=True, use_ai=True, ai_timeout_s=8
    ))

    @classmethod
    def load(cls) -> "PipelineConfig":
        """
        Carga la configuración desde config.json.
        Si no existe o falla, usa defaults seguros.
        Principio DEVIA: fallback determinista siempre.
        """
        cfg = cls()
        try:
            path = os.path.normpath(_CONFIG_PATH)
            if not os.path.exists(path):
                logger.debug(f"[PIPELINE] config.json no encontrado en {path}, usando defaults")
                return cfg
            with open(path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
            pipeline_data = data.get("pipeline", {})
            if not pipeline_data:
                return cfg

            def _load_phase(key: str, default: PhaseConfig) -> PhaseConfig:
                raw = pipeline_data.get(key, {})
                if not isinstance(raw, dict):
                    return default
                return PhaseConfig(
                    enabled=bool(raw.get("enabled", default.enabled)),
                    use_ai=bool(raw.get("use_ai", default.use_ai)),
                    ai_timeout_s=int(raw.get("ai_timeout_s", default.ai_timeout_s)),
                    log_level=str(raw.get("log_level", default.log_level)),
                )

            cfg.phase0_safety = _load_phase("phase0_safety", cfg.phase0_safety)
            cfg.phase4_formatter = _load_phase("phase4_formatter", cfg.phase4_formatter)
            logger.info(
                f"[PIPELINE] Config cargada: "
                f"safety={'ON' if cfg.phase0_safety.enabled else 'OFF'} "
                f"formatter={'ON' if cfg.phase4_formatter.enabled else 'OFF'}"
            )
        except Exception as e:
            logger.warning(f"[PIPELINE] Error cargando config: {e} — usando defaults")
        return cfg


# ── Singleton cargado al importar el módulo ───────────────────────────────────
_pipeline_config: PipelineConfig | None = None


def get_pipeline_config() -> PipelineConfig:
    """Devuelve la configuración del pipeline (singleton, recargable)."""
    global _pipeline_config
    if _pipeline_config is None:
        _pipeline_config = PipelineConfig.load()
    return _pipeline_config


def reload_pipeline_config() -> PipelineConfig:
    """Fuerza recarga de la configuración desde disco."""
    global _pipeline_config
    _pipeline_config = PipelineConfig.load()
    return _pipeline_config
