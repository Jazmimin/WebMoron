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
        # Use a more modern and common User-Agent
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.session_dir,
            headless=self.headless,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
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
        try:
            await self.page.goto("https://web.whatsapp.com", timeout=90000, wait_until="networkidle")
        except Exception as e:
            print(f"Navigation warning: {e}. Continuing anyway...")

        # Wait for either the QR code, the main interface, or an error message
        qr_selector = "canvas, [data-testid='qrcode']"
        main_selector = "div[contenteditable='true'][data-tab='3'], #pane-side, [data-testid='chat-list']"
        error_selector = ".landing-title, ._ak72, [data-testid='update-browser-title']" # Selectors for error/update pages

        print("Checking page state...")
        try:
            # Wait for either the QR code or the logged-in state to appear
            # Increased timeout to 90 seconds for slower connections
            await self.page.wait_for_selector(f"{qr_selector}, {main_selector}, {error_selector}", timeout=90000)

            # Check if it's the QR code
            if await self.page.query_selector(qr_selector):
                print("QR code detected. Waiting for scan...")

                # Loop to keep refreshing the QR code screenshot until logged in or timeout
                # Increased timeout to 5 minutes to give the user enough time
                for i in range(10): # 10 * 30s = 300s (5 minutes)
                    if await self.page.query_selector(main_selector):
                        break

                    print(f"Refreshing QR code screenshot... (Attempt {i+1}/10)")
                    await self.page.screenshot(path=qr_path)
                    print(f">>> Action Required: Scan {qr_path} with your phone.")

                    try:
                        # Wait for the main interface to appear with a short timeout
                        await self.page.wait_for_selector(main_selector, timeout=30000)
                        break
                    except Exception:
                        continue
            else:
                print("Already logged in, skipping QR scan.")
        except Exception as e:
            print(f"Neither QR code nor main interface appeared: {e}")
            await self.page.screenshot(path="login_error.png")
            print("Saved 'login_error.png' for troubleshooting.")
            return False

        # Wait for the main app to load
        print("Finalizing login...")
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

        try:
            await self.page.goto(url, wait_until="domcontentloaded")
        except Exception as e:
            print(f"Warning during navigation: {e}")

        # Check for invalid number popup or send button
        # Multiple selector options for better robustness
        invalid_popup_selectors = ["div[role='button']:has-text('OK')", "button:has-text('OK')", "div:has-text('Phone number shared via url is invalid')"]
        send_button_selectors = ["span[data-icon='send']", "button[data-testid='compose-btn-send']", "[data-icon='send']"]

        invalid_selector = ", ".join(invalid_popup_selectors)
        send_selector = ", ".join(send_button_selectors)

        # Create tasks for waiting
        send_task = asyncio.create_task(self.page.wait_for_selector(send_selector, timeout=60000))
        invalid_task = asyncio.create_task(self.page.wait_for_selector(invalid_selector, timeout=60000))

        try:
            # Wait for either the send button or an error popup
            done, pending = await asyncio.wait(
                [send_task, invalid_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel the pending task to avoid "Task exception was never retrieved" errors
            for task in pending:
                task.cancel()

            # Check if invalid popup was the one that finished
            if invalid_task in done and not invalid_task.cancelled() and invalid_task.exception() is None:
                print(f"Phone number {phone} is invalid on WhatsApp (detected via popup).")
                try:
                    # Try to click the OK button to clear the state
                    ok_btn = await self.page.query_selector(invalid_selector)
                    if ok_btn:
                        await ok_btn.click()
                except:
                    pass
                return False

            # Otherwise, check if send button is ready
            if send_task in done and not send_task.cancelled() and send_task.exception() is None:
                await self.page.click(send_selector)
                print(f"Message sent to {phone}!")
                await asyncio.sleep(2)
                return True

            # If we are here, something else happened (e.g. both timed out)
            print(f"Could not find send button or error popup for {phone}.")
            await self.page.screenshot(path=f"send_error_{phone}.png")
            return False

        except Exception as e:
            print(f"Failed to send message to {phone}: {e}")
            # Ensure tasks are cancelled on error
            send_task.cancel()
            invalid_task.cancel()
            return False
