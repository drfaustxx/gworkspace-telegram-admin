# Google Workspace credentials obtained in console.cloud.google.com
GWORKSPACE_CREDS_FILE = "credentials/white-rigging-YOURFILE.json"
GWORKSPACE_ADMIN_ACCOUNT = "admin@yourdomain.com"

# Google Sheets file name (find it in Google Drive)
SPREADSHEET_FILENAME = 'Emails_created_via_bot'


# from which address emails will be sent
GMAIL_SENDER_ADDRESS = 'noreply@yourdomain.com'
# and its credentials 
GMAIL_CREDENTIALS_FILE = 'credentials/client_secret_YOURFILE.apps.googleusercontent.com.json'
GMAIL_TOKEN_FILE = 'credentials/gmail_token.json'


# List of allowed Telegram usernames to control your bot
BOT_ALLOWED_USERS = ["@your_telegram_username"]

# List of protected accounts that cannot be suspended
BOT_PROTECTED_ACCOUNTS = ['admin@yourdomain.com', 'noreply@yourdomain.com']

# from @Botfather 
BOT_TOKEN = 'your bot token'

# Email signature
EMAIL_SIGNATURE_LASTLINE = 'Your company name'