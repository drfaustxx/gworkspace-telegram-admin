import logging
import json
import datetime
import random
import string
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError 
import os.path
import base64
import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Sheets API configuration
SCOPE = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
CREDS = ServiceAccountCredentials.from_json_keyfile_name(os.getenv('GWORKSPACE_CREDS_FILE'), SCOPE)
client = gspread.authorize(CREDS)
sheet = client.open(os.getenv('SPREADSHEET_FILENAME')).sheet1

# Google Workspace API configuration
WS_SCOPES = ["https://www.googleapis.com/auth/admin.directory.user"]
WORKSPACE_CREDS = service_account.Credentials.from_service_account_file(os.getenv('GWORKSPACE_CREDS_FILE'), scopes=WS_SCOPES)
delegatedCreds = WORKSPACE_CREDS.with_subject(os.getenv('GWORKSPACE_ADMIN_ACCOUNT'))
service = build('admin', 'directory_v1', credentials=delegatedCreds)


# Google Mail API configuration
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.send']

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

gmail_service = build('gmail', 'v1', credentials=creds)



def create_message(sender, to, subject, message_text, reply_to=None):
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    if reply_to:
        message['reply-to'] = reply_to
    raw_message = base64.urlsafe_b64encode(message.as_bytes())
    return {'raw': raw_message.decode()}

def send_message(service, user_id, message):
    try:
        message = service.users().messages().send(userId=user_id, body=message).execute()
        print(f'Message Id: {message["id"]}')
        return message
    except Exception as e:
        print(f'An error occurred: {e}')
        return None

BOT_PROTECTED_ACCOUNTS = os.getenv('BOT_PROTECTED_ACCOUNTS').split(',')
BOT_ALLOWED_USERS = os.getenv('BOT_ALLOWED_USERS').split(',')

def is_authorized(username):
    """Check if a user is authorized to use the bot."""
    return username in BOT_ALLOWED_USERS

