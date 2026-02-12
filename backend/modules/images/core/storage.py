import os
import aiofiles
import hashlib
import shutil
import logging
from typing import Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class LocalStorageManager:
    """
    Manages local file storage for Image Services.
    Handles saving, retrieving, and organizing image files.
    """
    
    def __init__(self, base_path: str = "data/images"):
        # Resolve absolute path relative to project root
        # Assuming run from root
        self.base_path = os.path.abspath(base_path)
        self.ensure_directories()
        
    def ensure_directories(self):
        """Creates necessary subdirectories."""
        os.makedirs(os.path.join(self.base_path, "input"), exist_ok=True)
        os.makedirs(os.path.join(self.base_path, "output"), exist_ok=True)
        os.makedirs(os.path.join(self.base_path, "temp"), exist_ok=True)

    def _get_date_path(self) -> str:
        """Returns YYYY/MM/DD path segment."""
        return datetime.now().strftime("%Y/%m/%d")

    async def save_file(self, content: bytes, mime_type: str, job_id: str, role: str) -> str:
        """
        Saves bytes to disk.
        Returns the relative path to the file.
        """
        # Generate hash for deduplication/naming
        file_hash = hashlib.sha256(content).hexdigest()
        ext = mime_type.split('/')[-1] if '/' in mime_type else 'bin'
        filename = f"{job_id}_{role}_{file_hash[:8]}.{ext}"
        
        # Organize by date
        date_path = self._get_date_path()
        relative_dir = os.path.join(role, date_path)
        full_dir = os.path.join(self.base_path, relative_dir)
        os.makedirs(full_dir, exist_ok=True)
        
        full_path = os.path.join(full_dir, filename)
        
        async with aiofiles.open(full_path, 'wb') as f:
            await f.write(content)
            
        logger.info(f"[STORAGE] File saved: {full_path}")
        return os.path.join(relative_dir, filename).replace('\\', '/')

    def get_absolute_path(self, relative_path: str) -> str:
        """Converts relative storage path to absolute system path."""
        # Security check: ensure path is within base_path
        full_path = os.path.abspath(os.path.join(self.base_path, relative_path))
        if not full_path.startswith(self.base_path):
            raise ValueError(f"Security: Path traversal attempt detected: {relative_path}")
        return full_path
