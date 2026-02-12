from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional
import logging
from .service import OutlookService
from .analysis_service import EmailAnalyzer
from backend.core.config.settings import settings

logger = logging.getLogger(__name__)

from .analysis_config import analysis_config

logging.basicConfig(level=logging.INFO)

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
    unread_only: bool = False
    date_filter: str = "all" # all, today, yesterday, week

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
    # Determine date filter (but always respect user's limit)
    date_filter = None
    
    if request.date_filter in ["today", "yesterday", "week", "3days"]:
        date_filter = request.date_filter

    def try_fetch(addr, pwd, server="outlook.office365.com"):
        fetched = service.fetch_recent_emails(
            addr, pwd, 
            limit=request.limit,  # Always use user's limit
            imap_server=server,
            full_content=True,
            date_filter=date_filter
        )
        
        # Filter Logic (Service does date filtering broadly, we refine here if needed)
        filtered = []
        
        for e in fetched:
            # Unread Filter
            if request.unread_only and e.get('is_read'):
                continue
            filtered.append(e)
            
        # Final Slice: Only if NO date filter was applied do we respect the strict numeric limit.
        if not date_filter:
             return filtered[:request.limit]
        return filtered

    emails = []
    source = "outlook"
    final_password = password_to_try
    final_server = "outlook.office365.com"

    # --- 0. FAST PATH: CHECK CACHE ---
    cached = auth_cache.get()
    if cached:
        # Verify if request matches cached email or if request has no email
        req_email = email
        if not req_email or req_email == cached['email']:
            logger.info(f"[AUTH CACHE] ⚡ Using cached credentials for {cached['source']}")
            try:
                emails = service.fetch_recent_emails(
                    cached['email'], 
                    cached['password'], 
                    request.limit, 
                    imap_server=cached['server'] or "outlook.office365.com",
                    full_content=True,
                    date_filter=date_filter
                )
                logger.info("[AUTH CACHE] Success!")
                
                # Filter Logic for Cached Result
                filtered = []
                for e in emails:
                     if request.unread_only and e.get('is_read'): continue
                     filtered.append(e)
                if not date_filter: filtered = filtered[:request.limit]
                emails = filtered

                # Unread/Stats setup for cached path (simplified)
                # We need final_password/server variables for later steps
                final_password = cached['password']
                final_server = cached['server'] or "outlook.office365.com"
                source = cached['source']
                
                # Jump to step 2 directly (using goto? no, just structural if/else block)
                # To avoid restructuring the whole function heavily, I will wrap the legacy logic in "if not emails:"
            except Exception as e:
                logger.warning(f"[AUTH CACHE] Cached credentials failed: {e}. Clearing cache.")
                auth_cache.clear()

    if not emails:
        # Standard Fallback Chain
        try:
            try:
                emails = try_fetch(email, password_to_try)
                auth_cache.set("outlook", email, password_to_try)
            except Exception:
                # Retry with App Password
                if app_password and app_password != primary_password:
                    try:
                        final_password = app_password
                        emails = try_fetch(email, app_password)
                        source = "outlook_app"
                        auth_cache.set("outlook_app", email, app_password)
                    except:
                        # Fallback to Gmail
                         if settings.GMAIL_EMAIL and settings.GMAIL_PASSWORD:
                            final_server = "imap.gmail.com"
                            emails = try_fetch(settings.GMAIL_EMAIL, settings.GMAIL_PASSWORD, server="imap.gmail.com")
                            source = "gmail"
                            final_password = settings.GMAIL_PASSWORD
                            auth_cache.set("gmail", settings.GMAIL_EMAIL, settings.GMAIL_PASSWORD, "imap.gmail.com")
                         else:
                            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 2. Unread Count
    unread = await service.get_unread_count(email, final_password, imap_server=final_server)

    # 3. Analyze
    stats = analyzer.calculate_stats(emails, unread)
    
    # 4. Global Daily Stats (New) - Wrapped in try/except for robustness
    global_daily = []
    try:
        global_daily = service.get_global_daily_stats(email, final_password, days=3)
    except Exception as e:
        logger.error(f"Failed to fetch global daily stats: {e}")
    
    ai_results = await analyzer.analyze_content(emails)
    
    # 5. Global Digest
    global_summary_text = await analyzer.generate_global_digest(ai_results)

    return {
        "success": True,
        "source": source,
        "stats": stats,
        "global_daily": global_daily,
        "global_digest": global_summary_text,
        "analysis": ai_results
    }

class DeepAnalysisRequest(BaseModel):
    subject: str = ""
    sender: str = ""
    body: str

