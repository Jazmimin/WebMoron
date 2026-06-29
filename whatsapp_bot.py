import asyncio
import random
from urllib.parse import quote
from playwright.async_api import async_playwright
import openpyxl

VERSION = "1.0.0"

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

    async def add_contacts_from_excel(self, file_path):
        """Reads phone numbers and names from an Excel file and adds them to the agenda."""
        print(f"Reading contacts from {file_path}...")
        workbook = openpyxl.load_workbook(file_path)
        sheet = workbook.active

        for row in sheet.iter_rows(min_row=2, values_only=True):
            phone = row[0]
            name = row[1]

            if not phone or not name:
                continue

            # Cleanup phone number
            if isinstance(phone, float):
                phone = str(int(phone))
            else:
                phone = str(phone).strip()
            phone = "".join(filter(str.isdigit, phone))

            success = await self.add_contact(phone, name)
            if success:
                print(f"Successfully added {name} ({phone})")
            else:
                print(f"Failed to add {name} ({phone})")

            # Random delay
            delay = random.uniform(3, 7)
            await asyncio.sleep(delay)

    async def add_contact(self, phone, name):
        """Adds a single contact to the WhatsApp agenda."""
        print(f"Adding contact {name} ({phone})...")

        try:
            # 1. Open "New Chat" menu
            new_chat_selectors = ["[data-testid='chat-list-search']", "span[data-icon='chat']", "button[aria-label='New chat']"]
            await self.page.click(", ".join(new_chat_selectors))
            await asyncio.sleep(1)

            # 2. Click "New contact"
            new_contact_selectors = [
                "div:has-text('New contact')",
                "div:has-text('Nuevo contacto')",
                "[data-testid='new-contact-button']"
            ]
            await self.page.click(", ".join(new_contact_selectors))
            await asyncio.sleep(1)

            # 3. Fill details
            # First Name
            name_input = "input[aria-label='First name'], input[aria-label='Nombre']"
            await self.page.fill(name_input, str(name))

            # Phone
            phone_input = "input[aria-label='Phone number'], input[aria-label='Teléfono']"
            await self.page.fill(phone_input, str(phone))

            # 4. Click Save
            save_button = "div[role='button']:has-text('Save'), div[role='button']:has-text('Guardar')"
            await self.page.click(save_button)

            # Wait for save to complete or error
            await asyncio.sleep(2)

            # Close the contact pane if still open (success or error)
            close_button = "span[data-icon='x']"
            if await self.page.is_visible(close_button):
                await self.page.click(close_button)

            return True
        except Exception as e:
            print(f"Error adding contact {phone}: {e}")
            await self.page.screenshot(path=f"add_contact_error_{phone}.png")
            return False

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

            # Ensure phone is a clean string (Excel often reads them as floats like 123.0)
            if isinstance(phone, float):
                phone = str(int(phone))
            else:
                phone = str(phone).strip()

            # Robust cleanup: remove all non-digits
            phone = "".join(filter(str.isdigit, phone))

            if len(phone) < 10:
                print(f"Skipping {phone}: Number too short (missing country code?)")
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

    async def send_message(self, phone, message, retry_count=1):
        """Sends a message to a specific phone number with retry logic."""
        for attempt in range(retry_count + 1):
            if attempt > 0:
                print(f"Retrying send to {phone} (Attempt {attempt+1}/{retry_count+1})...")

            success = await self._do_send_message(phone, message)
            if success:
                return True

            # Brief wait before retry
            await asyncio.sleep(3)

        return False

    async def _do_send_message(self, phone, message):
        """Internal method to perform the message sending logic."""
        print(f"Sending message to {phone}...")
        # WhatsApp Web URL scheme for direct chat
        # URL encode phone and message to handle special characters
        safe_phone = quote(str(phone).strip("+"))
        safe_message = quote(str(message))
        url = f"https://web.whatsapp.com/send?phone={safe_phone}&text={safe_message}"

        try:
            # wait_until="load" for more completeness
            await self.page.goto(url, wait_until="load", timeout=60000)
        except Exception as e:
            print(f"Warning during navigation for {phone}: {e}")

        # Selectors for send button and invalid number popup
        # Expanded based on localization (Spanish/English) and various WhatsApp versions
        invalid_popup_selectors = [
            "div[role='button']:has-text('OK')",
            "button:has-text('OK')",
            "div[role='button']:has-text('Aceptar')",
            "button:has-text('Aceptar')",
            "div:has-text('Phone number shared via url is invalid')",
            "div:has-text('El número de teléfono compartido a través de la URL es inválido')",
            "[data-testid='popup-controls-ok']"
        ]
        send_button_selectors = [
            "span[data-icon='send']",
            "button[data-testid='compose-btn-send']",
            "[data-icon='send']",
            "button:has(span[data-icon='send'])",
            "div[aria-label='Send']",
            "div[aria-label='Enviar']",
            "button[aria-label='Send']",
            "button[aria-label='Enviar']",
            "footer div[role='button']:has(span[data-icon='send'])",
            "span[data-icon='send-light']",
            "span[data-icon='send-dark']",
            "button:has(span[data-icon='send-light'])",
            "button:has(span[data-icon='send-dark'])"
        ]

        invalid_selector = ", ".join(invalid_popup_selectors)
        send_selector = ", ".join(send_button_selectors)
        combined_selector = f"{send_selector}, {invalid_selector}"

        try:
            # 1. Wait for "Starting chat" overlay to disappear if present
            # Expanded to include Spanish "Iniciando chat"
            try:
                starting_overlay = "div:has-text('Starting chat'), div:has-text('Iniciando chat'), [role='progressbar']"
                await self.page.wait_for_selector(starting_overlay, state="hidden", timeout=20000)
            except:
                pass

            # 2. Wait for either the send button or an error popup
            print(f"Waiting for chat interface or error for {phone}...")
            element = await self.page.wait_for_selector(combined_selector, timeout=60000)

            if not element:
                print(f"Neither send button nor error popup appeared for {phone}.")
                await self.page.screenshot(path=f"send_error_{phone}.png")
                return False

            # Check if it was an invalid number popup
            is_invalid = False
            for sel in invalid_popup_selectors:
                try:
                    if await self.page.is_visible(sel):
                        is_invalid = True
                        break
                except:
                    continue

            if is_invalid:
                print(f"Phone number {phone} is invalid on WhatsApp.")
                try:
                    # Capture screenshot of the invalid popup for confirmation
                    await self.page.screenshot(path=f"invalid_{phone}.png")
                    await element.click() # Click OK to clear the popup
                except:
                    pass
                return False

            # If not invalid, it must be the send button
            # We use a force click in case it's partially obscured
            print(f"Send button found for {phone}, clicking...")
            await element.click(force=True)

            # Post-send verification: wait to see if the button disappears or the message is clear
            await asyncio.sleep(1)
            if await self.page.is_visible(send_selector):
                # Try clicking one more time if still visible
                try:
                    await element.click(force=True)
                    await asyncio.sleep(1)
                except:
                    pass

            print(f"Message sent to {phone}!")
            # Wait to ensure message is actually dispatched
            await asyncio.sleep(2)
            return True

        except Exception as e:
            print(f"Failed to send message to {phone}: {e}")
            await self.page.screenshot(path=f"send_exception_{phone}.png")
            return False
