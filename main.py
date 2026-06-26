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

        # Check if we should process an excel file, send a single message, or just login
        if "--excel" in sys.argv:
            try:
                excel_index = sys.argv.index("--excel")
                file_path = sys.argv[excel_index + 1]
                await bot.login()
                await bot.send_messages_from_excel(file_path)
            except (ValueError, IndexError):
                print("Usage: python main.py --excel <path_to_excel_file>")
        elif len(sys.argv) >= 3:
            phone = sys.argv[1]
            message = " ".join(sys.argv[2:])

            # Ensure we are logged in before sending
            await bot.login()
            await bot.send_message(phone, message)
        else:
            print("Usage:")
            print("  Single message: python main.py <phone_number> <message>")
            print("  Excel list:     python main.py --excel <path_to_excel_file>")
            print("  Login only:     python main.py")
            print("\nOptions:")
            print("  --head: Run in non-headless mode (visible browser window)")

            print("\nRunning in login mode. Scan the QR code if prompted.")
            await bot.login()

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