@router.post("/analyze-deep")
async def analyze_deep(request: DeepAnalysisRequest):
    """Endpoint for deep analysis of a single email."""
    try:
        context = f"Asunto: {request.subject}\nRemitente: {request.sender}\nCuerpo: {request.body}"
        analysis = await analyzer.analyze_deeply(context)
        return {"success": True, "analysis": analysis}
    except Exception as e:
        logger.error(f"Deep analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- ATTENTION: AUTHENTICATION CACHE ---
# To avoid repetitive login failures and delays, we cache the last working configuration.
class AuthCache:
    def __init__(self):
        self.source = None
        self.email = None
        self.password = None
        self.server = None
        self.last_success = 0 # Timestamp could be added for expiry

    def set(self, source, email, password, server=None):
        self.source = source
        self.email = email
        self.password = password
        self.server = server
        logger.info(f"[AUTH CACHE] Updated: {source} ({email})")

    def get(self):
        if self.source:
            return {
                "source": self.source,
                "email": self.email,
                "password": self.password,
                "server": self.server
            }
        return None

    def clear(self):
        self.source = None
        self.email = None
        self.password = None
        self.server = None

auth_cache = AuthCache()
# ---------------------------------------

@router.post("/messages")
async def get_messages(request: FetchRequest):
    # Use settings if not provided
    email = request.email or settings.OUTLOOK_EMAIL
    primary_password = request.password or settings.OUTLOOK_PASSWORD
    app_password = settings.OUTLOOK_PASSWORD_APP
    
    # --- 0. FAST PATH: CHECK CACHE ---
    cached = auth_cache.get()
    if cached:
        # Verify if request matches cached email or if request has no email
        req_email = email
        if not req_email or req_email == cached['email']:
            logger.info(f"[AUTH CACHE] ⚡ Using cached credentials for {cached['source']}")
            try:
                emails = service.fetch_recent_emails(
                    cached['email'], 
                    cached['password'], 
                    request.limit, 
                    imap_server=cached['server'] or "outlook.office365.com"
                )
                logger.info("[AUTH CACHE] Success!")
                return {"success": True, "messages": emails, "source": cached['source']}
            except Exception as e:
                logger.warning(f"[AUTH CACHE] Cached credentials failed: {e}. Clearing cache.")
                auth_cache.clear()
                # Continue to normal flow...
    # ---------------------------------

    if not email or (not primary_password and not app_password):
        raise HTTPException(status_code=400, detail="Credentials not provided and not found in settings")

    # Try primary password first (or app_password if primary is missing)
    password_to_try = primary_password or app_password
    
    print(f"DEBUG: Attempting login for {email}")
    
    try:
        try:
            emails = service.fetch_recent_emails(email, password_to_try, request.limit)
            print("DEBUG: Login successful!")
            auth_cache.set("outlook", email, password_to_try) # Update Cache
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
                    auth_cache.set("outlook_app", email, app_password) # Update Cache
                    return {"success": True, "messages": emails, "source": "outlook_app"}
                except Exception as retry_e:
                    print(f"DEBUG: Retry also failed: {retry_e}")
                    
                    
                    # ---------------------
                    # HYBRID AUTH: Outlook Server + Gmail Creds
                    # ---------------------
                    gmail_email = settings.GMAIL_EMAIL
                    gmail_password = settings.GMAIL_PASSWORD
                    
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
                            auth_cache.set("outlook_hybrid", gmail_email, gmail_password) # Update Cache
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
                            auth_cache.set("gmail", gmail_email, gmail_password, "imap.gmail.com") # Update Cache
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
                        auth_cache.set("gmail", settings.GMAIL_EMAIL, settings.GMAIL_PASSWORD, "imap.gmail.com") # Update Cache
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

class ReplyRequest(BaseModel):
    content: str
    sender: str

@router.post("/reply-suggestion")
async def generate_reply(request: ReplyRequest):
    suggestion = await analyzer.generate_reply_suggestion(request.content, request.sender)
    return {"success": True, "reply": suggestion}

class AttachmentAnalysisRequest(BaseModel):
    email_id: str
    attachment_index: int
    email_address: str
    password: str

@router.post("/analyze-attachment")
async def analyze_attachment(request: AttachmentAnalysisRequest):
    """Analyze a specific attachment from an email."""
    from backend.modules.outlook.attachment_analyzer import attachment_analyzer
    
    try:
        # Use same 3-step authentication logic as messages endpoint
        email = request.email_address or settings.OUTLOOK_EMAIL
        primary_password = request.password or settings.OUTLOOK_PASSWORD
        app_password = settings.OUTLOOK_PASSWORD_APP
        gmail_email = settings.GMAIL_EMAIL
        gmail_password = settings.GMAIL_PASSWORD
        
        emails = []
        source = "unknown"
        
        # --- 0. FAST PATH: CHECK CACHE ---
        cached = auth_cache.get()
        if cached:
             if not email or email == cached['email']: # logic check
                 try:
                     logger.info(f"[AUTH CACHE] ⚡ Using cached credentials for attachment analysis ({cached['source']})")
                     emails = service.fetch_recent_emails(
                         cached['email'], 
                         cached['password'], 
                         limit=1000, 
                         full_content=True,
                         imap_server=cached['server'] or "outlook.office365.com"
                     )
                     source = cached['source']
                     logger.info("[AUTH CACHE] Success!")
                 except Exception as e:
                     logger.warning(f"[AUTH CACHE] Failed: {e}")
                     auth_cache.clear()
        
        # Step 1: Try Outlook with primary/app password (only if cache missed/failed)
        if not emails and email and (primary_password or app_password):
            password_to_try = app_password if app_password else primary_password
            try:
                logger.info(f"Step 1: Trying Outlook for attachment analysis: {email}")
                emails = service.fetch_recent_emails(email, password_to_try, limit=1000, full_content=True)
                source = "outlook"
                auth_cache.set("outlook", email, password_to_try)
                logger.info(f"Outlook successful, got {len(emails)} emails")
            except Exception as e1:
                logger.warning(f"Step 1 failed: {e1}")
                
                # Step 1b: Retry with app password if different
                if password_to_try == primary_password and app_password and app_password != primary_password:
                    try:
                        logger.info(f"Step 1b: Retrying Outlook with app password")
                        emails = service.fetch_recent_emails(email, app_password, limit=1000, full_content=True)
                        source = "outlook_app"
                        auth_cache.set("outlook_app", email, app_password)
                        logger.info(f"Outlook app password successful, got {len(emails)} emails")
                    except Exception as e1b:
                        logger.warning(f"Step 1b failed: {e1b}")
        
        # Step 2: Try Hybrid (Outlook server + Gmail creds)
        if not emails and gmail_email and gmail_password:
            try:
                logger.info(f"Step 2: Trying HYBRID (Outlook server + Gmail creds): {gmail_email}")
                emails = service.fetch_recent_emails(gmail_email, gmail_password, limit=1000, full_content=True)
                source = "outlook_hybrid"
                auth_cache.set("outlook_hybrid", gmail_email, gmail_password)
                logger.info(f"Hybrid successful, got {len(emails)} emails")
            except Exception as e2:
                logger.warning(f"Step 2 failed: {e2}")
        
        # Step 3: Try Gmail fallback (Gmail server + Gmail creds)
        if not emails and gmail_email and gmail_password:
            try:
                logger.info(f"Step 3: Trying Gmail fallback: {gmail_email}")
                emails = service.fetch_recent_emails(gmail_email, gmail_password, limit=1000, full_content=True, imap_server="imap.gmail.com")
                source = "gmail"
                auth_cache.set("gmail", gmail_email, gmail_password, "imap.gmail.com")
                logger.info(f"Gmail fallback successful, got {len(emails)} emails")
            except Exception as e3:
                logger.warning(f"Step 3 failed: {e3}")
        
        if not emails:
            error_msg = "Could not fetch emails after trying all authentication methods (Outlook, Hybrid, Gmail)"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        logger.info(f"Successfully fetched {len(emails)} emails using {source}")
        
        # Find the specific email by ID
        target_email = None
        for e in emails:
            if e['id'] == request.email_id:
                target_email = e
                break
        
        if not target_email:
            return {"success": False, "error": "Email not found"}
        
        attachments = target_email.get('attachments', [])
        
        if request.attachment_index >= len(attachments):
            return {"success": False, "error": "Attachment index out of range"}
        
        attachment = attachments[request.attachment_index]
        
        if not attachment.get('content'):
            return {"success": False, "error": "Attachment content not available"}
        
        # Decode base64 content
        import base64
        content_bytes = base64.b64decode(attachment['content'])
        
        # Analyze the attachment
        analysis = await attachment_analyzer.analyze_attachment(
            content_bytes,
            attachment['filename'],
            attachment['content_type']
        )
        
        return {
            "success": True,
            "filename": attachment['filename'],
            "content_type": attachment['content_type'],
            "size": attachment['size'],
            "analysis": analysis
        }
        
    except Exception as e:
        logger.error(f"Error analyzing attachment: {e}")
        return {"success": False, "error": str(e)}

# --- EXCLUSION CONFIG API ---

@router.get("/config/exclusions")
async def get_exclusions():
    return analysis_config.get_exclusions()

class ExclusionRule(BaseModel):
    type: str # sender, subject_contains
    value: str
    enabled: bool = True

@router.post("/config/exclusions")
async def add_exclusion(rule: ExclusionRule):
    new_rule = analysis_config.add_exclusion(rule.dict())
    return {"success": True, "rule": new_rule}

@router.delete("/config/exclusions/{rule_id}")
async def remove_exclusion(rule_id: str):
    analysis_config.remove_exclusion(rule_id)
    return {"success": True}

