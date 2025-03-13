import os
import re
import json
import csv
import time
import logging
import random
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import io
from datetime import datetime, timedelta
from telegram import Update, InputFile, Chat
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
# Directory containing celebration photos
CELEBRATION_FOLDER = "home/zebbi/img/"  # update with your folder path

# -----------------------------
#    CONFIG & LOGGING
# -----------------------------
logging.basicConfig(
    level=logging.DEBUG,  # Change INFO to DEBUG for more detailed logs
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),  # Logs to file
        logging.StreamHandler()  # Logs to console (PyCharm terminal)
    ]
)
logger = logging.getLogger(__name__)

# -----------------------------
#      GLOBAL CONSTANTS
# -----------------------------
TWO_DAYS = 2 * 24 * 60 * 60  # 2 days in seconds
REMINDER_INTERVAL = 4 * 60 * 60  # 4 hours in seconds

DATA_FILE = "bot_data.json"
EGGS_FILE = "eggs.csv"
# SOLD_FILE now stores: date, eggs_sold, price_per_egg, chat_id
SOLD_FILE = "sold.csv"

MAIN_GROUP_ID = -1002454851481  # your real group ID
ALLOWED_TOPIC_ID = 6  # feeding topic ID
SELL_TOPIC_ID = 322  # sales topic ID

WORKERS_DICT = {
    "mario": "Mario",
    "marietto": "Mario",
    "marione": "Mario",
    "dario": "Mario",
    "fischiante": "Lambruschi",
    "lambru": "Lambruschi",
    "lambruschi": "Lambruschi",
    "sali": "Sali",
    "tenzo": "Sali",
    "cacio": "Caciotta",
    "caciotta": "Caciotta",
    "sia": "Dema",
    "sya": "Dema",
    "dema": "Dema",
    "leo": "Dema",
    "ambro": "Ambro",
    "demasia": "Dema",
    "cazzo": "Simone",
    "simo": "Simone",
    "gazzo": "Simone",
    "gazzoni": "Simone",
    "simone": "Simone",
    "jack": "Jack",
    "mino": "Jack",
    "giacomo": "Jack",
    "minetti": "Jack"
}

USER_ID_DICT = {
    317624352: "Simone",  # admin
    277828600: "Mario",
    833522284: "Sali",
    7896164328: "Jack",
    529432334: "Caciotta",
    1480298757: "Lambruschi",
    343096546: "Ambro",
    190249762: "Dema"
}

EGG_PRICE = 0.50  # default price if missing

SPECIAL_USER_ID = 529432334
ADMIN_ID = 317624352

SPECIAL_USER_REPLIES = [
    "Ma succhiami sto cazzo elettronico coglione!",
    "Sisi continua a dire cazzate scemo",
    "Succhia",
    "Ma fammi una sega",
    "Ma quante cazzate spari",
    "Ah scemooooooooo",
    "Caciotta sono morte tutte le galline",
    "AH SCEMOOOOOOO",
    "Ecco questa è una stronzata",
    "Dio ca se parli",
    "Cacio sono scappate tutte la galline",
    "Dio canaglia questa l'hai detta grossa",
    "💀",
    "Ti supplico sposami, tutto quello che dici è geniale",
    "Suca scemo",
    "Cacio sono un bot, è inutile che ti incazzi",
    "Ma ti sei rincoglionito del tutto",
    "Che turbo botta che c'hai fratmo",
    "WEEE ALLEVATOREEEE",
    "Cacio sei il numero uno❤️",
    "Continua a parlare delle galline in questo modo e ti frulliamo nel pollaio",
    "Dio ladro"
]

# -----------------------------
#         LOAD / SAVE
# -----------------------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "last_command_time": None,
        "reminders_active": False,
        "presence_data": {}
    }