async def start(update: Update, context: CallbackContext) -> None:
    """Send a welcome message and instructions when the /start command is issued."""
    if not is_authorized(update.message.from_user.username):
        await update.message.reply_text('You are not authorised to use write me.')
        return
    await update.message.reply_text('Hello! Plaese send me a message in the format:\nName Surname\nDesired email\nExisting email\nComment')

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle incoming messages and process the user information."""
    if not is_authorized(update.message.from_user.username):
        return
    try:
        # Remove the introductory part of the message
        text = update.message.tsext
        if "Hey" in text or "Hi" in text:
            text = text.split("\n", 1)[1].strip()
        
        if "We need" in text or "new member" in text:
            text = text.split("\n", 1)[1].strip()

        print(text)
        # Parse the remaining message
        text_lines = text.split('\n')
        if len(text_lines) < 4:
            await update.message.reply_text('I couldn\'t understand your message. Plaese send me a message in the format:\nName Surname\nDesired email\nExisting email\nComment')
            return

        first_name, last_name = text_lines[0].split()
        desired_email = text_lines[1]
        secondary_email = text_lines[2]
        comment = text_lines[3] + " " + text_lines[4] if len(text_lines) > 4 else text_lines[3]  # Handle multi-line comments
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        username = update.message.from_user.username

        # Add data to Google Sheet
        try:
            sheet.append_row([desired_email.strip(), "", first_name +" "+ last_name, comment, secondary_email, timestamp, username], table_range='A165')
        except gspread.exceptions.APIError as e:
            logger.error(f"Error addind data to Google Sheet: {e}")
            await update.message.reply_text('There is a problem with adding to Google Sheet. Please try again later.')
            return

        password = generate_random_password()
        
        # Create a new user in Google Workspace
        user_info = {
            'primaryEmail': desired_email,
            'name': {
                'givenName': first_name,
                'familyName': last_name
            },
            'password': password,
            'changePasswordAtNextLogin': True,
            'recoveryEmail': secondary_email
        }
        
        
        # Uncomment the next line to enable user creation in Google Workspace
        try:
            service.users().insert(body=user_info).execute()
        except HttpError as e:
            logger.error(f"There is an error creating user in Google Workspace: {e}")
            await update.message.reply_text('There is an error creating user in Google Workspace. Please try again later.')

        # Send email with user credentials
        message_text = generate_email_text(first_name, last_name, desired_email, password)
        message = create_message(os.getenv('GMAIL_SENDER_ADDRESS'), secondary_email, "Access Details for Google Workspace Account", message_text, reply_to=os.getenv('GWORKSPACE_ADMIN_ACCOUNT'))
        
        # Uncomment the next line to enable sending email with user credentials in Google Workspace
        send_message(gmail_service, 'me', message)

        await update.message.reply_text(f'The account for {first_name} {last_name} has been created.')
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"Error. Please verify your input. {e}")

def generate_random_password(length=12):
    """Generate a random password."""
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for i in range(length))
    return password

def generate_email_text(first_name, last_name, desired_email, password):
    text = f"""
        Hello, {first_name} {last_name}!

        Here are your access details for the Google Workspace account:

        Login page: https://mail.google.com/
        Username: {desired_email}
        Password: {password}

        Please log in and change your password immediately.

        Best regards,
        {os.getenv('EMAIL_SIGNATURE_LASTLINE')}
    """
    return text

async def add_user(update: Update, context: CallbackContext) -> None:
    """Add a new user to Google Workspace."""
    if not is_authorized(update.message.from_user.username):
        await update.message.reply_text('You are not authorised to use this command.')
        return

    try:
        # Extract arguments from the command
        args = context.args
        if len(args) < 4:
            await update.message.reply_text('Usage: /adduser <First Name> <Last Name> <Desired Email> <Secondary Email> <Comment>')
            return

        first_name = args[0]
        last_name = args[1]
        desired_email = args[2]
        secondary_email = args[3]
        comment = ' '.join(args[4:]) if len(args) > 4 else ''
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        username = update.message.from_user.username

        # Add data to Google Sheet
        try:
            sheet.append_row([desired_email.strip(), "", first_name + " " + last_name, comment, secondary_email, timestamp, username], table_range='A165')
        except gspread.exceptions.APIError as e:
            logger.error(f"Error adding to Google Sheet: {e}")
            await update.message.reply_text('Error adding to Google Sheet. Please try again later.')
            return

        password = generate_random_password()

        # Create a new user in Google Workspace
        user_info = {
            'primaryEmail': desired_email,
            'name': {
                'givenName': first_name,
                'familyName': last_name
            },
            'password': password,
            'changePasswordAtNextLogin': True,
            'recoveryEmail': secondary_email
        }

        try:
            service.users().insert(body=user_info).execute()
        except HttpError as e:
            logger.error(f"Error creating account in Google Workspace: {e}")
            await update.message.reply_text('Error creating account in Google Workspace. Please try again later.')
            return

        # Send email with user credentials
        message_text = generate_email_text(first_name, last_name, desired_email, password)
        message = create_message(os.getenv('GMAIL_SENDER_ADDRESS'), secondary_email, "Access Details for Google Workspace Account", message_text, reply_to=os.getenv('GWORKSPACE_ADMIN_ACCOUNT'))

        send_message(gmail_service, 'me', message)

        await update.message.reply_text(f'The account for {first_name} {last_name} has been created.')
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"There is an error sending email. Please verify your input. {e}")


async def suspend_user(update: Update, context: CallbackContext) -> None:
    """Suspend a user by their email address."""
    if not is_authorized(update.message.from_user.username):
        await update.message.reply_text('You are not authorised to use this command.')
        return

    try:
        email = context.args[0]
        if email in BOT_PROTECTED_ACCOUNTS:
            await update.message.reply_text(f'The account with email {email} cannot be suspended.')
            return

        service.users().update(userKey=email, body={'suspended': True}).execute()
        await update.message.reply_text(f'The account with email {email} has been suspended.')
    except IndexError:
        await update.message.reply_text('Please provide an email address. Usage: /suspend <email>')
    except HttpError as e:
        logger.error(f"There is an error suspending user in Google Workspace: {e}")
        await update.message.reply_text('There is an error suspending user in Google Workspace. Please try again later.')

async def get_user_info(update: Update, context: CallbackContext) -> None:
    """Retrieve user information by their email address."""
    if not is_authorized(update.message.from_user.username):
        await update.message.reply_text('You are not authorised to use this command.')
        return

    try:
        email = context.args[0]
        if email in BOT_PROTECTED_ACCOUNTS:
            await update.message.reply_text(f'The account info for email {email} cannot be disclosed.')
            return
        user = service.users().get(userKey=email).execute()
        
        first_name = user['name']['givenName']
        last_name = user['name']['familyName']
        secondary_email = user.get('recoveryEmail', 'Not provided')

        user_info = f"Name: {first_name}\nSurname: {last_name}\nSecondary Email: {secondary_email}"
        await update.message.reply_text(user_info)
    except IndexError:
        await update.message.reply_text('Please provide an email address. Usage: /userinfo <email>')
    except HttpError as e:
        logger.error(f"Error retrieving user info from Google Workspace: {e}")
        await update.message.reply_text('Error retrieving user info from Google Workspace. Please try again later.')

async def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    if not is_authorized(update.message.from_user.username):
        await update.message.reply_text('You are not authorised to use this command.')
        return
    
    help_text = (
        "Available commands:\n"
        "/start - Send a welcome message and instructions\n"
        "/suspend <email> - Suspend a user by their email address\n"
        "/userinfo <email> - Retrieve user information by their email address\n"
        "/adduser <First Name> <Last Name> <Desired Email> <Secondary Email> <Comment> - Add a new user to Google Workspace\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(help_text)

def main() -> None:
    """Start the bot."""
    token = os.getenv('BOT_TOKEN')
    
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("suspend", suspend_user))
    application.add_handler(CommandHandler("userinfo", get_user_info))  # Add this line
    application.add_handler(CommandHandler("adduser", add_user))
    application.add_handler(CommandHandler("help", help_command))  # Add this line
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == '__main__':
    main()