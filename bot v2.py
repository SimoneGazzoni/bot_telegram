import os
import re
import json
import csv
import time
import logging
import matplotlib.pyplot as plt
import matplotlib
import pandas as pd
import io
from telegram import InputFile, Update
from datetime import datetime, timedelta
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# 🔧 Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 📌 Costanti Globali
TWO_DAYS = 2 * 24 * 60 * 60      # Timer di default: 2 giorni (in secondi)
REMINDER_INTERVAL = 4 * 60 * 60    # Reminder ogni 4 ore (in secondi)
DATA_FILE = "bot_data_old.json"
EGGS_FILE = "eggs.csv"

# ID del topic consentito
ALLOWED_TOPIC_ID = 6

# 🛠️ Funzioni per la gestione dei dati
def load_data():
    return json.load(open(DATA_FILE)) if os.path.exists(DATA_FILE) else {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def get_chat_data(chat_id, bot_data):
    if str(chat_id) not in bot_data:
        bot_data[str(chat_id)] = {"last_command_time": None, "reminders_active": False}
    return bot_data[str(chat_id)]

# 🔍 Funzione per controllare se il messaggio proviene dal topic consentito
def check_topic(update: Update) -> bool:
    topic_id = getattr(update.message, "message_thread_id", None)
    logger.info(topic_id)
    return topic_id == ALLOWED_TOPIC_ID



# 🔥 Timer Management
def remove_jobs(chat_id, context: CallbackContext):
    for job_name_prefix in ("deadline", "reminder"):
        for job in context.job_queue.get_jobs_by_name(f"{job_name_prefix}_{chat_id}"):
            job.schedule_removal()

def schedule_deadline(chat_id, context: CallbackContext, topic_id):
    context.job_queue.run_once(
        callback=deadline_job,
        when=TWO_DAYS,
        context={"chat_id": chat_id, "topic_id": topic_id},
        name=f"deadline_{chat_id}"
    )

# 🚨 Funzione per il deadline
def deadline_job(context: CallbackContext):
    job_context = context.job.context
    chat_id = job_context["chat_id"]
    topic_id = job_context["topic_id"]

    bot_data = load_data()
    chat_data = get_chat_data(chat_id, bot_data)

    if chat_data.get("last_command_time") is None:
        return

    if (time.time() - chat_data["last_command_time"]) >= TWO_DAYS:
        context.bot.send_message(
            chat_id,
            text=f"⚠️ Sono passate {TWO_DAYS/3600:.0f} ore! Invia /sono_andato_oggi ORA! 😡🥚",
            message_thread_id=topic_id
        )
        chat_data["reminders_active"] = True
        context.job_queue.run_repeating(
            reminder_job,
            interval=REMINDER_INTERVAL,
            first=0,
            context={"chat_id": chat_id, "topic_id": topic_id},
            name=f"reminder_{chat_id}"
        )
        save_data(bot_data)

# 🔔 Reminder ripetuto ogni 4 ore (invio solo se tra le 9 e le 10)
def reminder_job(context: CallbackContext):
    job_context = context.job.context
    chat_id = job_context["chat_id"]
    topic_id = job_context["topic_id"]
    if 9 <= datetime.now().hour < 22:
        context.bot.send_message(
            chat_id,
            text="‼️ MUOVETE IL CULO E ANDATE A FEEDDARE LE GALLINE ‼️",
            message_thread_id=topic_id
        )
        context.bot.send_message(
            chat_id,
            text="‼️ CACIO VAI ORAAAAAAAA‼️",
            message_thread_id=topic_id
        )

# 🏁 Comandi Bot
def start_command(update: Update, context: CallbackContext):
    if not check_topic(update):
        logger.info("start_command ignorato: messaggio non nel topic %s.", ALLOWED_TOPIC_ID)
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id
    bot_data = load_data()
    chat_data = get_chat_data(chat_id, bot_data)

    remove_jobs(chat_id, context)
    chat_data["last_command_time"] = time.time()
    chat_data["reminders_active"] = False
    save_data(bot_data)

    schedule_deadline(chat_id, context, topic_id)

    update.message.reply_text(
        f"🔥 Timer di {TWO_DAYS/3600:.0f} ore impostato! Feeddate ste galline o si cacasburano. 🔥",
        message_thread_id=topic_id
    )

def sono_andato_oggi_command(update: Update, context: CallbackContext):
    if not check_topic(update):
        logger.info("sono_andato_oggi_command ignorato: messaggio non nel topic %s.", ALLOWED_TOPIC_ID)
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id
    bot_data = load_data()
    chat_data = get_chat_data(chat_id, bot_data)

    chat_data["last_command_time"] = time.time()
    chat_data["reminders_active"] = False
    save_data(bot_data)

    remove_jobs(chat_id, context)
    schedule_deadline(chat_id, context, topic_id)

    update.message.reply_text(
        "✅ Bene, giovane allevatore di galline. Ci sentiamo alla prossima. 🐔🥚",
        message_thread_id=topic_id
    )


def stat_command(update: Update, context: CallbackContext):
    if not check_topic(update):
        logger.info("stat_command ignored: message not from allowed topic %s.", ALLOWED_TOPIC_ID)
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id
    if not os.path.isfile(EGGS_FILE):
        update.message.reply_text("⚠️ Niente uova nel database fratm 🥚", message_thread_id=topic_id)
        return

    cutoff_date = datetime.now() - timedelta(days=30)
    daily_totals = {}

    with open(EGGS_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row["chat_id"]) == str(chat_id):
                row_date = datetime.strptime(row["date"], "%Y-%m-%d")
                if row_date >= cutoff_date:
                    day_str = row_date.strftime("%Y-%m-%d")
                    daily_totals[day_str] = daily_totals.get(day_str, 0) + int(row["eggs"])

    if not daily_totals:
        update.message.reply_text("📉 Niente uova questo mese broke ass nigga 🥚💀", message_thread_id=topic_id)
        return

    df = pd.DataFrame(list(daily_totals.items()), columns=["Data", "Uova"])
    df["Data"] = pd.to_datetime(df["Data"])
    df = df.sort_values("Data")

    # Compute the 7-day moving average. For days with fewer than 7 records, it computes average of available data.
    df["7_day_avg"] = df["Uova"].rolling(window=7, min_periods=1).mean()

    matplotlib.use('Agg')
    plt.figure(figsize=(10, 5))

    # Plot the daily totals line
    plt.plot(df["Data"], df["Uova"], marker="o", linestyle="-", color="orange", label="Daily Eggs")
    # Plot the 7-day moving average line
    plt.plot(df["Data"], df["7_day_avg"], marker="o", linestyle="--", color="blue", label="7-Day Average")

    plt.xlabel("Data 📅")
    plt.ylabel("Numero di uova 🥚")
    plt.title("📈 Produzione giornaliera(Ultimi 30 giorni)")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.legend()

    img_bytes = io.BytesIO()
    plt.savefig(img_bytes, format="png")
    plt.close()
    img_bytes.seek(0)

    update.message.reply_photo(
        photo=InputFile(img_bytes, filename="eggs_chart.png"),
        caption="📊 Sparati ste stats ovipare 🥚🔥",
        message_thread_id=topic_id
    )
def reset_command(update: Update, context: CallbackContext):
    if not check_topic(update):
        logger.info("reset_command ignorato: messaggio non nel topic %s.", ALLOWED_TOPIC_ID)
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id
    remove_jobs(chat_id, context)
    update.message.reply_text(
        "🛑 Tutto resettato, coglione. Timer e promemoria bloccati. Usa /start per ricominciare.",
        message_thread_id=topic_id
    )

def handle_message(update: Update, context: CallbackContext):
    if not check_topic(update):
        logger.info("handle_message ignorato: messaggio non nel topic %s.", ALLOWED_TOPIC_ID)
        return

    global TWO_DAYS
    text = update.message.text.strip().lower()
    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id

    # Se il messaggio è del tipo "<numero> ore", aggiorna il timer
    match = re.match(r"(\d+)\s*ore$", text)
    if match:
        ore = int(match.group(1))
        TWO_DAYS = ore * 3600  # Imposta il timer in secondi
        update.message.reply_text(
            f"⏳ Timer aggiornato! Ora il promemoria scatta tra {ore} ore. 🔥",
            message_thread_id=topic_id
        )
        return

    # Se il messaggio è del tipo "<numero> uova", registra il numero di uova
    match_uova = re.search(r"(\+?\d+)\s*uova", text, re.IGNORECASE)
    if match_uova:
        eggs = int(match_uova.group(1))
        if eggs < 0:
            update.message.reply_text(
                "❌ Niente uova negative, fratello. Che stai combinando? 🤨",
                message_thread_id=topic_id
            )
            return
        save_eggs(chat_id, eggs)
        update.message.reply_text(
            f"✅ *{eggs}* uova segnate, continua a far cash 🥚💰",
            parse_mode="Markdown",
            message_thread_id=topic_id
        )
        return

    # Se il messaggio contiene solo un numero (senza "ore" o "uova"), registra il numero di uova
    try:
        eggs = int(text)
        if eggs < 0:
            update.message.reply_text(
                "❌ Niente uova negative, fratello. Che stai combinando? 🤨",
                message_thread_id=topic_id
            )
            return
        save_eggs(chat_id, eggs)
        update.message.reply_text(
            f"✅ *{eggs}* uova segnate, continua a far cash 🥚💰",
            parse_mode="Markdown",
            message_thread_id=topic_id
        )
    except ValueError:
        logger.info("Messaggio da ignorare")

def save_eggs(chat_id, eggs):
    today_str = datetime.now().strftime("%Y-%m-%d")
    # Se il file non esiste, scrive anche l'intestazione
    file_exists = os.path.isfile(EGGS_FILE)
    with open(EGGS_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["date", "eggs", "chat_id"])
        writer.writerow([today_str, eggs, chat_id])

def restore_schedules(updater: Updater):
    """
    Ripristina i job (deadline e reminder) al riavvio del bot.
    """
    bot_data = load_data()
    now = time.time()

    for chat_id, data in bot_data.items():
        if data["last_command_time"] is None:
            continue

        last_time = data["last_command_time"]
        delta = now - last_time

        if delta < TWO_DAYS:
            remaining_time = TWO_DAYS - delta
            updater.job_queue.run_once(
                callback=deadline_job,
                when=remaining_time,
                context={"chat_id": int(chat_id), "topic_id": ALLOWED_TOPIC_ID},
                name=f"deadline_{chat_id}"
            )
            logger.info(f"🔄 Ripristinato deadline per chat {chat_id} tra {remaining_time // 3600} ore.")
        elif data.get("reminders_active", False):
            updater.job_queue.run_repeating(
                callback=reminder_job,
                interval=REMINDER_INTERVAL,
                first=0,
                context={"chat_id": int(chat_id), "topic_id": ALLOWED_TOPIC_ID},
                name=f"reminder_{chat_id}"
            )
            logger.info(f"🔄 Ripristinati i promemori  a per chat {chat_id}.")

def main():
    TOKEN = "7213666662:AAHrgOCJZJxk7t0eRZ0irLfoKrMnIz3d7sU"
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start_command))
    dp.add_handler(CommandHandler("sono_andato_oggi", sono_andato_oggi_command))
    dp.add_handler(CommandHandler("stat", stat_command))
    dp.add_handler(CommandHandler("reset", reset_command))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # 🔄 Ripristina i job esistenti al riavvio
    restore_schedules(updater)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
