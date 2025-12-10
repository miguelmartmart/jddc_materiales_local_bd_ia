from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional
from .service import OutlookService
from .analysis_service import EmailAnalyzer
from backend.core.config.settings import settings

router = APIRouter(prefix="/api/outlook", tags=["Outlook"])
service = OutlookService()
analyzer = EmailAnalyzer()

class ConnectionRequest(BaseModel):
    email: str
    password: str

class FetchRequest(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    limit: int = 5

@router.post("/test-connection")
async def test_connection(request: ConnectionRequest):
    success = service.test_connection(request.email, request.password)
    if not success:
        raise HTTPException(status_code=401, detail="Authentication failed or connection error")
    return {"success": True, "message": "Connected successfully"}

@router.post("/analyze")
async def analyze_emails(request: FetchRequest):
    # Reuse credential logic (TODO: refactor into dependency if time permits)
    email = request.email or settings.OUTLOOK_EMAIL
    primary_password = request.password or settings.OUTLOOK_PASSWORD
    app_password = settings.OUTLOOK_PASSWORD_APP
    
    if not email or (not primary_password and not app_password):
        raise HTTPException(status_code=400, detail="Credenciales no encontradas")

    password_to_try = primary_password or app_password
    
    # 1. Fetch Emails (Full Content)
    # We use a similar fallback logic to get_messages but streamlined for brevity in this snippet
    # If get_messages logic is complex, we should extract it. 
    # For now, let's assume the happy path or simple retry matches get_messages.
    
    # helper to fetch
    def try_fetch(e, p, server="outlook.office365.com"):
        return service.fetch_recent_emails(e, p, request.limit, imap_server=server, full_content=True)

    emails = []
    source = "outlook"
    final_password = password_to_try
    final_server = "outlook.office365.com"

    try:
        try:
            emails = try_fetch(email, password_to_try)
        except Exception:
            # Retry with App Password
            if app_password and app_password != primary_password:
                try:
                    final_password = app_password
                    emails = try_fetch(email, app_password)
                    source = "outlook_app"
                except:
                    # Fallback to Gmail
                     if settings.GMAIL_EMAIL and settings.GMAIL_PASSWORD:
                        final_server = "imap.gmail.com"
                        emails = try_fetch(settings.GMAIL_EMAIL, settings.GMAIL_PASSWORD, server="imap.gmail.com")
                        source = "gmail"
                        # Reset for unread count check
                        email = settings.GMAIL_EMAIL 
                        final_password = settings.GMAIL_PASSWORD
                     else:
                        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 2. Unread Count
    unread = await service.get_unread_count(email, final_password, imap_server=final_server)

    # 3. Analyze
    stats = analyzer.calculate_stats(emails, unread)
    ai_results = await analyzer.analyze_content(emails)

    return {
        "success": True,
        "source": source,
        "stats": stats,
        "analysis": ai_results
    }

@router.post("/messages")
async def get_messages(request: FetchRequest):
    # Use settings if not provided
    email = request.email or settings.OUTLOOK_EMAIL
    primary_password = request.password or settings.OUTLOOK_PASSWORD
    app_password = settings.OUTLOOK_PASSWORD_APP

    if not email or (not primary_password and not app_password):
        raise HTTPException(status_code=400, detail="Credentials not provided and not found in settings")

    # Try primary password first (or app_password if primary is missing)
    password_to_try = primary_password or app_password
    
    print(f"DEBUG: Attempting login for {email}")
    print(f"DEBUG: Using primary/provided password? {'Yes' if password_to_try == primary_password else 'No'}")
    print(f"DEBUG: App password available? {'Yes' if app_password else 'No'}")

    try:
        try:
            emails = service.fetch_recent_emails(email, password_to_try, request.limit)
            print("DEBUG: Login successful!")
            return {"success": True, "messages": emails, "source": "outlook"}
        except Exception as e:
            # Check if it is an auth error and we have a fallback password
            err_msg = str(e)
            print(f"DEBUG: First attempt failed. Error: {err_msg}")
            
            is_auth_error = "Error de autenticación" in err_msg or "LOGIN failed" in err_msg
            
            # If we used primary, and failed, and have a different app password available
            if is_auth_error and password_to_try == primary_password and app_password and app_password != primary_password:
                print(f"DEBUG: Primary password failed. Retrying with App Password...") # Log to console
                try:
                    emails = service.fetch_recent_emails(email, app_password, request.limit)
                    print("DEBUG: Retry successful!")
                    return {"success": True, "messages": emails, "source": "outlook_app"}
                except Exception as retry_e:
                    print(f"DEBUG: Retry also failed: {retry_e}")
                    
                    
                    # ---------------------
                    # HYBRID AUTH: Outlook Server + Gmail Creds
                    # ---------------------
                    gmail_email = settings.GMAIL_EMAIL
                    gmail_password = settings.GMAIL_PASSWORD
                    
                    hybrid_success = False
                    
                    if gmail_email and gmail_password:
                        print(f"DEBUG: Attempting HYBRID Auth (Outlook Server + Gmail Creds)...")
                        try:
                            emails = service.fetch_recent_emails(
                                gmail_email, 
                                gmail_password, 
                                request.limit
                                # imap_server defaults to outlook
                            )
                            print("DEBUG: Hybrid Auth successful!")
                            return {"success": True, "messages": emails, "source": "outlook_hybrid"}
                        except Exception as hybrid_e:
                            print(f"DEBUG: Hybrid Auth failed: {hybrid_e}")
                            # Continue to Gmail Fallback
                    
                    # ---------------------
                    # GMAIL FALLBACK
                    # ---------------------
                    
                    if gmail_email and gmail_password:
                        print(f"DEBUG: Attempting GMAIL Fallback for {gmail_email}...")
                        try:
                            # Using imap.gmail.com
                            emails = service.fetch_recent_emails(
                                gmail_email, 
                                gmail_password, 
                                request.limit,
                                imap_server="imap.gmail.com"
                            )
                            print("DEBUG: Gmail Fallback successful!")
                            return {"success": True, "messages": emails, "source": "gmail"}
                        except Exception as gmail_e:
                            print(f"DEBUG: Gmail Fallback failed: {gmail_e}")
                            raise gmail_e
                    else:
                        print("DEBUG: No Gmail credentials configured.")
                        raise retry_e
            else:
                # If primary failed and no app password, OR if it wasn't an auth error
                # Check Gmail fallback directly here too? 
                # Simplification: Only fallback to Gmail if Outlook failed AUTH.
                if is_auth_error and settings.GMAIL_EMAIL and settings.GMAIL_PASSWORD:
                     print(f"DEBUG: Outlook Auth failed. Fallback to GMAIL {settings.GMAIL_EMAIL}...")
                     try:
                        emails = service.fetch_recent_emails(
                            settings.GMAIL_EMAIL, 
                            settings.GMAIL_PASSWORD, 
                            request.limit,
                            imap_server="imap.gmail.com"
                        )
                        print("DEBUG: Gmail Fallback successful!")
                        return {"success": True, "messages": emails, "source": "gmail"}
                     except Exception as gmail_e:
                        print(f"DEBUG: Gmail Fallback failed: {gmail_e}")
                        raise gmail_e

                print("DEBUG: No retry conditions met.")
                raise e # Re-raise if no fallback or different error
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config-status")
async def get_config_status():
    """Returns whether Outlook is configured in settings."""
    return {
        "configured": bool(settings.OUTLOOK_EMAIL and settings.OUTLOOK_PASSWORD),
        "email": settings.OUTLOOK_EMAIL if settings.OUTLOOK_EMAIL else None
    }
