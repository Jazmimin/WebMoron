import asyncio
import random
from urllib.parse import quote
from playwright.async_api import async_playwright
import openpyxl

VERSION = "1.0.2"

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
            viewport={"width": 1280, "height": 720},
            # Stealth: Hide automation flags
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

    async def stop(self):
        """Closes the browser."""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

    def _format_phone(self, phone):
        """Cleans and formats a phone number, adding Argentinian code if missing."""
        if isinstance(phone, float):
            phone = str(int(phone))
        else:
            phone = str(phone).strip()

        phone = "".join(filter(str.isdigit, phone))

        # Argentine fix: If 10 digits (e.g. 1135897647), add 549
        if len(phone) == 10:
            print(f"Detected 10-digit number {phone}. Adding Argentinian country code 549...")
            phone = "549" + phone

        return phone

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

            phone = self._format_phone(phone)

            success = await self.add_contact(phone, name)
            if success:
                print(f"Successfully added {name} ({phone})")
            else:
                print(f"Failed to add {name} ({phone})")

            # Random delay
            delay = random.uniform(3, 7)
            await asyncio.sleep(delay)

    async def add_contact(self, phone, name):
        """Adds a single contact to the WhatsApp agenda with robust selector detection."""
        print(f"Adding contact {name} ({phone})...")

        try:
            # 1. Open "New Chat" menu
            # Refined selectors for the 'New Chat' button (plus icon)
            new_chat_selectors = [
                "[data-testid='chat-list-search']",
                "span[data-icon='chat']",
                "button[aria-label='New chat']",
                "button[aria-label='Nuevo chat']",
                "header span[data-icon='plus']",
                "header span[data-icon='chat-add']"
            ]

            print("Searching for 'New Chat' button...")
            try:
                await self.page.wait_for_selector(", ".join(new_chat_selectors), timeout=10000)
                await self.page.click(", ".join(new_chat_selectors))
            except Exception as e:
                print(f"Could not find 'New Chat' button: {e}")
                await self.page.screenshot(path="add_contact_fail_step1.png")
                return False

            await asyncio.sleep(1)

            # 2. Click "New contact"
            # We use more specific child-of-menu selectors to avoid white-screen/background matches
            new_contact_selectors = [
                "[data-testid='cell-frame-container'] div:has-text('New contact')",
                "[data-testid='cell-frame-container'] div:has-text('Nuevo contacto')",
                "div[role='button']:has-text('New contact')",
                "div[role='button']:has-text('Nuevo contacto')",
                "[data-testid='new-contact-button']"
            ]

            print("Searching for 'New Contact' option...")
            try:
                # Wait for the specific menu container if possible
                await asyncio.sleep(1) # Extra breath for the menu to slide in
                await self.page.wait_for_selector(", ".join(new_contact_selectors), timeout=10000, state="visible")

                # Try clicking the one that is actually visible and has text
                found = False
                for sel in new_contact_selectors:
                    elements = await self.page.query_selector_all(sel)
                    for el in elements:
                        if await el.is_visible():
                            await el.click()
                            found = True
                            break
                    if found: break

                if not found:
                    raise Exception("No visible 'New Contact' button found")

            except Exception as e:
                print(f"Could not find 'New Contact' option: {e}")
                await self.page.screenshot(path="add_contact_fail_step2.png")
                return False

            await asyncio.sleep(1)

            # 3. Fill details
            print("Filling contact details...")
            # Detect form header first to ensure we are in the right pane
            form_header = "div:has-text('New contact'), div:has-text('Nuevo contacto')"
            try:
                await self.page.wait_for_selector(form_header, timeout=10000)
            except:
                print("Warning: Contact form header not detected, but attempting to fill anyway.")

            # Identify input fields by index if aria-labels fail (common in dynamic UIs)
            # Typically 0 is Name, 1 is Surname, 2 is Phone (or variations)
            inputs = await self.page.query_selector_all("input[type='text'], div[contenteditable='true']")

            # First Name
            name_inputs = [
                "input[aria-label='First name']",
                "input[aria-label='Nombre']",
                "input[placeholder='First name']",
                "input[placeholder='Nombre']"
            ]

            # Phone
            phone_inputs = [
                "input[aria-label='Phone number']",
                "input[aria-label='Teléfono']",
                "input[placeholder='Phone number']",
                "input[placeholder='Teléfono']"
            ]

            # Last Name (Apellido)
            surname_inputs = [
                "input[aria-label='Last name']",
                "input[aria-label='Apellido']",
                "input[aria-label='Apellidos']",
                "input[placeholder='Last name']",
                "input[placeholder='Apellido']"
            ]

            # Fill Name
            try:
                await self.page.wait_for_selector(", ".join(name_inputs), timeout=5000)
                await self.page.fill(", ".join(name_inputs), str(name))
            except:
                # Fallback: try filling the first text input found
                if len(inputs) > 0:
                    await inputs[0].fill(str(name))

            # Optional: Clear Surname if it's autofocusing or causing issues
            try:
                await self.page.fill(", ".join(surname_inputs), " ", timeout=2000)
            except:
                pass

            # Fill Phone
            try:
                await self.page.wait_for_selector(", ".join(phone_inputs), timeout=5000)
                await self.page.fill(", ".join(phone_inputs), str(phone))
            except:
                # Fallback: try filling the last text input or the second/third one
                if len(inputs) >= 2:
                    # Usually Phone is after Name/Surname
                    await inputs[-1].fill(str(phone))

            # 4. Click Save
            save_buttons = [
                "div[role='button']:has-text('Save')",
                "div[role='button']:has-text('Guardar')",
                "button:has-text('Save')",
                "button:has-text('Guardar')",
                "[data-testid='contact-edit-save-button']",
                "span:has-text('Save')",
                "span:has-text('Guardar')",
                "div[aria-label='Save']",
                "div[aria-label='Guardar']"
            ]

            print("Saving contact...")
            try:
                # Try clicking first
                await self.page.click(", ".join(save_buttons), timeout=10000)
            except:
                # Fallback: try pressing Enter if clicking failed
                print("Clicking save failed, trying Enter key...")
                await self.page.keyboard.press("Enter")

            # Wait for save to complete or error
            await asyncio.sleep(3)

            # Close the contact pane if still open (success or error)
            close_buttons = ["span[data-icon='x']", "button[aria-label='Close']", "button[aria-label='Cerrar']"]
            for btn in close_buttons:
                if await self.page.is_visible(btn):
                    await self.page.click(btn)
                    break

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

        count = 0
        for row in sheet.iter_rows(min_row=2, values_only=True):
            phone = row[0]
            message = row[1]

            if not phone or not message:
                continue

            phone = self._format_phone(phone)

            if len(phone) < 10:
                print(f"Skipping {phone}: Number too short.")
                continue

            success = await self.send_message(phone, message)
            if success:
                print(f"Successfully sent to {phone}")
            else:
                print(f"Failed to send to {phone}")

            # Random delay between messages
            delay = random.uniform(8, 15)

            count += 1
            # Human break: every 6 messages, wait longer
            if count % 6 == 0:
                break_time = random.uniform(60, 120)
                print(f"Taking a human break for {break_time:.2f} seconds...")
                await asyncio.sleep(break_time)
            else:
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

    async def _type_human_like(self, selector, text):
        """Types text character by character with random delays."""
        await self.page.click(selector)
        for char in text:
            await self.page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.05, 0.15))

    async def _do_send_message(self, phone, message):
        """Internal method to perform the message sending logic with stealth."""
        print(f"Opening chat for {phone}...")
        # WhatsApp Web URL scheme to open the chat without pre-filling text
        # Pre-filling text via URL is a strong bot indicator
        safe_phone = quote(str(phone).strip("+"))
        url = f"https://web.whatsapp.com/send?phone={safe_phone}"

        try:
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

            # 2. Wait for chat input or error
            chat_input = "div[contenteditable='true'][data-tab='10']"
            combined_selector_stealth = f"{chat_input}, {invalid_selector}"

            print(f"Waiting for chat interface or error for {phone}...")
            element = await self.page.wait_for_selector(combined_selector_stealth, timeout=60000)

            if not element:
                return False

            # Check if invalid
            is_invalid = False
            for sel in invalid_popup_selectors:
                if await self.page.is_visible(sel):
                    is_invalid = True
                    break

            if is_invalid:
                print(f"Phone number {phone} is invalid.")
                await element.click()
                return False

            # 3. Type message manually (Stealth)
            print(f"Typing message for {phone}...")
            await self._type_human_like(chat_input, message)
            await asyncio.sleep(random.uniform(1, 2))

            # 4. Find and click send button
            # Re-detecting send button because it usually appears after typing
            send_btn = await self.page.wait_for_selector(send_selector, timeout=10000)
            if send_btn:
                await send_btn.click(force=True)
                print(f"Message sent to {phone}!")
                await asyncio.sleep(2)
                return True

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
