import json
import logging
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_FILE = Path("backend/core/config/analysis_exclusions.json")

class AnalysisConfig:
    def __init__(self):
        self._exclusions = []
        self._load()

    def _load(self):
        """Load exclusions from JSON file."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self._exclusions = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load analysis exclusions: {e}")
                self._exclusions = []
        else:
            self._exclusions = []
            self._save() # Create empty file

    def _save(self):
        """Save exclusions to JSON file."""
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._exclusions, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save analysis exclusions: {e}")

    def get_exclusions(self) -> List[Dict[str, Any]]:
        return self._exclusions

    def add_exclusion(self, rule: Dict[str, Any]):
        """
        Rule structure:
        {
            "id": str (uuid),
            "type": "sender" | "subject_contains" | "body_contains",
            "value": str,
            "enabled": bool
        }
        """
        if 'id' not in rule:
            import uuid
            rule['id'] = str(uuid.uuid4())
        
        self._exclusions.append(rule)
        self._save()
        return rule

    def remove_exclusion(self, rule_id: str):
        self._exclusions = [r for r in self._exclusions if r.get('id') != rule_id]
        self._save()

    def update_exclusion(self, rule_id: str, updates: Dict[str, Any]):
        for r in self._exclusions:
            if r.get('id') == rule_id:
                r.update(updates)
                break
        self._save()

    def should_exclude(self, email: Dict[str, Any]) -> bool:
        """Check if an email should be excluded based on active rules."""
        for rule in self._exclusions:
            if not rule.get('enabled', True):
                continue

            rtype = rule.get('type')
            rvalue = rule.get('value', '').lower()

            if not rvalue:
                continue

            if rtype == 'sender':
                sender = email.get('sender', '').lower()
                if rvalue in sender:
                    logger.info(f"Excluding email from {sender} due to rule: {rvalue}")
                    return True
            
            elif rtype == 'subject_contains':
                subject = email.get('subject', '').lower()
                if rvalue in subject:
                    logger.info(f"Excluding email '{subject}' due to rule: {rvalue}")
                    return True
            
            # Add more types if needed

        return False

analysis_config = AnalysisConfig()
