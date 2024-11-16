from google.oauth2 import service_account
from googleapiclient.discovery import build
import sys
import os
import logging

# Add the directory containing config.py to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv

load_dotenv()

# Constants
SCOPES = ['https://www.googleapis.com/auth/admin.directory.user']
MAX_RESULTS = 10

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_domain_from_admin_account():
    """Extract the domain from the GWORKSPACE_ADMIN_ACCOUNT email address."""
    return os.getenv('GWORKSPACE_ADMIN_ACCOUNT').split('@')[1]

def list_users():
    """List the first 10 users in the domain."""
    creds = service_account.Credentials.from_service_account_file(os.getenv('GWORKSPACE_CREDS_FILE'), scopes=SCOPES)
    delegated_creds = creds.with_subject(os.getenv('GWORKSPACE_ADMIN_ACCOUNT'))
    service = build('admin', 'directory_v1', credentials=delegated_creds)

    logger.info('Getting the first %d users in the domain', MAX_RESULTS)
    try:
        results = service.users().list(domain=get_domain_from_admin_account(), viewType="domain_public", maxResults=MAX_RESULTS).execute()
        users = results.get('users', [])
    except Exception as e:
        logger.error('An error occurred: %s', e)
        return "error"

    if not users:
        logger.info('No users in the domain.')
    else:
        logger.info('Users:')
        for user in users:
            logger.info('%s (%s)', user['primaryEmail'], user['name']['fullName'])
    
    return "ok"

if __name__ == "__main__":
    list_users()