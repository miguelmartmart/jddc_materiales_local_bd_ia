from backend.core.config.settings import settings
import os

print("--- Environment Config Check ---")
print(f"Loading from: {os.path.abspath('.env')}")
print(f"OUTLOOK_EMAIL: {settings.OUTLOOK_EMAIL}")
print(f"OUTLOOK_PASSWORD: {'*' * len(settings.OUTLOOK_PASSWORD) if settings.OUTLOOK_PASSWORD else 'None'}")
print(f"OUTLOOK_PASSWORD_APP: {'*' * len(settings.OUTLOOK_PASSWORD_APP) if settings.OUTLOOK_PASSWORD_APP else 'None'}")

if settings.OUTLOOK_PASSWORD_APP:
    print("✅ App Password detected.")
else:
    print("❌ App Password NOT detected in settings. Check .env spelling.")
