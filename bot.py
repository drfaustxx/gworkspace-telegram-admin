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
from tabulate import tabulate
from functools import wraps
import inspect

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

try:
    # Trying to open log sheet
    log_sheet = client.open(os.getenv('LOGS_SHEET_FILENAME')).sheet1
except Exception as e:
    # If it is not exists, trying to create it
    log_spreadsheet = client.create(os.getenv('LOGS_SHEET_FILENAME'))
    log_sheet = log_spreadsheet.sheet1
    
    # Setting headers
    headers = [
        'Timestamp',
        'Username',
        'User ID',
        'Type',
        'Content',
        'Handler'
    ]
    log_sheet.append_row(headers)

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

def log_to_sheet(func):
    """Decorator for logging messages to Google Spreadsheet."""
    @wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        try:
            # Getting log sheet
            log_sheet = client.open(os.getenv('LOGS_SHEET_FILENAME')).sheet1
            
            # Collecting message information
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            username = update.effective_user.username
            user_id = update.effective_user.id
            
            # Determining message type (command or text)
            if update.message.text.startswith('/'):
                message_type = 'command'
                content = update.message.text
            else:
                message_type = 'message'
                content = update.message.text

            # Getting handler name
            handler_name = func.__name__

            # Writing to the sheet
            log_sheet.append_row([
                timestamp,
                username,
                str(user_id),
                message_type,
                content,
                handler_name
            ])

        except Exception as e:
            logger.error(f"Error logging to sheet: {e}")
            # Not interrupting the main function execution in case of logging error
            pass

        # Executing the original function
        return await func(update, context, *args, **kwargs)

    return wrapper

@log_to_sheet
async def start(update: Update, context: CallbackContext) -> None:
    """Send a welcome message and instructions when the /start command is issued."""
    if not is_authorized(update.message.from_user.username):
        await update.message.reply_text('You are not authorised to use write me.')
        return
    await update.message.reply_text('Hello! Plaese send me a message in the format:\nName Surname\nDesired email\nExisting email\nComment')

@log_to_sheet
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

@log_to_sheet
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


@log_to_sheet
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

@log_to_sheet
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

@log_to_sheet
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
        "/listusers - Lists all users in Google Workspace\n"
        "/resetpw <email> - Reset user's password and force change on next login\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(help_text)

@log_to_sheet
async def list_users(update: Update, context: CallbackContext) -> None:
    """List all users with their status and last login date."""
    if not is_authorized(update.message.from_user.username):
        await update.message.reply_text('You are not authorised to use this command.')
        return

    try:
        # Get list of all users with pagination
        users = []
        page_token = None
        while True:
            results = service.users().list(
                customer='my_customer',
                orderBy='email',
                projection='full',
                pageToken=page_token,
                maxResults=500  # Maximum allowed by the API
            ).execute()
            
            users.extend(results.get('users', []))
            page_token = results.get('nextPageToken')
            if not page_token:
                break

        # Prepare data for table
        table_data = []
        for user in users:
            email = user['primaryEmail']
            # Skip protected accounts if needed
            if email in BOT_PROTECTED_ACCOUNTS:
                continue
                
            is_suspended = user.get('suspended', False)
            status = '🔴 Suspended' if is_suspended else '🟢 Active'
            
            # Get last login time
            last_login = user.get('lastLoginTime', None)
            if last_login:
                # Convert to datetime and format
                last_login_dt = datetime.datetime.strptime(last_login, "%Y-%m-%dT%H:%M:%S.%fZ")
                last_login_str = last_login_dt.strftime("%Y-%m-%d %H:%M")
            else:
                last_login_str = "Never"

            # Get creation time
            creation_time = user.get('creationTime', None)
            if creation_time:
                creation_dt = datetime.datetime.strptime(creation_time, "%Y-%m-%dT%H:%M:%S.%fZ")
                creation_str = creation_dt.strftime("%Y-%m-%d %H:%M")
            else:
                creation_str = "Unknown"

            table_data.append([
                email,
                status,
                creation_str,
                last_login_str
            ])

        if not table_data:
            await update.message.reply_text('No users found.')
            return

        # Split table_data into chunks of 50 rows
        chunk_size = 50
        for i in range(0, len(table_data), chunk_size):
            chunk = table_data[i:i + chunk_size]
            
            # Create table for this chunk
            table = tabulate(
                chunk,
                headers=['Email', 'Status', 'Created On', 'Last Login'],
                tablefmt='simple',
                numalign='left'
            )
            
            # Add page number info
            page_number = f"\nPage {i//chunk_size + 1} of {(len(table_data) + chunk_size - 1)//chunk_size}"
            
            # Send message with this chunk
            try:
                await update.message.reply_text(
                    f'```\n{table}{page_number}\n```', 
                    parse_mode='MarkdownV2'
                )
            except Exception as e:
                # If markdown parsing fails, try sending without special formatting
                await update.message.reply_text(f'{table}{page_number}')
            
    except HttpError as e:
        logger.error(f"Error retrieving users from Google Workspace: {e}")
        await update.message.reply_text('Error retrieving users from Google Workspace. Please try again later.')

@log_to_sheet
async def reset_password(update: Update, context: CallbackContext) -> None:
    """Reset a user's password and force them to change it on next login."""
    if not is_authorized(update.message.from_user.username):
        await update.message.reply_text('You are not authorised to use this command.')
        return

    try:
        
        # Check if email was provided
        if not context.args:
            await update.message.reply_text('Please provide an email address. Usage: /resetpw <email>')
            return
            
        email = context.args[0]
        
        # Check if it's a protected account
        if email in BOT_PROTECTED_ACCOUNTS:
            await update.message.reply_text(f'The password for {email} cannot be reset using this bot.')
            return

        # Generate new password
        new_password = generate_random_password()

        # Update user password
        user_update = {
            'password': new_password,
            'changePasswordAtNextLogin': True
        }

        try:
            service.users().update(userKey=email, body=user_update).execute()
            
            # Get user info for the response
            user = service.users().get(userKey=email).execute()
            first_name = user['name']['givenName']
            last_name = user['name']['familyName']
            
            # Format response message
            response = (
                f"Password has been reset for {first_name} {last_name} ({email})\n\n"
                f"New temporary password: `{new_password}`\n\n"
                "User will be required to change password on next login."
            )
            
            # Send response with password in monospace format
            await update.message.reply_text(response, parse_mode='Markdown')
            
        except HttpError as e:
            error_message = e._get_reason() if hasattr(e, '_get_reason') else str(e)
            logger.error(f"Error resetting password: {error_message}")
            await update.message.reply_text(f'Error resetting password: {error_message}')
            
    except Exception as e:
        logger.error(f"Error in reset_password: {e}")
        await update.message.reply_text(f'An error occurred while resetting the password. Please try again later.')

def main() -> None:
    """Start the bot."""
    token = os.getenv('BOT_TOKEN')
    
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("suspend", suspend_user))
    application.add_handler(CommandHandler("userinfo", get_user_info))  # Add this line
    application.add_handler(CommandHandler("adduser", add_user))
    application.add_handler(CommandHandler("help", help_command))  # Add this line
    application.add_handler(CommandHandler("listusers", list_users))  # Add this line
    application.add_handler(CommandHandler("resetpw", reset_password))  # Add this line
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == '__main__':
    main()