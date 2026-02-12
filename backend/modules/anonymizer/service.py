import logging
import json
import os
from typing import Dict, Any, Optional, List
from openai import OpenAI
from backend.modules.chat.chat_history_service import ChatHistoryService
from backend.core.config.settings import settings

logger = logging.getLogger(__name__)

class AnonymizerService:
    # Default Configuration
    DEFAULT_API_URL = "http://localhost:1234/v1"
    DEFAULT_MODEL = "local-model"
    # Updated Default Configuration with Few-Shot Examples for better Local AI performance
    DEFAULT_SYSTEM_PROMPT = """You are an expert data anonymization assistant specialized in Spanish text.
Your GOAL is to redact ALL Personally Identifiable Information (PII) to protect privacy.

CATEGORIES TO REDACT:
{categories_section}

RULES:
- REPLACE the sensitive data with the corresponding placeholder.
- DO NOT summarize. KEEP the exact sentence structure.
- IF text is already anonymized (e.g. [DNI]), keep it.
- OUTPUT ONLY THE ANONYMIZED TEXT. NO EXPLANATIONS, NO LABELS, NO MARKDOWN.
{exceptions_section}

EXAMPLES:
Input: "El usuario Miguel Ángel con DNI 12345678Z nació el 17 de enero de 1999."
Output: "El usuario [NOMBRE] con DNI [ID] nació el [FECHA]."

Input: "Contacta a ana.garcia@email.com o al 600123456."
Output: "Contacta a [EMAIL] o al [TELEFONO]."

Input: "hola"
Output: "hola"

Input: "Vivo en Calle Mayor 12, Madrid."
Output: "Vivo en [DIRECCION], Madrid."

Now, anonymize the following user text (and ONLY return the result):
"""

    def __init__(self):
        self.chat_history = ChatHistoryService()
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self._load_config()

    def _load_config(self):
        """Loads configuration from file or sets defaults."""
        self.config = {
            "api_url": self.DEFAULT_API_URL,
            "model": self.DEFAULT_MODEL,
            "system_prompt": self.DEFAULT_SYSTEM_PROMPT,
            "enable_chat": True, # Default Enabled
            "enable_outlook": True,
            "enable_database": True,
            # Granular defaults
            "anonymize_ids": True,
            "anonymize_emails": True,
            "anonymize_phones": True,
            "anonymize_names": True,
            "preserve_products": True
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
            except Exception as e:
                logger.error(f"Failed to load anonymizer config: {e}")

    def _regex_anonymize_pre(self, text: str) -> str:
        """
        Uses strong Regex patterns to deterministically redact well-defined PII.
        Respects configuration settings.
        """
        import re
        
        # 1. Emails
        if self.config.get('anonymize_emails', True):
            text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
        
        # 2. Spanish Phones (Generic +34 or 9/6/7 starts, 9 digits)
        # Matches: +34 600 000 000, 600000000, 912 345 678
        if self.config.get('anonymize_phones', True):
            phone_pattern = r'(?:\+34\s?)?[6789]\d{2}[\s.-]?\d{3}[\s.-]?\d{3}'
            text = re.sub(phone_pattern, '[TELEFONO]', text)
        
        # 3. DNI/NIE (Simple check: 8 digits + letter, or X/Y/Z + 7 digits + letter)
        if self.config.get('anonymize_ids', True):
            dni_pattern = r'\b[XYZ]?\d{7,8}[A-Z]\b'
            text = re.sub(dni_pattern, '[ID]', text)
        
        return text

    def _build_config_aware_prompt(self) -> str:
        """Constructs the system prompt based on enabled categories."""
        categories = []
        if self.config.get('anonymize_names', True):
            categories.append("1. PERSON NAMES (e.g., Miguel Ángel, Juan Pérez, María) -> [NOMBRE]")
        if self.config.get('anonymize_ids', True):
            categories.append("2. ID NUMBERS (DNI, NIF, NIE, Passport) -> [ID]")
        if self.config.get('anonymize_emails', True) or self.config.get('anonymize_phones', True):
            categories.append("3. CONTACT INFO (Emails, Phone Numbers) -> [EMAIL], [TELEFONO]")
        
        # Always included for general safety
        categories.append("4. DATES (Birthdates, specific dates) -> [FECHA]")
        categories.append("5. LOCATIONS (Specific addresses, not cities) -> [DIRECCION]")

        exceptions = ""
        if self.config.get('preserve_products', True):
            exceptions = "- IMPORTANT: Do NOT anonymize Product names, Technical codes, or Articles (e.g. 'iPhone 15', 'Tuerca M5', 'Cemento'). Preserve them exactly."

        # If user defined a custom prompt that doesn't look like our template, use it (respecting customization)
        # But here we assume the template structure for "Hybrid" mode.
        # We'll use the class template and formatting.
        
        prompt = self.DEFAULT_SYSTEM_PROMPT.format(
            categories_section="\n".join(categories),
            exceptions_section=exceptions
        )
        return prompt

    def should_anonymize(self, feature: str) -> bool:
        """Checks if anonymization is enabled for a specific feature."""
        key = f"enable_{feature}"
        return self.config.get(key, True) # Default true if unknown feature

    def anonymize_if_enabled(self, text: str, feature: str) -> str:
        """
        Anonymizes text if the feature is enabled.
        Returns original text on failure (Fail-Open) to ensure app resilience.
        """
        if not self.should_anonymize(feature):
            return text
            
        try:
            result = self.anonymize_text(text)
            return result["anonymized"]
        except Exception as e:
            # Fail-Open: Log error but return original text so the main app flow continues
            logger.error(f"Anonymization failed for {feature}, proceeding with original text. Error: {e}")
            return text

    def _get_api_key_for_url(self, url: str) -> Optional[str]:
        """Auto-detects API key from settings based on the URL domain."""
        url = url.lower()
        if "groq.com" in url:
            return settings.GROQ_API_KEY
        if "openai.com" in url:
            return settings.OPENAI_API_KEY
        if "deepseek" in url: # Generic check, adjust if specific URL known
            return settings.DEEPSEEK_API_KEY
        if "openrouter" in url:
            return settings.OPENROUTER_API_KEY
        # Add more providers as needed
        return None

    def save_config(self, new_config: Dict[str, str]):
        """Updates and saves the configuration."""
        self.config.update(new_config)
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save anonymizer config: {e}")
            raise Exception("Could not save configuration settings.")

    def get_config(self) -> Dict[str, str]:
        return self.config

    def anonymize_text(self, text: str) -> Dict[str, Any]:
        """
        1. Pre-process with Regex for hard patterns.
        2. Send to AI for Context/Names using dynamic prompt.
        3. Return result.
        """
        if not text:
            raise ValueError("Text cannot be empty.")

        try:
            # 1. Regex Safety Layer
            pre_processed_text = self._regex_anonymize_pre(text)
            
            # 2. Build Dynamic Prompt
            system_prompt = self._build_config_aware_prompt()

            # Determine API Key based on Provider URL
            api_key = self._get_api_key_for_url(self.config["api_url"])
            if not api_key:
                 api_key = "not-needed" # Default for Local LLMs

            # Configure OpenAI Client
            client = OpenAI(
                base_url=self.config["api_url"],
                api_key=api_key 
            )

            # Log Start to History (logging original text for audit)
            session_title = f"Anonymization: {text[:30]}..."
            session_id = self.chat_history.create_session(self.config["model"], title=session_title)
            
            # Add System Message (The Prompt)
            self.chat_history.add_message(
                session_id, 
                "system", 
                system_prompt, 
                {"module": "anonymizer", "config_snapshot": self.config}
            )

            # Add User Message
            self.chat_history.add_message(
                session_id, 
                "user", 
                text, 
                {"module": "anonymizer", "pre_processed": pre_processed_text}
            )

            # Call AI with Pre-processed text to help it focus on Names/Context
            logger.info(f"Sending anonymization request to {self.config['api_url']}")
            
            # Note: We send the Pre-processed text. The AI will see [ID] and should keep it according to prompt.
            response = client.chat.completions.create(
                model=self.config["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f'Input text to anonymize:\n"{pre_processed_text}"'}
                ],
                temperature=0.1 # Low temperature for consistent results
            )
            
            # Update Session with the ACTUAL model used (in case of fallback or specific version)
            actual_model = response.model
            if actual_model:
                self.chat_history.update_session_model(session_id, actual_model)

            import re
            anonymized_text = response.choices[0].message.content.strip()
            # Remove explicit outer quotes if AI added them due to prompt example
            anonymized_text = anonymized_text.strip('"').strip("'")
            
            # Cleanup <think> blocks (DeepSeek-R1 style reasoning)
            anonymized_text = re.sub(r'<think>.*?</think>', '', anonymized_text, flags=re.DOTALL).strip()


            # Add Assistant Message (Result)
            self.chat_history.add_message(
                session_id, 
                "assistant", 
                anonymized_text, 
                {"module": "anonymizer", "status": "success", "method": "hybrid (regex+ai)"}
            )
            
            return {
                "original": text,
                "anonymized": anonymized_text,
                "session_id": session_id
            }

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            target_url = self.config.get("api_url", "UNKNOWN_URL")
            
            # Smart Error Analysis for User Feedback
            user_error_msg = str(e)
            if "Connection error" in str(e) or "connection attempt failed" in str(e) or "target machine" in str(e):
                if "localhost" in target_url or "127.0.0.1" in target_url:
                    user_error_msg = f"⚠️ No se puede conectar con el servidor local en {target_url}. Por favor, asegúrate de iniciar tu servidor de IA Local (LM Studio, LocalAI, etc)."
                else:
                    user_error_msg = f"⚠️ Error de conexión con el proveedor de IA en {target_url}. Verifica tu conexión a internet o la URL."

            logger.error(f"❌ Anonymization FAILED connecting to {target_url}")
            logger.error(f"Error Type: {type(e).__name__}")
            logger.error(f"Original Error: {str(e)}")
            logger.error(f"Traceback:\n{error_details}")
            
            # Log Failure if session was created
            if 'session_id' in locals():
                self.chat_history.add_message(
                    session_id, 
                    "system", 
                    f"FATAL: {user_error_msg}", 
                    {"module": "anonymizer", "status": "failed", "raw_error": str(e)}
                )
            # Raise the friendly message
            raise Exception(user_error_msg)

    def get_history(self, limit: int = 20) -> List[Dict]:
        """Retrieves anonymization history."""
        # We can reuse general chat history but filter or just return session list for now.
        # Since we use a specific prefix or metadata, we could filter.
        # For simplicity, we'll fetch recent sessions and return those that look like anonymization.
        sessions = self.chat_history.get_recent_sessions(limit=limit * 2)
        
        anonymizer_sessions = []
        for s in sessions:
            # Check title or check first message meta if needed, but title is simplest heuristc for now
            if s['title'].startswith("Anonymization:"):
                s['messages'] = self.chat_history.get_session_messages(s['id'])
                anonymizer_sessions.append(s)
                if len(anonymizer_sessions) >= limit:
                    break
        
        return anonymizer_sessions