def get_random_photo(folder_path):
    """
    Returns an InputFile object for a random image from the folder.
    Supports .png, .jpg, .jpeg, and .gif.
    """
    images = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]

    if not images:
        return None  # No images found, return None

    random_image = random.choice(images)
    image_path = os.path.join(folder_path, random_image)

    logger.info(f"Selected image: {image_path}")

    return open(image_path, "rb")

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# -----------------------------
#  TIMER / REMINDER FUNCTIONS
# -----------------------------
def remove_jobs(context: CallbackContext):
    for prefix in ("deadline", "reminder"):
        for job in context.job_queue.get_jobs_by_name(prefix):
            job.schedule_removal()

def schedule_deadline(context: CallbackContext):
    context.job_queue.run_once(deadline_job, when=TWO_DAYS, name="deadline")

def deadline_job(context: CallbackContext):
    data = load_data()
    if data["last_command_time"] is None:
        return
    if time.time() - data["last_command_time"] >= TWO_DAYS:
        context.bot.send_message(
            chat_id=MAIN_GROUP_ID,
            text=f"⚠️ DA {TWO_DAYS} secondi che non date da mangiare alle galline!",
            message_thread_id=ALLOWED_TOPIC_ID
        )
        data["reminders_active"] = True
        save_data(data)
        context.job_queue.run_repeating(reminder_job, interval=REMINDER_INTERVAL, first=0, name="reminder")

def reminder_job(context: CallbackContext):
    now_h = datetime.now().hour
    if 9 <= now_h < 22:
        context.bot.send_message(
            chat_id=MAIN_GROUP_ID,
            text="‼️ Date da mangiare alle galline!",
            message_thread_id=ALLOWED_TOPIC_ID
        )

# -----------------------------
#   FILE OPERATIONS
# -----------------------------
def save_eggs(eggs: int):
    today_str = datetime.now().strftime("%Y-%m-%d")
    new_file = not os.path.exists(EGGS_FILE)
    with open(EGGS_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["date", "eggs", "chat_id"])
        w.writerow([today_str, eggs, MAIN_GROUP_ID])


def save_sold_eggs(eggs_sold: int, price_per_egg: float):
    today_str = datetime.now().strftime("%Y-%m-%d")
    new_file = not os.path.exists(SOLD_FILE)
    with open(SOLD_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["date", "eggs_sold", "price_per_egg", "chat_id"])
        w.writerow([today_str, eggs_sold, price_per_egg, MAIN_GROUP_ID])


# -----------------------------
#   TOPIC CHECKS
# -----------------------------
def in_feeding_topic(update: Update) -> bool:
    if update.effective_chat.id == MAIN_GROUP_ID and update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        return getattr(update.message, "message_thread_id", None) == ALLOWED_TOPIC_ID
    return False


def in_sales_topic(update: Update) -> bool:
    if update.effective_chat.id == MAIN_GROUP_ID and update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        return getattr(update.message, "message_thread_id", None) == SELL_TOPIC_ID
    return False


# -----------------------------
#   UNIVERSAL COMMAND CHECK
# -----------------------------
def can_execute_command(update: Update) -> bool:
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        return True
    if update.effective_chat.id == MAIN_GROUP_ID:
        return True
    return False


# -----------------------------
#   UNIVERSAL COMMANDS
# -----------------------------
def start_command(update: Update, context: CallbackContext):
    if not can_execute_command(update):
        update.message.reply_text(f"🔥Weeee cazzone. Invia i messaggi sul gruppo principale")
        return
    data = load_data()
    remove_jobs(context)
    data["last_command_time"] = time.time()
    data["reminders_active"] = False
    save_data(data)
    schedule_deadline(context)
    hours = TWO_DAYS // 3600
    update.message.reply_text(f"🔥 Timer impostato per {hours} ore (gruppo principale).")


