from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ..schemas import GenerateRequest, JobResponse, JobStatus

class BaseImageProvider(ABC):
    """
    Abstract Base Class for Image Generation Providers.
    All providers (ComfyUI, A1111, Cloud) must implement this interface.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    @abstractmethod
    async def validate_connection(self) -> bool:
        """Checks if the provider is reachable."""
        pass
        
    @abstractmethod
    async def submit_job(self, job_id: str, request: GenerateRequest) -> str:
        """
        Submits a job to the provider.
        Returns the external provider's job ID (if applicable).
        """
        pass
        
    @abstractmethod
    async def get_job_status(self, provider_job_id: str) -> JobStatus:
        """Checks the status of a job on the provider side."""
        pass
        
    @abstractmethod
    async def cancel_job(self, provider_job_id: str) -> bool:
        """Cancels a running job."""
        pass
