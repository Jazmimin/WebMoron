import asyncio
import argparse
import sys
from whatsapp_bot import WhatsAppBot, VERSION

async def main():
    parser = argparse.ArgumentParser(description=f"WhatsApp Web Bot v{VERSION}")

    # Flags
    parser.add_argument("--head", action="store_true", help="Run in non-headless mode (visible browser)")

    # Mutual exclusive groups or individual arguments
    parser.add_argument("--excel", metavar="PATH", help="Send messages to a list from Excel")
    parser.add_argument("--add-excel-contacts", metavar="PATH", help="Add contacts to agenda from Excel")
    parser.add_argument("--add-contact", nargs=2, metavar=("PHONE", "NAME"), help="Add a single contact to agenda")

    # Positional arguments for single message
    parser.add_argument("phone", nargs="?", help="Phone number for single message")
    parser.add_argument("message", nargs="*", help="Message text for single message")

    args = parser.parse_args()

    print(f"--- WhatsApp Web Bot v{VERSION} ---")

    bot = WhatsAppBot(headless=not args.head)
    try:
        await bot.start()

        # Decide action
        if args.excel:
            await bot.login()
            await bot.send_messages_from_excel(args.excel)
        elif args.add_excel_contacts:
            await bot.login()
            await bot.add_contacts_from_excel(args.add_excel_contacts)
        elif args.add_contact:
            await bot.login()
            await bot.add_contact(args.add_contact[0], args.add_contact[1])
        elif args.phone and args.message:
            await bot.login()
            full_message = " ".join(args.message)
            await bot.send_message(args.phone, full_message)
        else:
            # No specific command provided, just show help or default to login
            if len(sys.argv) <= 1 or (len(sys.argv) == 2 and args.head):
                print("Running in login mode. Scan the QR code if prompted.")
                await bot.login()
            else:
                parser.print_help()

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
