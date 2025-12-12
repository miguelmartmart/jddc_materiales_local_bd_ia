import logging
import base64
from typing import Dict, Any, Optional, List
from backend.core.factory.ai_factory import AIFactory
from backend.core.abstract.ai import AIConfig
from backend.core.config.settings import settings

logger = logging.getLogger(__name__)

class AttachmentAnalyzer:
    """Analyzes email attachments using AI with chunking for large files."""
    
    def __init__(self):
        self.max_chunk_size = 15000  # characters per chunk to avoid token limits
    
    def _chunk_text(self, text: str, max_size: int = None) -> List[str]:
        """Split text into chunks to avoid token limits."""
        if max_size is None:
            max_size = self.max_chunk_size
            
        if len(text) <= max_size:
            return [text]
        
        chunks = []
        current_pos = 0
        
        while current_pos < len(text):
            chunk = text[current_pos:current_pos + max_size]
            chunks.append(chunk)
            current_pos += max_size
        
        return chunks
    
    async def analyze_text_attachment(self, content: str, filename: str) -> str:
        """Analyze text-based attachment with chunking if needed."""
        chunks = self._chunk_text(content)
        
        if len(chunks) == 1:
            # Single chunk - analyze directly
            prompt = f"""Analiza el siguiente archivo adjunto: {filename}

Contenido:
{content[:10000]}

Proporciona un resumen conciso en español de:
1. Tipo de documento
2. Contenido principal
3. Información relevante o importante
"""
            return await self._generate_with_fallback(prompt)
        
        # Multiple chunks - analyze each and combine
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            prompt = f"""Analiza la parte {i+1}/{len(chunks)} del archivo: {filename}

Contenido:
{chunk}

Proporciona un resumen breve de esta sección."""
            
            summary = await self._generate_with_fallback(prompt)
            chunk_summaries.append(f"Parte {i+1}: {summary}")
        
        # Combine summaries
        combined_prompt = f"""Resume el siguiente análisis del archivo {filename}:

{chr(10).join(chunk_summaries)}

Proporciona un resumen final conciso y coherente en español."""
        
        return await self._generate_with_fallback(combined_prompt)
    
    async def analyze_pdf(self, content: bytes, filename: str) -> str:
        """Analyze PDF attachment (requires PyPDF2)."""
        try:
            import PyPDF2
            import io
            
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            text_parts = []
            
            # Extract text from all pages (limit to first 10 pages for performance)
            max_pages = min(10, len(pdf_reader.pages))
            for page_num in range(max_pages):
                page = pdf_reader.pages[page_num]
                text_parts.append(page.extract_text())
            
            full_text = "\n".join(text_parts)
            
            if not full_text.strip():
                return f"PDF '{filename}': No se pudo extraer texto (puede ser un PDF de imágenes)"
            
            return await self.analyze_text_attachment(full_text, filename)
            
        except ImportError:
            return f"PDF '{filename}': Requiere PyPDF2 para análisis (pip install PyPDF2)"
        except Exception as e:
            logger.error(f"Error analyzing PDF {filename}: {e}")
            return f"PDF '{filename}': Error al analizar - {str(e)}"
    
    async def analyze_image(self, content: bytes, filename: str, content_type: str) -> str:
        """Analyze image attachment using AI vision models."""
        try:
            # Encode image to base64
            image_b64 = base64.b64encode(content).decode('utf-8')
            
            # Try to use a vision-capable model
            prompt = f"Describe esta imagen adjunta en el correo (nombre: {filename}). Proporciona un resumen conciso en español de lo que se ve."
            
            # For now, return a placeholder - vision models require special handling
            return f"Imagen '{filename}' ({content_type}): Análisis de imágenes requiere modelo con visión (Gemini Vision/GPT-4 Vision) - Tamaño: {len(content)} bytes"
            
        except Exception as e:
            logger.error(f"Error analyzing image {filename}: {e}")
            return f"Imagen '{filename}': Error al analizar - {str(e)}"
    
    async def analyze_document(self, content: bytes, filename: str, content_type: str) -> str:
        """Analyze document attachments (DOCX, XLSX, etc.)."""
        try:
            if "wordprocessingml" in content_type or filename.endswith(".docx"):
                # DOCX analysis
                try:
                    import docx
                    import io
                    
                    doc = docx.Document(io.BytesIO(content))
                    text_parts = [para.text for para in doc.paragraphs if para.text.strip()]
                    full_text = "\n".join(text_parts)
                    
                    return await self.analyze_text_attachment(full_text, filename)
                except ImportError:
                    return f"Documento '{filename}': Requiere python-docx (pip install python-docx)"
            
            elif "spreadsheetml" in content_type or filename.endswith(".xlsx"):
                # XLSX analysis
                try:
                    import openpyxl
                    import io
                    
                    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
                    sheet_summaries = []
                    
                    for sheet_name in wb.sheetnames[:3]:  # Limit to first 3 sheets
                        sheet = wb[sheet_name]
                        rows_text = []
                        for row in list(sheet.rows)[:20]:  # First 20 rows
                            row_values = [str(cell.value) if cell.value is not None else "" for cell in row]
                            rows_text.append(" | ".join(row_values))
                        
                        sheet_summaries.append(f"Hoja '{sheet_name}':\n" + "\n".join(rows_text))
                    
                    full_text = "\n\n".join(sheet_summaries)
                    return await self.analyze_text_attachment(full_text, filename)
                except ImportError:
                    return f"Excel '{filename}': Requiere openpyxl (pip install openpyxl)"
            
            else:
                return f"Documento '{filename}' ({content_type}): Tipo no soportado para análisis automático"
                
        except Exception as e:
            logger.error(f"Error analyzing document {filename}: {e}")
            return f"Documento '{filename}': Error al analizar - {str(e)}"
    
    async def analyze_attachment(self, content: bytes, filename: str, content_type: str) -> str:
        """Main method to analyze any attachment type."""
        try:
            # Determine analysis method based on content type
            if "text" in content_type or "json" in content_type or "csv" in content_type:
                text_content = content.decode('utf-8', errors='ignore')
                return await self.analyze_text_attachment(text_content, filename)
            
            elif "pdf" in content_type:
                return await self.analyze_pdf(content, filename)
            
            elif "image" in content_type:
                return await self.analyze_image(content, filename, content_type)
            
            elif "wordprocessingml" in content_type or "spreadsheetml" in content_type or \
                 filename.endswith((".docx", ".xlsx")):
                return await self.analyze_document(content, filename, content_type)
            
            else:
                return f"Archivo '{filename}' ({content_type}): Tipo no soportado para análisis - Tamaño: {len(content)} bytes"
                
        except Exception as e:
            logger.error(f"Error analyzing attachment {filename}: {e}")
            return f"Error al analizar '{filename}': {str(e)}"
    
    async def _generate_with_fallback(self, prompt: str) -> str:
        """Generate text using available AI models with fallback."""
        from backend.core.config.model_manager import model_manager
        
        models = model_manager.list_models(enabled_only=True)
        
        for model_config in models:
            try:
                # Get provider name from model config
                provider_name = model_config.get("provider")
                
                # Create AIConfig without provider parameter
                ai_config = AIConfig(
                    api_key=model_config.get("api_key", ""),
                    model=model_config.get("model_id"),
                    base_url=model_config.get("base_url"),
                    temperature=0.3
                )
                
                # Get provider instance using provider name
                provider = AIFactory.get_provider(provider_name)
                provider.configure(ai_config)
                
                response = await provider.generate_text(prompt)
                return response.strip()
                
            except Exception as e:
                logger.warning(f"Model {model_config.get('model_id')} failed: {e}")
                continue
        
        return "No se pudo generar análisis: todos los modelos AI fallaron"

# Global instance
attachment_analyzer = AttachmentAnalyzer()
