"""
progress_tracker.py — Tracker de progreso de peticiones IA en tiempo real

PRINCIPIO DEVIA — Ultra-resiliente:
  - Singleton thread-safe (asyncio.Lock)
  - TTL automático: las entradas se limpian tras 10 minutos
  - Sin dependencias externas (solo stdlib)
  - El frontend hace polling GET /api/chat/progress/{request_id}
  - El backend reporta fases con tracker.add_phase(request_id, fase, detalle)

Flujo:
  1. ChatService genera un request_id único al inicio de cada petición
  2. ChatService llama a tracker.add_phase() en cada fase del procesamiento
  3. El frontend hace polling cada 2s a /api/chat/progress/{request_id}
  4. El frontend muestra las fases en el bubble "Pensando..."
  5. Al terminar, ChatService llama a tracker.finish(request_id)
  6. El frontend deja de hacer polling cuando recibe finished=True
"""

import asyncio
import time
import uuid
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

# TTL en segundos para limpiar entradas antiguas
_TTL_SECONDS = 600  # 10 minutos


class ProgressEntry:
    """Entrada de progreso para una petición IA."""

    def __init__(self, request_id: str):
        self.request_id = request_id
        self.phases: List[Dict[str, Any]] = []
        self.finished: bool = False
        self.success: Optional[bool] = None
        self.created_at: float = time.time()
        self.updated_at: float = time.time()

    def add_phase(self, phase: str, detail: str = "", icon: str = "⚙️") -> None:
        self.phases.append({
            "phase": phase,
            "detail": detail,
            "icon": icon,
            "ts": time.time(),
        })
        self.updated_at = time.time()

    def finish(self, success: bool = True) -> None:
        self.finished = True
        self.success = success
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "phases": self.phases,
            "finished": self.finished,
            "success": self.success,
            "phase_count": len(self.phases),
        }

    def is_expired(self) -> bool:
        return time.time() - self.updated_at > _TTL_SECONDS


class ProgressTracker:
    """
    Singleton thread-safe para rastrear el progreso de peticiones IA.

    Uso en el backend:
        from backend.modules.chat.progress_tracker import tracker

        request_id = tracker.new_request()
        tracker.add_phase(request_id, "🧠 Clasificando intención...", "DB_QUERY")
        tracker.add_phase(request_id, "🔍 Explorando tablas...", "DOCCAB, DOCLIN")
        tracker.finish(request_id, success=True)
    """

    _instance: Optional["ProgressTracker"] = None
    _lock: asyncio.Lock = None

    def __new__(cls) -> "ProgressTracker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._entries: Dict[str, ProgressEntry] = {}
            cls._instance._sync_lock = __import__("threading").Lock()
        return cls._instance

    def new_request(self) -> str:
        """Crea una nueva entrada de progreso y devuelve el request_id."""
        request_id = str(uuid.uuid4())[:12]  # ID corto para URLs
        with self._sync_lock:
            self._entries[request_id] = ProgressEntry(request_id)
            self._cleanup_expired()
        logger.debug(f"[ProgressTracker] Nueva petición: {request_id}")
        return request_id

    def add_phase(self, request_id: str, phase: str, detail: str = "", icon: str = "") -> None:
        """
        Añade una fase de progreso a la petición.

        Args:
            request_id: ID de la petición (devuelto por new_request())
            phase: Texto de la fase (ej: "🧠 Clasificando intención...")
            detail: Detalle adicional (ej: "DB_QUERY (conf=0.98)")
            icon: Emoji/icono (si no está incluido en phase)
        """
        with self._sync_lock:
            entry = self._entries.get(request_id)
            if entry:
                entry.add_phase(phase, detail, icon)
                logger.debug(f"[ProgressTracker] {request_id}: {phase} {detail}")
            else:
                logger.warning(f"[ProgressTracker] request_id no encontrado: {request_id}")

    def finish(self, request_id: str, success: bool = True) -> None:
        """Marca la petición como terminada."""
        with self._sync_lock:
            entry = self._entries.get(request_id)
            if entry:
                entry.finish(success)
                logger.debug(f"[ProgressTracker] {request_id}: finished (success={success})")

    def get(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Devuelve el estado actual de la petición."""
        with self._sync_lock:
            entry = self._entries.get(request_id)
            if entry:
                return entry.to_dict()
            return None

    def get_since(self, request_id: str, since_index: int = 0) -> Optional[Dict[str, Any]]:
        """
        Devuelve solo las fases nuevas desde el índice dado.
        Útil para polling incremental: el frontend envía el índice de la última
        fase que ya tiene, y el backend devuelve solo las nuevas.
        """
        with self._sync_lock:
            entry = self._entries.get(request_id)
            if not entry:
                return None
            return {
                "request_id": request_id,
                "phases": entry.phases[since_index:],
                "finished": entry.finished,
                "success": entry.success,
                "total_phases": len(entry.phases),
            }

    def _cleanup_expired(self) -> None:
        """Limpia entradas expiradas (llamado internamente con lock ya adquirido)."""
        expired = [rid for rid, e in self._entries.items() if e.is_expired()]
        for rid in expired:
            del self._entries[rid]
        if expired:
            logger.debug(f"[ProgressTracker] Limpiadas {len(expired)} entradas expiradas")


# Singleton global — importar desde cualquier módulo del backend
tracker = ProgressTracker()