def sono_andato_oggi_command(update: Update, context: CallbackContext):
    if not can_execute_command(update):
        update.message.reply_text(f"🔥Weeee cazzone. Invia i messaggi sul gruppo principale")
        return
    data = load_data()
    remove_jobs(context)
    data["last_command_time"] = time.time()
    data["reminders_active"] = False
    save_data(data)
    schedule_deadline(context)
    update.message.reply_text("✅ Tutto resettato (gruppo principale).")


def reset_command(update: Update, context: CallbackContext):
    if not can_execute_command(update):
        update.message.reply_text(f"🔥Weeee cazzone. Invia i messaggi sul gruppo principale")
        return
    remove_jobs(context)
    data = load_data()
    data["reminders_active"] = False
    save_data(data)
    update.message.reply_text("🛑 Timer fermato (gruppo principale). Usa /start per ripartire.")


def stat_command(update: Update, context: CallbackContext):
    if not can_execute_command(update):
        update.message.reply_text(f"🔥Weeee cazzone. Invia i messaggi sul gruppo principale")
        return
    if not os.path.isfile(EGGS_FILE):
        update.message.reply_text("⚠️ No egg data found for main group!")
        return
    df = pd.read_csv(EGGS_FILE, parse_dates=["date"])
    if df.empty:
        update.message.reply_text("No data in the eggs file!")
        return
    df = df[df["chat_id"] == MAIN_GROUP_ID]
    if df.empty:
        update.message.reply_text("Nessun uovo registrato per questo gruppo!")
        return
    df = df.sort_values("date").set_index("date")
    df = df.resample("D").sum(numeric_only=True)
    df["7_day_avg"] = df["eggs"].rolling("7D", min_periods=1).mean()
    df = df.reset_index()
    if df.empty:
        update.message.reply_text("No data after resampling.")
        return
    matplotlib.use('Agg')
    plt.figure(figsize=(10, 6))
    plt.plot(df["date"], df["eggs"], marker="o", linestyle="-", color="orange", label="Daily Eggs")
    plt.plot(df["date"], df["7_day_avg"], marker="o", linestyle="--", color="blue", label="7-Day Avg")
    plt.xlabel("Date")
    plt.ylabel("Eggs")
    plt.title("Egg Production (Main Group, 7-Day Rolling)")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.legend()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    update.message.reply_photo(photo=InputFile(buf, filename="eggs_chart.png"), caption="Produzione di uova (7D avg).")


