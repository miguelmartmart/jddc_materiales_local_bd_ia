from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from typing import Dict, Any
from .service import ImageService
from .schemas import GenerateRequest, JobCreatedResponse, JobResponse

router = APIRouter()
service = ImageService()

@router.post("/generate", response_model=JobCreatedResponse)
async def generate_image(request: GenerateRequest):
    """
    Submits a Text-to-Image generation job.
    """
    try:
        return await service.generate_image(request, user_id="system")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    """
    Get the status of a job.
    """
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/config/presets")
async def get_presets():
    """
    Get available configuration presets.
    """
    # This would come from config manager
    return {"presets": ["fast", "quality", "hd"]}

@router.get("/files/{folder}/{filename}")
async def get_image_file(folder: str, filename: str):
    """
    Serve image files from storage.
    """
    from fastapi.responses import FileResponse
    import os
    
    # Security check: folder provided must be one of allowed
    if folder not in ["output", "temp", "input"]:
        raise HTTPException(status_code=400, detail="Invalid folder")
    
    # Get absolute path from storage manager logic
    # We can reuse LocalStorageManager or just construct it securely
    # Assuming data/images structure relative to project root
    # Project root is ../../../../ from here? No, let's use service.storage
    
    try:
        # Re-using service storage manager would be cleaner but it's initialized in service
        # Let's use service.storage.get_absolute_path logic if possible, or just build it here
        # Service instance is available globally in this module
        
        # We need relative path to storage root. 
        # service.storage stores in data/images/{folder}/...
        # But get_absolute_path expects a relative path like "output/filename"
        
        # Searching recursively if needed? No, LocalStorageManager saves with date folders usually.
        # Wait, LocalStorageManager.save_file returns path like "temp/2026/01/14/file.jpg"
        # If the ChatService link logic uses "output/{filename}", we assume flat structure or filename includes path?
        # ComfyUI output (from my simple logic) might be just flat in "output" or date based.
        # ComfyUI usually saves to its own output folder.
        # Wait! ComfyUI saves to ITS OWN folder. My LocalStorageManager manages "data/images".
        # ComfyUIProvider currently relies on ComfyUI hosting the file?
        # NO. ComfyUI API `/view` serves images.
        # If I want to serve them via MY backend, I have two choices:
        # 1. Proxy the image from ComfyUI (safer if ComfyUI is local only).
        # 2. Move/Copy the image from ComfyUI output to my data/images folder.
        
        # Given "Server Unificado", and ComfyUI is a separate process.
        # Simplest approach for "Integration" phase:
        # ComfyUI API serves images at `http://127.0.0.1:8188/view?filename=...`
        # I should probably just return THAT URL if reachable by user, OR proxy it.
        # If User is accessing "Server Unificado" remotely, they can't reach localhost:8188.
        # So I MUST proxy it.
        
        # Let's adjust this endpoint to PROXY from ComfyUI if the file is not found locally.
        # OR, simpler: Modify ComfyUIProvider to DOWNLOAD the image and save it to `data/images/output`.
        
        # PLAN CHANGE: 
        # 1. Provide endpoint here to serve local files.
        # 2. Update ComfyUIProvider (in previous step I did get_job_status) to DOWNLOAD the file.
        # Wait, I did NOT implement download in ComfyUIProvider. I just extracted filename.
        
        # So I will implement the endpoint to proxy/fetch from ComfyUI for now?
        # No, better: "ComfyUIProvider" should ensure the file is in our storage.
        # But for now, let's implement the Proxy endpoint to ComfyUI.
        pass
        
    except Exception:
        pass

    # Quick Proxy Implementation
    import aiohttp
    from fastapi.responses import StreamingResponse
    
    comfy_url = f"http://127.0.0.1:8188/view?filename={filename}&type=output"
    
    async def iterfile():
        async with aiohttp.ClientSession() as session:
            async with session.get(comfy_url) as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=404, detail="Image not found in ComfyUI")
                async for chunk in resp.content.iter_chunked(1024):
                    yield chunk
                    
    return StreamingResponse(iterfile(), media_type="image/png")
