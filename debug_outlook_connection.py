import imaplib
import os
import logging

# Configure logging to console
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

def load_env_credentials():
    email = None
    password = None
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('OUTLOOK_EMAIL='):
                    email = line.split('=')[1].strip()
                elif line.startswith('OUTLOOK_PASSWORD='):
                    password = line.split('=')[1].strip()
    except Exception as e:
        print(f"Error reading .env: {e}")
    return email, password

def debug_connection():
    email_addr, password = load_env_credentials()
    
    print("--- Outlook IMAP Debugger ---")
    if not email_addr or not password:
        print("❌ Error: Credentials not found in .env")
        print("Please ensure OUTLOOK_EMAIL and OUTLOOK_PASSWORD are set.")
        return

    print(f"📧 Targeting: {email_addr}")
    # Mask password for output
    masked_pw = password[:2] + "****" + password[-2:] if len(password) > 4 else "****"
    print(f"🔑 Password: {masked_pw}")

    servers = [
        ("outlook.office365.com", 993),
        ("imap-mail.outlook.com", 993),
    ]

    for server, port in servers:
        print(f"\n📡 Attempting connection to {server}:{port}...")
        try:
            mail = imaplib.IMAP4_SSL(server, port)
            mail.debug = 4 # Full verbosity
            
            print("   ✅ Connected to socket.")
            print("   🔐 Attempting LOGIN...")
            
            mail.login(email_addr, password)
            print(f"   ✅ LOGIN SUCCESSFUL on {server}!")
            
            mail.select("inbox")
            status, messages = mail.search(None, "ALL")
            print(f"   📩 Messages found: {len(messages[0].split())}")
            
            mail.logout()
            return # Exit on success

        except imaplib.IMAP4.error as e:
            print(f"   ❌ LOGIN FAILED on {server}: {e}")
            if "LOGIN failed" in str(e):
                print("      -> The server rejected the credentials.")
        except Exception as e:
            print(f"   ❌ CONNECTION ERROR on {server}: {e}")

    print("\n\n📊 DIAGNOSIS:")
    print("If all attempts failed with 'LOGIN failed', possible causes:")
    print("1. IMAP is disabled in Outlook.com settings (Cog icon > Mail > Sync email).")
    print("2. 'Basic Auth' is blocked for this account (requires OAuth2).")
    print("3. Wrong password (even if you think it's right). Try generating a new App Password.")

if __name__ == "__main__":
    debug_connection()
