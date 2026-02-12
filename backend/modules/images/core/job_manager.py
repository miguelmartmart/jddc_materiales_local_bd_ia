import logging
# DEVIA: backend/modules/images/core/DEVIA.md
import asyncio
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from ..schemas import JobStatus, ImageJobType
from ..config.manager import ConfigurationManager
from ..providers.base import BaseImageProvider

logger = logging.getLogger(__name__)

# Basic in-memory storage for jobs
_JOBS: Dict[str, Dict] = {}
MAX_SEMANTIC_RETRIES = 2
MAX_TECHNICAL_RETRIES = 2

class JobManager:
    """
    Orchestrates image generation jobs.
    """
    
    def __init__(self, config_manager: ConfigurationManager, provider: BaseImageProvider, planner=None, verifier=None):
        self.config = config_manager
        self.provider = provider
        self.planner = planner
        self.verifier = verifier
        pool_size = self.config.get_provider_config().get("pool_size", 1)
        self._semaphore = asyncio.Semaphore(pool_size)
    
    async def create_job(self, job_type: ImageJobType, params: Dict, user_id: str = "system") -> str:
        job_id = str(uuid.uuid4())
        
        job_record = {
            "job_id": job_id,
            "type": job_type,
            "status": JobStatus.PENDING,
            "created_at": datetime.now().timestamp(),
            "params": params,
            "user_id": user_id,
            "provider": "comfyui_local",
            "files": []
        }
        
        _JOBS[job_id] = job_record
        asyncio.create_task(self._process_job(job_id))
        return job_id

    async def get_job(self, job_id: str) -> Optional[Dict]:
        return _JOBS.get(job_id)

    async def _process_job(self, job_id: str):
        job = _JOBS.get(job_id)
        if not job:
            return

        async with self._semaphore:
            logger.info(f"[JOB MANAGER] Starting job {job_id}")
            job["status"] = JobStatus.RUNNING
            job["started_at"] = datetime.now().timestamp()
            
            try:
                # Dispatch to provider
                if job["type"] == ImageJobType.DESCRIBE:
                    result = await self.provider.describe_image(job)
                    job["result"] = result
                else: 
                     
                     # --- ROBUST EXECUTION LOOP ---
                     current_params = job["params"]
                     final_files = []
                     
                     for attempt in range(MAX_SEMANTIC_RETRIES + 1):
                         try:
                            logger.info(f"[JOB MANAGER] 🔄 Attempt {attempt+1}/{MAX_SEMANTIC_RETRIES + 1} for Job {job_id}")
                            
                            # 1. Technical Execution (with internal technical retries)
                            submit_result = None
                            tech_success = False
                            for tech_attempt in range(MAX_TECHNICAL_RETRIES + 1):
                                try:
                                    submit_result = await self.provider.submit_job(job_id, current_params)
                                    # Poll
                                    max_poll = 30
                                    files = []
                                    for _ in range(max_poll):
                                        await asyncio.sleep(2)
                                        status_res = await self.provider.get_job_status(submit_result)
                                        if isinstance(status_res, tuple):
                                             status, files = status_res
                                        else:
                                             status = status_res
                                        
                                        if status == JobStatus.COMPLETED:
                                            tech_success = True
                                            break
                                        if status == JobStatus.FAILED:
                                            raise Exception("Provider reported failure")
                                    if tech_success:
                                        break
                                except Exception as tech_e:
                                    logger.warning(f"[JOB MANAGER] Technical Retry {tech_attempt}: {tech_e}")
                                    await asyncio.sleep(2)
                            
                            if not tech_success:
                                raise Exception("Max technical retries exceeded")
                                
                            # 2. Semantic Verification
                            final_files = files
                            if self.verifier and files:
                                # Verify the first image
                                # TODO: Handle multiple candidates
                                image_path = files[0]
                                report = await self.verifier.verify_image(image_path, current_params)
                                
                                if report.get("verification_passed", True):
                                    logger.info(f"[JOB MANAGER] ✅ Verification Passed for Attempt {attempt+1}")
                                    break
                                else:
                                    logger.warning(f"[JOB MANAGER] ❌ Verification Failed: {report.get('issues')}")
                                    
                                    if attempt < MAX_SEMANTIC_RETRIES:
                                        # 3. Repair Plan
                                        if self.planner:
                                            logger.info("[JOB MANAGER] 🔧 Repairing Plan...")
                                            # We need original prompt. Where is it?
                                            # Plan doesn't store original prompt in params usually. 
                                            # We assume params has enough info or 'intent_summary'.
                                            # For now, simplistic repair
                                            
                                            # TODO: Call self.planner.repair_plan(current_params, report)
                                            # Stub for simplistic repair:
                                            if "issues" in report:
                                                 issues = report["issues"]
                                                 # Naive injection
                                                 current_params["positive_prompt"] += f", {', '.join(issues)} enforced"
                                                 current_params["seed_policy"] = "randomize" # Change seed
                                    else:
                                         logger.error("[JOB MANAGER] Max semantic retries reached. Accepting result despite failure.")
                            else:
                                # No verifier, assume success
                                break

                         except Exception as logic_e:
                             logger.error(f"[JOB MANAGER] Semantic Attempt Failed: {logic_e}")
                             if attempt == MAX_SEMANTIC_RETRIES:
                                 raise logic_e
                     
                     job["result_data"] = {"provider_id": submit_result, "files": final_files}
                
                job["status"] = JobStatus.COMPLETED
                job["finished_at"] = datetime.now().timestamp()
                
            except Exception as e:
                logger.error(f"[JOB MANAGER] Job {job_id} failed: {e}")
                job["status"] = JobStatus.FAILED
                job["error"] = str(e)
                job["finished_at"] = datetime.now().timestamp()