def cash_command(update: Update, context: CallbackContext):
    if not can_execute_command(update):
        update.message.reply_text(f"🔥Weeee cazzone. Invia i messaggi sul gruppo principale")
        return
    if not os.path.isfile(SOLD_FILE):
        update.message.reply_text("Nessun dato di vendita per il gruppo principale!")
        return
    df_all = pd.read_csv(SOLD_FILE, parse_dates=["date"])
    if df_all.empty:
        update.message.reply_text("Nessun dato di vendita!")
        return
    df_all["eggs_sold"] = df_all["eggs_sold"].astype(int)
    df_all["price_per_egg"] = df_all["price_per_egg"].astype(float)
    df_all = df_all[df_all["chat_id"] == MAIN_GROUP_ID]
    if df_all.empty:
        update.message.reply_text("Nessuna vendita per questo gruppo!")
        return
    universal_total = df_all["eggs_sold"].sum()
    # Calculate income per row and universal income
    df_all["income"] = df_all["eggs_sold"] * df_all["price_per_egg"]
    universal_income = df_all["income"].sum()

    cutoff = datetime.now() - timedelta(days=28)
    df_4weeks = df_all[df_all["date"] >= cutoff]
    if df_4weeks.empty:
        msg = (
            "Nessuna vendita negli ultimi 28 giorni (gruppo principale).\n"
            f"**Totale vendite**: {universal_total} uova, incasso: €{universal_income:.2f}"
        )
        update.message.reply_text(msg, parse_mode="Markdown")
        return

    df_4weeks_sorted = df_4weeks.sort_values("date").set_index("date")
    weekly = df_4weeks_sorted.resample("7D").agg({"eggs_sold": "sum", "income": "sum"})
    total_eggs_4weeks = weekly["eggs_sold"].sum()
    total_income_4weeks = weekly["income"].sum()

    txt = (
        f"**Ultime 4 settimane (gruppo principale)**\n\n"
        f"**Uova vendute (4w)**: {total_eggs_4weeks}\n"
        f"**Incasso (4w)**: €{total_income_4weeks:.2f}\n\n"
        "— **Riepilogo settimanale** —\n"
    )
    for period_start, row in weekly.iterrows():
        period_end = period_start + pd.Timedelta(days=6)
        eggs_in_period = row["eggs_sold"]
        income_in_period = row["income"]
        txt += f"- {period_start.date()} to {period_end.date()}: {eggs_in_period} uova => €{income_in_period:.2f}\n"

    # DAILY CHART WITH A SECOND AXIS FOR AVERAGE PRICE PER EGG
    # Resample daily for the last 28 days:
    daily = df_4weeks_sorted.resample("D").agg({"eggs_sold": "sum", "income": "sum"})
    # Compute daily average price (if eggs sold > 0)
    daily["avg_price"] = daily.apply(lambda row: row["income"] / row["eggs_sold"] if row["eggs_sold"] > 0 else None,
                                     axis=1)
    daily["7_day_avg"] = daily["eggs_sold"].rolling("7D", min_periods=1).mean()

    # Plot with two y-axes:
    matplotlib.use('Agg')
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax2 = ax1.twinx()

    ax1.plot(daily.index, daily["eggs_sold"], marker="o", linestyle="-", color="orange", label="Daily Sales")
    ax1.plot(daily.index, daily["7_day_avg"], marker="o", linestyle="--", color="blue", label="7-Day Avg Sales")
    ax2.plot(daily.index, daily["avg_price"], marker="s", linestyle="", color="green", label="Avg Price")

    ax1.set_xlabel("Data")
    ax1.set_ylabel("Uova vendute", color="orange")
    ax2.set_ylabel("Prezzo medio per uovo (€)", color="green")
    ax1.tick_params(axis='y', labelcolor="orange")
    ax2.tick_params(axis='y', labelcolor="green")
    ax1.set_title("Vendite (ultimi 28 giorni) – Gruppo Principale")
    fig.autofmt_xdate()
    ax1.grid(True)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)

    caption = (
            txt + "\n"
                  f"**Totale vendite**: {universal_total} uova => €{universal_income:.2f} totali"
    )
    update.message.reply_photo(
        photo=InputFile(buf, filename="sales_chart.png"),
        caption=caption,
        parse_mode="Markdown"
    )


def presenze_command(update: Update, context: CallbackContext):
    if not can_execute_command(update):
        update.message.reply_text(f"🔥Weeee cazzone. Invia i messaggi sul gruppo principale")
        return
    data = load_data()
    presence_data = data.get("presence_data", {})
    if not presence_data:
        update.message.reply_text("Nessuna presenza registrata finora.")
        return
    sorted_list = sorted(presence_data.items(), key=lambda x: x[1]["count"], reverse=True)
    lines = ["Presenze registrate finora (gruppo principale):\n"]
    for worker_name, info in sorted_list:
        lines.append(f"- {worker_name}: {info['count']} (ultima volta {info['last_date']})")
    update.message.reply_text("\n".join(lines))


# -----------------------------
#   PARSE SALES MESSAGE
# -----------------------------
import re
import logging

logger = logging.getLogger(__name__)

