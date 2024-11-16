import os.path
import base64
import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import sys
import os

# Add the directory containing config.py to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv

load_dotenv()

GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_credentials():
    """Get Google API credentials."""
    creds = None
    if os.path.exists(os.getenv('GMAIL_TOKEN_FILE')):
        creds = Credentials.from_authorized_user_file(os.getenv('GMAIL_TOKEN_FILE'), GMAIL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(os.getenv('GMAIL_CREDENTIALS_FILE'), GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(os.getenv('GMAIL_TOKEN_FILE'), 'w') as token:
            token.write(creds.to_json())
    return creds

def create_message(sender, to, subject, message_text):
    """Create a message for an email."""
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes())
    return {'raw': raw_message.decode()}

def send_message(service, user_id, message):
    """Send an email message."""
    try:
        message = service.users().messages().send(userId=user_id, body=message).execute()
        print(f'Message Id: {message["id"]}')
        return message
    except Exception as e:
        print(f'An error occurred: {e}')
        return None

def main():
    """Main function to send an email."""
    creds = get_credentials()
    service = build('gmail', 'v1', credentials=creds)

    sender = os.getenv('GMAIL_SENDER_ADDRESS')
    to = os.getenv('GWORKSPACE_ADMIN_ACCOUNT')
    subject = "Access Details for Google Workspace Account"
    message_text = """
    Hello,

    Here are your access details for the Google Workspace account:

    Username: your-username@example.com
    Password: your-password

    Please log in and change your password immediately.

    Best regards,
    Your Company
    """

    message = create_message(sender, to, subject, message_text)
    send_message(service, 'me', message)

if __name__ == '__main__':
    main()