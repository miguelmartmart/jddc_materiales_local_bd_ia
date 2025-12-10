from backend.modules.outlook.service import OutlookService
from unittest.mock import MagicMock, patch
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_outlook_service_mock():
    print("Testing OutlookService with Mocks...")
    
    with patch("imaplib.IMAP4_SSL") as mock_imap:
        # 1. Setup Mock
        mock_instance = mock_imap.return_value
        mock_instance.login.return_value = ("OK", [b"Logged in"])
        mock_instance.select.return_value = ("OK", [b"100"])
        mock_instance.search.return_value = ("OK", [b"1 2 3"])
        
        # Mock fetch response
        # Structure: (status, [ (b'RFC822', raw_email_bytes), b')', ...])
        raw_email = (
            b"From: test@example.com\r\n"
            b"Subject: Test Email\r\n"
            b"Date: Wed, 10 Dec 2025 12:00:00 +0000\r\n"
            b"Content-Type: text/plain\r\n"
            b"\r\n"
            b"This is a test body content."
        )
        mock_instance.fetch.return_value = ("OK", [(None, raw_email)])

        # 2. Execute Service
        service = OutlookService()
        emails = service.fetch_recent_emails("fake@email.com", "fake_pass", limit=1)

        # 3. Assertions
        if len(emails) == 1:
            print("✅ Email fetched successfully")
            print(f"   Subject: {emails[0]['subject']}")
            print(f"   Body: {emails[0]['body']}")
        else:
            print("❌ Failed to fetch emails")

        # Test Connection
        if service.test_connection("fake@email.com", "fake_pass"):
             print("✅ Connection test pass")
        else:
             print("❌ Connection test failed")

if __name__ == "__main__":
    test_outlook_service_mock()
