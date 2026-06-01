from fastapi import APIRouter, HTTPException
# DEVIA: backend/modules/chat/DEVIA.md
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import json
from backend.modules.chat.service import ChatService
from backend.modules.chat.chat_history_service import ChatHistoryService

router = APIRouter()
service = ChatService()
history_service = ChatHistoryService()

class ChatRequest(BaseModel):
    message: str
    db_params: Optional[Dict[str, Any]] = None
    model_id: Optional[str] = "groq-llama-70b"
    conversation_history: Optional[List[Dict[str, str]]] = []  # Lista de mensajes anteriores
    confirm_data_sending: Optional[bool] = None  # None = auto-confirm (Android/voice), False = web pending confirmation, True = web confirmed
    images: Optional[List[str]] = None  # Valid Base64 strings
    session_id: Optional[str] = None  # New field for persistence
    deep_analysis: Optional[bool] = False  # 🔬 Checkbox "Análisis Profundo" del frontend
    
class ConfigRequest(BaseModel):
    max_sql_retries: int
    ai_local_only: Optional[bool] = None  # None = no cambiar el valor actual


@router.get("/history")
async def get_history(limit: int = 50):
    """Get recent chat sessions."""
    return history_service.get_recent_sessions(limit)

@router.get("/history/all")
async def get_all_history_json():
    """Get ALL history as JSON for the detailed modal."""
    try:
        sessions = history_service.get_recent_sessions(limit=100) # Limit to last 100 sessions to avoid overload
        data = []
        for session in sessions:
            messages = history_service.get_session_messages(session['id'])
            data.append({
                "session": session,
                "messages": messages
            })
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{session_id}")
async def get_session_details(session_id: str):
    """Get messages for a specific session."""
    try:
        messages = history_service.get_session_messages(session_id)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/history/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session."""
    try:
        history_service.delete_session(session_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config")
async def get_config():
    """Get current chat configuration."""
    try:
        service._load_config() # Refresh
        return service.config
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config")
async def update_config(config: ConfigRequest):
    """Update chat configuration.
    
    Campos:
    - max_sql_retries: número máximo de reintentos SQL
    - ai_local_only: true = solo IA local Qwen3 LAN (sin internet), false = fallback multi-modelo
    """
    try:
        import os
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        
        current = {}
        if os.path.exists(config_path):
             with open(config_path, 'r') as f:
                 current = json.load(f)
        
        current['max_sql_retries'] = config.max_sql_retries
        
        # Solo actualizar ai_local_only si se envió explícitamente (no None)
        if config.ai_local_only is not None:
            current['ai_local_only'] = config.ai_local_only
        
        with open(config_path, 'w') as f:
            json.dump(current, f, indent=4)
            
        service._load_config() # Refresh service
        return {
            "success": True,
            "config": current,
            "ai_mode": "LOCAL_ONLY (Qwen3 LAN)" if current.get('ai_local_only') else "FALLBACK_MULTI_MODEL"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send")
async def send_message(request: ChatRequest):
    try:
        session_id = request.session_id
        
        # 1. Create session if needed
        if not session_id:
            # Use first few chars of message as title
            title = request.message[:30] + "..." if len(request.message) > 30 else request.message
            session_id = history_service.create_session(request.model_id, title)
        
        # 2. Save User Message
        user_meta = {}
        if request.images:
            user_meta['images_count'] = len(request.images)
        
        history_service.add_message(session_id, "user", request.message, user_meta)
        
        # 3. Process with AI
        # Pass the full request dict which includes confirm_data_sending
        response_text = await service.process_message(request.message, request.dict())

        # ── Disclaimer de simulación (server-side) ───────────────────────────
        # Si el simulador está activo, se antepone un aviso claro al usuario
        # para que sepa que los datos NO son de la BD real.
        from backend.modules.db_simulator.manager import simulator_manager as _sim_mgr
        from backend.modules.db_simulator.constants import SimulatorDisclaimer, SimulatorStatus

        if _sim_mgr.is_enabled():
            # Verificar si el simulador tiene datos — si no, mostrar onboarding
            _sim_status = _sim_mgr.get_status()
            _sim_ready = _sim_status.get("status") == SimulatorStatus.READY
            _row_counts = _sim_status.get("row_counts", {})
            _has_data = _sim_ready and bool(_row_counts) and any(v > 0 for v in _row_counts.values())

            if not _has_data:
                # ── ONBOARDING: simulador activo pero sin datos ───────────────
                # El usuario necesita generar datos sintéticos antes de usar el chat.
                # Mostramos los pasos exactos en lugar de un error críptico.
                _total_docs = _row_counts.get("DOCCAB", 0)
                _total_arts = _row_counts.get("ARTICULO", 0)
                _total_cli  = _row_counts.get("CLIENTE", 0)
                response_text = (
                    "<div style='background:#fff3cd;border:1px solid #ffc107;border-radius:8px;"
                    "padding:16px;margin-bottom:12px;font-family:sans-serif'>"
                    "<h3 style='margin:0 0 12px;color:#856404'>⚙️ Configuración necesaria</h3>"
                    "<p style='margin:0 0 10px'>El simulador está <strong>activado</strong> "
                    "pero aún no tiene datos. Sigue estos pasos para usar el chat IA:</p>"
                    "<ol style='margin:0 0 12px;padding-left:20px'>"
                    "<li style='margin-bottom:8px'>"
                    "<strong>✅ Simulador activado</strong> — ya está hecho</li>"
                    "<li style='margin-bottom:8px'>"
                    "<strong>⏳ Generar datos sintéticos</strong> — "
                    "Ve al panel del simulador y pulsa <em>«Generar datos sintéticos»</em>, "
                    "o llama a <code>POST /api/db-simulator/build-synthetic</code> "
                    "(tarda ~2 segundos, no requiere Firebird)</li>"
                    "<li style='margin-bottom:8px'>"
                    "<strong>💬 Usar el chat</strong> — "
                    "Después podrás preguntar cosas como:<br>"
                    "<em>«¿Cuántas facturas hay este mes?»</em>, "
                    "<em>«Dame el top 5 de clientes»</em>, "
                    "<em>«¿Qué artículos tienen stock bajo?»</em></li>"
                    "</ol>"
                    "<p style='margin:0;font-size:0.85em;color:#6c757d'>"
                    "💡 Los datos sintéticos son realistas pero ficticios — "
                    "no se conecta a ningún servidor Firebird real.</p>"
                    "</div>"
                )
            else:
                # Simulador listo — añadir disclaimer normal
                if isinstance(response_text, dict):
                    response_text[SimulatorDisclaimer.JSON_KEY] = SimulatorDisclaimer.JSON_TEXT
                elif isinstance(response_text, str):
                    response_text = _sim_mgr.get_disclaimer(html=True) + response_text
        # ─────────────────────────────────────────────────────────────────────

        # Handle dict response (confirmation) vs string response
        assistant_meta = {}
        final_response_text = response_text

        if isinstance(response_text, dict):
             # It's a structured response (like confirmation required)
             # We might not want to save this to history as a final message yet if it's just a confirmation request
             # But for now, let's treat it as a response
             final_response_text = json.dumps(response_text)
             assistant_meta['is_structured'] = True
        
        # 4. Save Assistant Message
        # Only save if it's a real response or confirmation request, not if it totally failed? 
        # For now, save everything.
        history_service.add_message(session_id, "assistant", final_response_text, assistant_meta)
        
        return {
            "success": True, 
            "response": response_text,
            "session_id": session_id 
        }
    except Exception as e:
        if request.session_id:
             history_service.add_message(request.session_id, "assistant", f"Error: {str(e)}", {"is_error": True})
        return {"success": False, "response": f"Error: {str(e)}"}


from fastapi.responses import HTMLResponse

@router.get("/export-full", response_class=HTMLResponse)
async def export_full_history():
    """Generates a friendly HTML report of all chat history."""
    try:
        # 1. Fetch all sessions (limit 1000)
        sessions = history_service.get_recent_sessions(limit=1000)
        
        html_content = """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Historial Completo Chat IA</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f0f2f5; color: #333; }
                .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
                h1 { color: #1a73e8; border-bottom: 2px solid #e0e0e0; padding-bottom: 15px; }
                .summary { margin-bottom: 30px; padding: 15px; background: #e8f0fe; border-radius: 8px; border: 1px solid #d2e3fc; }
                .session { border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 20px; overflow: hidden; background: #fff; }
                .session-header { background: #f8f9fa; padding: 15px; border-bottom: 1px solid #e0e0e0; display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
                .session-header:hover { background: #f1f3f4; }
                .session-meta { font-size: 0.85em; color: #5f6368; }
                .session-body { padding: 20px; display: none; }
                .session.open .session-body { display: block; }
                .message { margin-bottom: 15px; padding: 10px 15px; border-radius: 8px; max-width: 85%; }
                .message.user { background: #e3f2fd; margin-left: auto; border-bottom-right-radius: 2px; }
                .message.assistant { background: #f1f3f4; margin-right: auto; border-bottom-left-radius: 2px; }
                .message-meta { font-size: 0.75em; color: #888; margin-top: 5px; text-align: right; }
                pre { background: #2d2d2d; color: #f8f8f2; padding: 10px; border-radius: 4px; overflow-x: auto; font-family: 'Consolas', monospace; }
                .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; font-weight: bold; }
                .badge-model { background: #e6e6fa; color: #483d8b; }
                .toggle-btn { background: none; border: none; font-size: 1.2em; cursor: pointer; }
            </style>
            <script>
                function toggleSession(id) {
                    document.getElementById('session-' + id).classList.toggle('open');
                }
                function expandAll() {
                    document.querySelectorAll('.session').forEach(el => el.classList.add('open'));
                }
                function collapseAll() {
                    document.querySelectorAll('.session').forEach(el => el.classList.remove('open'));
                }
            </script>
        </head>
        <body>
            <div class="container">
                <h1>📜 Historial Completo de Conversaciones IA</h1>
                
                <div class="summary">
                    <p><strong>Total Sesiones:</strong> {total_sessions}</p>
                    <p><strong>Generado:</strong> {gen_date}</p>
                    <div style="margin-top: 10px;">
                        <button onclick="expandAll()" style="padding: 5px 10px; cursor:pointer;">Expandir Todo</button>
                        <button onclick="collapseAll()" style="padding: 5px 10px; cursor:pointer;">Colapsar Todo</button>
                    </div>
                </div>

                <div id="sessions-container">
        """
        
        import datetime
        html_content = html_content.replace("{total_sessions}", str(len(sessions)))
        html_content = html_content.replace("{gen_date}", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        for session in sessions:
            messages = history_service.get_session_messages(session['id'])
            
            # Formatting timestamp
            ts = session['created_at']
            
            html_content += f"""
            <div id="session-{session['id']}" class="session">
                <div class="session-header" onclick="toggleSession('{session['id']}')">
                    <div>
                        <strong style="font-size: 1.1em;">{session['title']}</strong>
                        <div class="session-meta">📅 {ts} | 🤖 {session['model_id']}</div>
                    </div>
                    <button class="toggle-btn">▼</button>
                </div>
                <div class="session-body">
            """
            
            for msg in messages:
                role_class = "user" if msg['role'] == "user" else "assistant"
                role_label = "👤 Usuario" if msg['role'] == "user" else "🤖 IA"
                
                content = msg['content'].replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                
                # Highlight code blocks (basic)
                if "```" in content:
                    # Simple regex to fix code blocks back to pre tags? 
                    # For simplicity, we just keep basic replacement or improve if needed.
                    pass 

                meta_html = ""
                if msg['meta'] and isinstance(msg['meta'], dict):
                    meta_str = ", ".join([f"{k}: {v}" for k, v in msg['meta'].items()])
                    meta_html = f"<div class='message-meta'>ℹ️ {meta_str}</div>"

                html_content += f"""
                    <div class="message {role_class}">
                        <div style="font-weight:bold; font-size:0.8em; margin-bottom:5px;">{role_label}</div>
                        <div>{content}</div>
                        {meta_html}
                        <div class="message-meta">{msg['created_at']}</div>
                    </div>
                """
            
            html_content += """
                </div>
            </div>
            """
            
        html_content += """
                </div>
                <div style="text-align: center; margin-top: 30px; color: #888;">
                    <small>Generado automáticamente por DEVIA System</small>
                </div>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error generando reporte</h1><p>{str(e)}</p>", status_code=500)