def parse_sale_message(t):
    match = re.search(
        r"(?i)vendut[ae]\s+(\d+)\s*(?:uova)?\s*(?:\+?\s*([\d,\.]+)\s*€?)?",
        t,
        flags=re.DOTALL
    )

    if not match:
        logger.warning(f"Could not parse sale message: {t}")
        return None, None  # No valid input detected

    eggs_sold = int(match.group(1))  # Extract egg count
    price = match.group(2)

    if price:
        price = float(price.replace(",", "."))  # Convert ',' to '.'
    else:
        price = None

    return eggs_sold, price / eggs_sold if price is not None else None

# -----------------------------
#   FEEDING / SALES MESSAGES
# -----------------------------
def handle_feeding_message(update: Update, context: CallbackContext):
    """
    Processes a feeding-topic message.
    Now the function checks the whole text for:
      - Any occurrence of "presenza" or "presenze" → triggers presence registration.
      - Any occurrence of a number followed by "uova" → triggers egg logging.
    This allows messages where these items are in any order.
    After processing, it resets the timer.
    """
    text_low = update.message.text.strip().lower()
    logger.info(f"Feeding topic message: {text_low}")
    data = load_data()
    user_id = update.effective_user.id

    overall_presence_done = False
    overall_eggs_done = False
    reply_lines = []

    # Presence logic: check if "presenza" or "presenze" occurs anywhere.
    if "presenza" in text_low or "presenze" in text_low:
        found_workers = set()
        # Add the sender if recognized by user ID.
        if user_id in USER_ID_DICT:
            found_workers.add(USER_ID_DICT[user_id])
        # Look for any synonyms in the entire text.
        for nickname, real_name in WORKERS_DICT.items():
            if nickname in text_low:
                found_workers.add(real_name)
        if found_workers:
            newly_registered = []
            already_registered = []
            today_str = datetime.now().strftime("%Y-%m-%d")
            for worker in found_workers:
                if worker not in data["presence_data"]:
                    data["presence_data"][worker] = {"count": 0, "last_date": ""}
                info = data["presence_data"][worker]
                if info["last_date"] == today_str:
                    already_registered.append(worker)
                else:
                    info["count"] += 1
                    info["last_date"] = today_str
                    newly_registered.append(worker)
            overall_presence_done = True
            if newly_registered:
                reply_lines.append("✅ Ho registrato la presenza di: " + ", ".join(newly_registered))
            if already_registered:
                reply_lines.append("❌ Già registrati oggi: " + ", ".join(already_registered))

    # Egg logging: look for a pattern like "15 uova"
    match_uova = re.search(r"(\d+)\s*uova\b", text_low)
    if match_uova:
        eggs = int(match_uova.group(1))
        if eggs < 0:
            reply_lines.append("❌ Niente uova negative.")
        else:
            save_eggs(eggs)
            reply_lines.append(f"✅ {eggs} uova registrate boii!")
            overall_eggs_done = True

    # Optionally, check for a timer update ("<x> ore") anywhere in the text.
    match_ore = re.search(r"(\d+)\s*ore\b", text_low)
    if match_ore:
        hours = int(match_ore.group(1))
        global TWO_DAYS
        if hours > 0:
            TWO_DAYS = hours * 3600
            reply_lines.append(f"⏳ Timer aggiornato a {hours} ore.")
        else:
            reply_lines.append("❌ Ore negative o zero non valide.")

    # Send all collected reply lines, if any.
    if reply_lines:
        update.message.reply_text("\n".join(reply_lines))

    # If any presence or egg info was processed, reset the timer.
    if overall_presence_done or overall_eggs_done:
        remove_jobs(context)
        data["last_command_time"] = time.time()
        data["reminders_active"] = False
        save_data(data)
        schedule_deadline(context)


