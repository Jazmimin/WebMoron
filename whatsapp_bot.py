import asyncio
import random
from urllib.parse import quote
from playwright.async_api import async_playwright
import openpyxl

class WhatsAppBot:
    def __init__(self, session_dir="wa_session", headless=True):
        self.session_dir = session_dir
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self):
        """Initializes the browser and context."""
        self.playwright = await async_playwright().start()
        # Use persistent context to save login session
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.session_dir,
            headless=self.headless,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

    async def stop(self):
        """Closes the browser."""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

    async def login(self, qr_path="qr_code.png"):
        """Navigates to WhatsApp Web and waits for the user to scan the QR code."""
        print("Navigating to WhatsApp Web (this may take a moment)...")
        # Increase navigation timeout
        await self.page.goto("https://web.whatsapp.com", timeout=60000)

        # Wait for either the QR code or the main interface
        qr_selector = "canvas, [data-testid='qrcode']"
        main_selector = "div[contenteditable='true'][data-tab='3'], #pane-side, [data-testid='chat-list']"

        print("Checking page state...")
        try:
            # Wait for either the QR code or the logged-in state to appear
            await self.page.wait_for_selector(f"{qr_selector}, {main_selector}", timeout=30000)

            # Check if it's the QR code
            if await self.page.query_selector(qr_selector):
                print(f"QR code detected. Saving to {qr_path}...")
                # Give it a small extra time to render fully
                await asyncio.sleep(2)
                await self.page.screenshot(path=qr_path)
                print(">>> Action Required: Please open qr_code.png and scan it with your phone.")
            else:
                print("Already logged in, skipping QR scan.")
        except Exception as e:
            print(f"Neither QR code nor main interface appeared: {e}")
            await self.page.screenshot(path="login_error.png")
            print("Saved 'login_error.png' for troubleshooting.")
            return False

        # Wait for the main app to load
        print("Waiting for main interface to be ready...")
        try:
            await self.page.wait_for_selector(main_selector, timeout=60000)
            print("Login successful!")
            return True
        except Exception:
            print("Timeout waiting for main interface. Try running with --head to see what is happening.")
            await self.page.screenshot(path="login_timeout.png")
            return False

    async def send_messages_from_excel(self, file_path):
        """Reads phone numbers and messages from an Excel file and sends them."""
        print(f"Reading messages from {file_path}...")
        workbook = openpyxl.load_workbook(file_path)
        sheet = workbook.active

        for row in sheet.iter_rows(min_row=2, values_only=True):
            phone = row[0]
            message = row[1]

            if not phone or not message:
                continue

            success = await self.send_message(phone, message)
            if success:
                print(f"Successfully sent to {phone}")
            else:
                print(f"Failed to send to {phone}")

            # Random delay between messages to avoid being flagged
            delay = random.uniform(5, 10)
            print(f"Waiting {delay:.2f} seconds before next message...")
            await asyncio.sleep(delay)

    async def send_message(self, phone, message):
        """Sends a message to a specific phone number."""
        print(f"Sending message to {phone}...")
        # WhatsApp Web URL scheme for direct chat
        # URL encode phone and message to handle special characters
        safe_phone = quote(str(phone).strip("+"))
        safe_message = quote(str(message))
        url = f"https://web.whatsapp.com/send?phone={safe_phone}&text={safe_message}"
        await self.page.goto(url)

        try:
            # Check for invalid number popup or send button
            # We use race condition to see which one appears first
            # The invalid number popup often has a button with text "OK"
            invalid_popup_selector = "div[role='button']:has-text('OK')"
            send_button_selector = "span[data-icon='send']"

            # Wait for either the send button or an error popup
            result = await asyncio.wait([
                asyncio.create_task(self.page.wait_for_selector(send_button_selector, timeout=30000)),
                asyncio.create_task(self.page.wait_for_selector(invalid_popup_selector, timeout=30000))
            ], return_when=asyncio.FIRST_COMPLETED)

            # Check if invalid popup is present
            if await self.page.query_selector(invalid_popup_selector):
                print(f"Phone number {phone} is invalid on WhatsApp.")
                await self.page.click(invalid_popup_selector)
                return False

            await self.page.click(send_button_selector)
            print(f"Message sent to {phone}!")
            await asyncio.sleep(2)
            return True
        except Exception as e:
            print(f"Failed to send message to {phone}: {e}")
            return False
