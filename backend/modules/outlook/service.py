import imaplib
import email
from email.header import decode_header
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class OutlookService:
    def __init__(self):
        self.imap_server = "outlook.office365.com"
        self.imap_port = 993

    def decode_mime_header(self, header_value: str) -> str:
        """Decodes MIME encoded headers like '=?utf-8?B?...?='."""
        if not header_value:
            return ""
        
        decoded_list = decode_header(header_value)
        decoded_text = ""
        
        for content, encoding in decoded_list:
            if isinstance(content, bytes):
                if encoding:
                    try:
                        decoded_text += content.decode(encoding)
                    except LookupError:
                        # Fallback for unknown encodings
                        decoded_text += content.decode('utf-8', errors='ignore')
                else:
                    decoded_text += content.decode('utf-8', errors='ignore')
            else:
                decoded_text += str(content)
                
        return decoded_text

    def get_email_body(self, msg) -> str:
        """Extracts plain text body from email message."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if "attachment" not in content_disposition:
                    if content_type == "text/plain":
                        try:
                            body += part.get_payload(decode=True).decode()
                        except:
                            pass
                    # Optionally handle html if needed, but we want text-only for now
        else:
            if msg.get_content_type() == "text/plain":
                try:
                    body = msg.get_payload(decode=True).decode()
                except:
                    pass
        
        return body.strip()

    def get_attachments(self, msg) -> List[Dict]:
        """Extracts attachments metadata and text content if possible."""
        attachments = []
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue

            filename = part.get_filename()
            if filename:
                filename = self.decode_mime_header(filename)
                content_type = part.get_content_type()
                
                text_content = None
                size = 0
                
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        size = len(payload)
                        # Try to extract text for analysis
                        if "text" in content_type or "json" in content_type or "csv" in content_type:
                           text_content = payload.decode('utf-8', errors='ignore')
                except:
                    pass

                attachments.append({
                    "filename": filename,
                    "content_type": content_type,
                    "size": size,
                    "content": text_content 
                })
        return attachments

    def fetch_recent_emails(self, email_address: str, password: str, limit: int = 5, imap_server: str = "outlook.office365.com", full_content: bool = False) -> List[Dict]:
        """Connects to IMAP Server and fetches recent emails."""
        try:
            # Connect to IMAP
            mail = imaplib.IMAP4_SSL(imap_server, self.imap_port)
            mail.login(email_address, password)
            mail.select("inbox")

            # Search for all emails
            status, messages = mail.search(None, "ALL")
            if status != "OK":
                return []

            email_ids = messages[0].split()
            # Get the last 'limit' emails
            latest_email_ids = email_ids[-limit:]
            latest_email_ids.reverse() # Newest first

            results = []

            for e_id in latest_email_ids:
                status, msg_data = mail.fetch(e_id, "(RFC822 FLAGS)")
                if status != "OK":
                    continue
                
                # Check for flags in msg_data
                is_read = False
                for response_part in msg_data:
                    # Flags are usually in the byte string part or separate part
                    # e.g. b'369 (RFC822 {2000} FLAGS (\\Seen))'
                    if isinstance(response_part, bytes):
                        if b'\\Seen' in response_part:
                            is_read = True
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        subject = self.decode_mime_header(msg.get("Subject"))
                        sender = self.decode_mime_header(msg.get("From"))
                        body = self.get_email_body(msg)
                        date = msg.get("Date")
                        
                        # Handle attachments and body truncation
                        attachments = []
                        if full_content:
                            attachments = self.get_attachments(msg)
                        else:
                            body = body[:500] + "..." if len(body) > 500 else body # Truncate long bodies

                        results.append({
                            "id": e_id.decode(),
                            "subject": subject,
                            "sender": sender,
                            "date": date,
                            "body": body,
                            "is_read": is_read,
                            "attachments": attachments
                        })

            mail.close()
            mail.logout()
            return results

        except imaplib.IMAP4.error as e:
            error_msg = str(e)
            logger.error(f"IMAP Error: {error_msg}")
            if "LOGIN failed" in error_msg:
                raise Exception("Error de autenticación: Verifica tu usuario y contraseña. Si usas 2FA, necesitas una Contraseña de Aplicación.")
            raise Exception(f"Error IMAP Outlook: {error_msg}")
        except Exception as e:
            logger.error(f"Error fetching emails: {str(e)}")
            raise e

    async def get_unread_count(self, email_address: str, password: str, imap_server: str = "outlook.office365.com") -> int:
        """Returns the total number of unread emails in Inbox."""
        try:
            # We use a new connection to avoid state conflicts
            mail = imaplib.IMAP4_SSL(imap_server, self.imap_port)
            mail.login(email_address, password)
            mail.select("inbox")
            status, messages = mail.search(None, "UNSEEN")
            mail.logout()
            
            if status == "OK":
                return len(messages[0].split())
            return 0
        except:
            return 0

    def test_connection(self, email_address: str, password: str) -> bool:
        """Tests connection to Outlook."""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(email_address, password)
            mail.logout()
            return True
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            return False
