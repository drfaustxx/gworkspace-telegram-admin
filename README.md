# Google Workspace Management through Telegram Bot

This project automates the tasks of creating new Google Workspace accounts and suspending them via text commands in Telegram messenger.

## Requirements

1. **Google Workspace (Gsuite) account with your domain**
2. **Google Cloud account for using Google API:**
   - G Suite Admin API to create and suspend accounts
   - Gmail API for sending emails
   - Google Sheets API to store the list of created accounts
3. **Telegram account**

## Configuring the Google Workspace Admin in Telegram

1. **Register your bot in Telegram:**
   - Use @BotFather to register your bot and save its token to `config.py`.

2. **Create a Google Sheet and access its API:**
   - Create a new Google Sheet.
   - Go to the Google Cloud Console and create a new project.
   - Enable the API for Google Sheets and Google Drive.
   - Create credentials to access the API and save a JSON file with the key to the `credentials/` directory.
   - Put the filename obtained from Google into `config.py`.

3. **Set up Google Workspace API:**
   - Enable the Admin SDK API.
   - Create credentials, upload, and save a JSON file with the key to the `credentials/` directory.
   - Put the filename obtained from Google into `config.py`.

4. **Using the Gmail API:**
   - Enable the Gmail API in the Google Cloud Console.
   - Run `test_gmail.py`, follow the web page instructions to authorize email sending through your account. It will save a token to `credentials/gmail_token.json`.

## Running the Bot

### Using Docker Compose

```sh
docker-compose up -d
```

### Using systemd

1. Copy `telegrambot.service` to `/etc/systemd/system`
2. Copy this repo to `/usr/local/gworkspace-telegram-admin/`
3. `pip install --no-cache-dir -r requirements.txt`
4. `sudo systemctl daemon-reload`
5. `sudo systemctl start telegrambot`
6. `sudo systemctl enable telegrambot`

Logs can be managed and viewed using `journalctl`:

```sh
sudo journalctl -u telegrambot