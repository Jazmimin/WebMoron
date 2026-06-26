import asyncio
from urllib.parse import quote
from playwright.async_api import async_playwright

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
        print("Navigating to WhatsApp Web...")
        await self.page.goto("https://web.whatsapp.com")

        # Wait for the QR code to appear or the main interface if already logged in
        try:
            # Selector for the QR code canvas
            await self.page.wait_for_selector("canvas", timeout=10000)
            print(f"QR code found. Saving to {qr_path}...")
            await self.page.screenshot(path=qr_path)
            print("Please scan the QR code to log in.")
        except Exception:
            print("QR code not found, you might be already logged in.")

        # Wait for the main app to load (search bar or message list)
        print("Waiting for login...")
        await self.page.wait_for_selector("div[contenteditable='true'][data-tab='3']", timeout=60000)
        print("Login successful!")

    async def send_message(self, phone, message):
        """Sends a message to a specific phone number."""
        print(f"Sending message to {phone}...")
        # WhatsApp Web URL scheme for direct chat
        # URL encode phone and message to handle special characters
        safe_phone = quote(str(phone))
        safe_message = quote(str(message))
        url = f"https://web.whatsapp.com/send?phone={safe_phone}&text={safe_message}"
        await self.page.goto(url)

        # Wait for the send button or the text area to be ready
        try:
            # The "Send" button usually appears after the message is pre-filled
            # Selector for the send button (it's often a button with a 'send' icon)
            send_button_selector = "span[data-icon='send']"
            await self.page.wait_for_selector(send_button_selector, timeout=20000)
            await self.page.click(send_button_selector)
            print(f"Message sent to {phone}!")
            # Brief wait to ensure the message is processed
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Failed to send message to {phone}: {e}")