def handle_sales_message(update: Update, context: CallbackContext):
    # Combine lines into a single string
    full_text = update.message.text.replace("\n", " ")
    logger.info(f"Sales topic message: {full_text}")

    eggs_sold, price_per_egg = parse_sale_message(full_text)

    # If no eggs or eggs < 0 => invalid
    if eggs_sold is None or eggs_sold < 0:
        logger.info("No recognized pattern or invalid egg count.")
        update.message.reply_text("❌ Dati di vendita non validi! (Nessun numero o eggs < 0)")
        return

    # If we have eggs but no price => decline
    if price_per_egg is None:
        update.message.reply_text(
            f"❌ Hai detto {eggs_sold} uova ma non hai specificato il totale. "
            "Per favore scrivi sia il numero di uova sia il prezzo totale. (Se le hai date a gratis invia 0)"
        )
        return

    if price_per_egg < 0:
        update.message.reply_text("❌ Dati di vendita non validi! (Prezzo < 0)")
        return

    # Save the sale
    save_sold_eggs(eggs_sold, price_per_egg)
    update.message.reply_text(
        f"✅ {eggs_sold} uova vendute a €{price_per_egg:.2f} l'una! Bravo campione"
    )

    # Additional responses based on price
    if price_per_egg < 0.39:
        if random.random > 0.5:
            update.message.reply_text("❌ Wei bassino sto prezzo! Spero che ti diano il culo almeno")
        else:
            update.message.reply_text(f"❌ {price_per_egg}?? Fai gli sconti alle fighe maiale?")
    elif price_per_egg >= 0.5:
        update.message.reply_text("👍 Dio ca top prezzo fratello allevatore! Come premio beccati sta pic")
        random_photo = get_random_photo(CELEBRATION_FOLDER)
        if random_photo:
            update.message.reply_photo(random_photo)

# -----------------------------
#   MAIN MESSAGE HANDLER
# -----------------------------
def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text
    if user_id == SPECIAL_USER_ID and random.random() < 0.03:
        random_reply = random.choice(SPECIAL_USER_REPLIES)
        update.message.reply_text(random_reply)
    if in_feeding_topic(update):
        handle_feeding_message(update, context)
    elif in_sales_topic(update) or user_id == ADMIN_ID:
        handle_sales_message(update, context)
    else:
        save_user_log(user_id, update.effective_user.username or "N/A", text)
        logger.info("Unsupported topic => user logged.")


def save_user_log(user_id, username, message_text):
    fn = "user_ids_log.csv"
    new_file = not os.path.exists(fn)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(fn, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "user_id", "username", "message"])
        w.writerow([now_str, user_id, username, message_text])


# -----------------------------
#  RESTORE SCHEDULES ON RESTART
# -----------------------------
def restore_schedules(updater: Updater):
    data = load_data()
    now = time.time()
    last_cmd = data["last_command_time"]
    if last_cmd is not None:
        delta = now - last_cmd
        if delta < TWO_DAYS:
            remaining = TWO_DAYS - delta
            updater.job_queue.run_once(deadline_job, when=remaining, name="deadline")
            logger.info(f"Restored deadline in {int(remaining // 3600)} hours.")
        elif data["reminders_active"]:
            updater.job_queue.run_repeating(reminder_job, interval=REMINDER_INTERVAL, first=0, name="reminder")
            logger.info("Restored repeating reminders.")

def photo(updater: Updater,context: CallbackContext):
    random_photo = get_random_photo(CELEBRATION_FOLDER)
    if random_photo:
        updater.message.reply_text("Come premio beccati sta pic")
        updater.message.reply_photo(random_photo)

# -----------------------------
#              MAIN
# -----------------------------
def main():
    TOKEN = "7213666662:AAHrgOCJZJxk7t0eRZ0irLfoKrMnIz3d7sU"
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start_command))
    dp.add_handler(CommandHandler("sono_andato_oggi", sono_andato_oggi_command))
    dp.add_handler(CommandHandler("reset", reset_command))
    dp.add_handler(CommandHandler("stat", stat_command))
    dp.add_handler(CommandHandler("cash", cash_command))
    dp.add_handler(CommandHandler("presenze", presenze_command))
    dp.add_handler(CommandHandler("photo",photo))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    restore_schedules(updater)
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
