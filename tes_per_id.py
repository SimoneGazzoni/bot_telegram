import logging
from telegram.ext import Updater, MessageHandler, Filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def handle_message(update, context):
    message = update.effective_message
    # Older versions might not support topics; adjust as needed.
    # Check if 'message_thread_id' exists in the message object:
    topic_id = getattr(message, 'message_thread_id', None)
    if topic_id is not None:
        print(f"Topic ID: {topic_id}")
    else:
        print("No topic ID (message is not in a topic).")

def main():
    # Use your bot token here
    updater = Updater("7213666662:AAHrgOCJZJxk7t0eRZ0irLfoKrMnIz3d7sU")
    dp = updater.dispatcher

    text_handler = MessageHandler(Filters.text & ~Filters.command, handle_message)
    dp.add_handler(text_handler)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
