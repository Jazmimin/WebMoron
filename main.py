import asyncio
import sys
from whatsapp_bot import WhatsAppBot

async def main():
    # Use --head for non-headless mode
    headless = "--head" not in sys.argv
    if not headless:
        sys.argv.remove("--head")

    bot = WhatsAppBot(headless=headless)
    try:
        await bot.start()

        # Check if we should just login or also send a message
        if len(sys.argv) < 3:
            print("Usage: python main.py <phone_number> <message>")
            print("Running in login mode. Scan the QR code if prompted.")
            await bot.login()
        else:
            phone = sys.argv[1]
            message = " ".join(sys.argv[2:])

            # Ensure we are logged in before sending
            # Note: bot.login() will wait for the main interface
            await bot.login()
            await bot.send_message(phone, message)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
