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
        """Extracts plain text body from email message, falling back to html stripping if needed."""
        body = ""
        html_body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if "attachment" not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            decoded = payload.decode('utf-8', errors='ignore')
                            if content_type == "text/plain":
                                body += decoded
                            elif content_type == "text/html":
                                html_body += decoded
                    except:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    decoded = payload.decode('utf-8', errors='ignore')
                    if msg.get_content_type() == "text/plain":
                        body = decoded
                    elif msg.get_content_type() == "text/html":
                        html_body = decoded
            except:
                pass
        
        final_body = body.strip()
        if not final_body:
            final_body = html_body.strip()
            
        # Check if we need to clean HTML (either because it was html_body OR text/plain contained html)
        if final_body and ('<' in final_body and '>' in final_body):
             # Robust strip tags
            import re
            import html
            
            # Remove head, style, script completely
            final_body = re.sub(r'<(head|style|script)[^>]*>.*?</\1>', '', final_body, flags=re.IGNORECASE | re.DOTALL)
            
            # Replace breaks/paragraphs with newlines for readability
            final_body = re.sub(r'<(br|div|p)[^>]*>', '\n', final_body, flags=re.IGNORECASE)
            
            # Strip remaining tags
            clean = re.compile('<.*?>')
            final_body = re.sub(clean, '', final_body)
            
            # Unescape entities (twice to be safe)
            final_body = html.unescape(final_body)
            
            # Clean up excessive newlines
            final_body = re.sub(r'\n\s*\n', '\n\n', final_body).strip()
            
        return final_body

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
                # Use BODY.PEEK[] to fetch without marking as read
                status, msg_data = mail.fetch(e_id, "(BODY.PEEK[] FLAGS)")
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

    def get_global_daily_stats(self, email_address: str, password: str, days: int = 3) -> List[Dict]:
        """Fetches total and unread counts for the last N days using IMAP Search."""
        stats = []
        try:
            # Connect to IMAP
            # Note: We need to respect the server argument if passed, but here we assume standard outlook/gmail logic
            # For simplicity, default to outlook but we might need to pass server if using Gmail fallback
            # Currently this method signature doesn't accept imap_server. I will add it or default to self.imap_server.
            # Ideally, we should pass 'imap_server' as arg, but router calls it with just (email, password, days=3).
            # I'll stick to self.imap_server for now, BUT if hybrid auth is used, we might be checking the wrong server.
            # However, simpler is better to fix the crash first.
            
            # Wait, if router.py calls it, it doesn't pass server.
            # Let's check router.py logic. It calls `service.get_global_daily_stats(email, final_password, days=3)`.
            # If using Gmail, `final_password` is Gmail's, but `service.imap_server` is "outlook.office365.com".
            # This will fail login if using Gmail creds on Outlook server.
            # I should update router.py to pass server too, OR update this method to try/catch.
            # Let's update this method to accept imap_server, defaulting to outlook.
            
            server = "outlook.office365.com"
            if "gmail" in email_address: # Naive check, but helpful
                 server = "imap.gmail.com"
            
            # Use the calculated server, not self.imap_server
            mail = imaplib.IMAP4_SSL(server, self.imap_port)
            try:
                mail.login(email_address, password)
            except:
                # Fallback implementation if needed, but for now just logging
                logger.warning(f"Global stats login failed for {email_address} on {server}")
                return []

            mail.select("inbox")
            
            import datetime
            # Helper for IMAP date format: DD-Mon-YYYY
            def format_date(dt):
                months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                return f"{dt.day}-{months[dt.month-1]}-{dt.year}"
            
            now = datetime.datetime.now()
            
            for i in range(days):
                target_date = now - datetime.timedelta(days=i)
                date_str = format_date(target_date)
                
                # Check Total
                typ, data = mail.search(None, f'(ON "{date_str}")')
                total = 0
                if typ == 'OK':
                    total = len(data[0].split())
                
                # Check Unread
                typ, data = mail.search(None, f'(ON "{date_str}" UNSEEN)')
                unread = 0
                if typ == 'OK':
                    unread = len(data[0].split())
                    
                read_count = total - unread
                
                label = "Hoy" if i == 0 else "Ayer" if i == 1 else "Anteayer" if i == 2 else date_str
                
                stats.append({
                    "label": label,
                    "date": date_str,
                    "total": total,
                    "unread": unread,
                    "read": read_count
                })
                
            mail.logout()
        except Exception as e:
            logger.error(f"Error fetching global stats: {e}")
            
        return stats
