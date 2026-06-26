# WhatsApp Web Automation Bot

This is a simple WhatsApp Web automation bot built with Python and Playwright. It allows you to send messages through the WhatsApp Web interface, bypassing the need for the official API.

## Features

- **Browser Automation:** Uses Playwright to interact with WhatsApp Web.
- **Persistent Session:** Saves your login session in a local directory (`wa_session`), so you only need to scan the QR code once.
- **Direct Messaging:** Send messages to any phone number using the WhatsApp Web URL scheme.

## Prerequisites

- Python 3.9+
- Node.js (required by Playwright)

## Installation

1. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Install Playwright browsers:
   ```bash
   playwright install chromium
   ```

## Usage

### Initial Login

To log in for the first time, run the script without arguments:
```bash
python main.py
```
A screenshot of the QR code will be saved as `qr_code.png`. Open this image and scan it with your WhatsApp mobile app (Linked Devices > Link a Device).

### Sending a Message

Once logged in, you can send messages using the following command:
```bash
python main.py <phone_number> <message>
```
Example:
```bash
python main.py 1234567890 "Hello from my automated bot!"
```
*Note: Include the country code in the phone number without any symbols (e.g., `1234567890` instead of `+1 (234) 567-890`).*

## File Structure

- `whatsapp_bot.py`: Contains the `WhatsAppBot` class and automation logic.
- `main.py`: The entry point for the CLI.
- `requirements.txt`: List of Python dependencies.
- `wa_session/`: (Generated) Stores browser session data for persistent login.
- `qr_code.png`: (Generated) Screenshot of the login QR code.

## Disclaimer

This project is for educational purposes only. Automated use of WhatsApp may violate their [Terms of Service](https://www.whatsapp.com/legal/terms-of-service/). Use it responsibly.
