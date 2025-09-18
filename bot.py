from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google.oauth2.service_account import Credentials
from datetime import datetime
import telegram
import gspread
import os
import json

# ------------------------
# CONFIG
# ------------------------
BOT_TOKEN = "7068376411:AAGzavPyfycKGwPJYYAmAtPfDOPT9kr7T6k"
ADMIN_IDS = [1429922548]

GOOGLE_SHEET_NAME = "TelegramUserData"
BLOCKED_SHEET = "Blocked"
CONTACTS_SHEET = "Contacts"
BROADCAST_SHEET = "BroadcastLogs"
USER_BLOCKED_BOT_SHEET = "UserBlockedBot"

# ------------------------
# GOOGLE SHEET SETUP (From Environment)
# ------------------------
creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = Credentials.from_service_account_info(
    creds_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"]
)
gc = gspread.authorize(creds)
sheet = gc.open(GOOGLE_SHEET_NAME)

blocked_sheet = sheet.worksheet(BLOCKED_SHEET)
contacts_sheet = sheet.worksheet(CONTACTS_SHEET)

# Create broadcast logs sheet if not exists
try:
    broadcast_sheet = sheet.worksheet(BROADCAST_SHEET)
except:
    broadcast_sheet = sheet.add_worksheet(title=BROADCAST_SHEET, rows="1000", cols="4")
    broadcast_sheet.append_row(["Date", "Type", "Message", "Status"])

# Create UserBlockedBot sheet if not exists
try:
    user_blocked_bot_sheet = sheet.worksheet(USER_BLOCKED_BOT_SHEET)
except:
    user_blocked_bot_sheet = sheet.add_worksheet(title=USER_BLOCKED_BOT_SHEET, rows="1000", cols="1")
    user_blocked_bot_sheet.append_row(["User ID"])

# ------------------------
# MESSAGE MAP
# ------------------------
message_map = {}

# ------------------------
# SAVE USER TO GOOGLE SHEETS
# ------------------------
def save_user(user_id, name, username):
    users = contacts_sheet.get_all_values()
    user_ids = [row[0] for row in users[1:]]
    if str(user_id) not in user_ids:
        contacts_sheet.append_row([str(user_id), name, username or ""])

# ------------------------
# LOG USER WHO BLOCKED BOT
# ------------------------
def log_user_blocked(user_id):
    blocked_users = user_blocked_bot_sheet.col_values(1)
    if str(user_id) not in blocked_users:
        user_blocked_bot_sheet.append_row([str(user_id)])

# ------------------------
# CHECK IF BLOCKED BY ADMIN
# ------------------------
def is_blocked(user_id):
    blocked_ids = blocked_sheet.col_values(1)
    return str(user_id) in blocked_ids

# ------------------------
# START COMMAND
# ------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    username = update.effective_user.username or "No Username"

    save_user(user_id, user_name, username)
    await update.message.reply_text("မင်္ဂလာပါ👋 EUROPA369 မှ ကြိုဆိုပါတယ်နော်")

    for admin_id in ADMIN_IDS:
        sent_msg = await context.bot.send_message(
            chat_id=admin_id,
            text=f"🆕 User Started/Restarted Bot:\nName: {user_name}\nUsername: @{username}\nID: {user_id}"
        )
        message_map[sent_msg.message_id] = {
            "user_id": user_id,
            "user_name": user_name
        }

# ------------------------
# BLOCK USER BY ADMIN
# ------------------------
async def block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /block <user_id>")
        return

    user_id = context.args[0]
    if not is_blocked(user_id):
        blocked_sheet.append_row([str(user_id)])
        await update.message.reply_text(f"✅ User {user_id} has been blocked.")
    else:
        await update.message.reply_text(f"⚠️ User {user_id} is already blocked.")

# ------------------------
# UNBLOCK USER BY ADMIN
# ------------------------
async def unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /unblock <user_id>")
        return

    user_id = context.args[0]
    blocked_ids = blocked_sheet.col_values(1)
    if user_id in blocked_ids:
        index = blocked_ids.index(user_id) + 1
        blocked_sheet.delete_rows(index)
        await update.message.reply_text(f"✅ User {user_id} has been unblocked.")
    else:
        await update.message.reply_text(f"⚠️ User {user_id} is not blocked.")

# ------------------------
# VIEW BLOCKED USERS
# ------------------------
async def view_blocked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    blocked = blocked_sheet.col_values(1)
    if blocked:
        await update.message.reply_text("🔒 Blocked users:\n" + "\n".join(blocked))
    else:
        await update.message.reply_text("✅ No blocked users.")

# ------------------------
# FORWARD USER MESSAGES TO ADMINS
# ------------------------
async def forward_to_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    username = update.effective_user.username

    if user_id in ADMIN_IDS or is_blocked(user_id):
        return

    save_user(user_id, user_name, username)

    for admin_id in ADMIN_IDS:
        forwarded = await update.message.forward(chat_id=admin_id)
        message_map[forwarded.message_id] = {
            "user_id": user_id,
            "user_name": user_name
        }

# ------------------------
# ADMIN REPLIES TO USERS
# ------------------------
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return
    reply_to_msg_id = update.message.reply_to_message.message_id
    if reply_to_msg_id not in message_map:
        return

    user_id = message_map[reply_to_msg_id]["user_id"]
    user_name = message_map[reply_to_msg_id]["user_name"]

    if is_blocked(user_id):
        await update.message.reply_text(f"⛔ User {user_name} ({user_id}) is blocked. Message not sent.")
        return

    try:
        if update.message.text:
            await context.bot.send_message(chat_id=user_id, text=update.message.text)
    except telegram.error.Forbidden:
        log_user_blocked(user_id)

    for other_admin in ADMIN_IDS:
        if other_admin != update.effective_user.id:
            await context.bot.send_message(
                chat_id=other_admin,
                text=f"[Admin {update.effective_user.first_name} replied to {user_name}]\n{update.message.text}"
            )

# ------------------------
# BROADCAST TO USERS
# ------------------------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    users = contacts_sheet.get_all_values()[1:]
    blocked_ids = set(blocked_sheet.col_values(1))

    target_message = update.message.reply_to_message if update.message.reply_to_message else update.message

    message_type = "Text"
    message_content = ""
    photo_file = video_file = document_file = None

    if target_message.photo:
        message_type = "Image"
        photo_file = target_message.photo[-1].file_id
        message_content = target_message.caption or ""
    elif target_message.video:
        message_type = "Video"
        video_file = target_message.video.file_id
        message_content = target_message.caption or ""
    elif target_message.document:
        message_type = "Document"
        document_file = target_message.document.file_id
        message_content = target_message.caption or ""
    else:
        args_text = " ".join(context.args)
        message_content = args_text if args_text else target_message.text or "[Empty Text]"

    success_count, failed_count = 0, 0
    total_users = len(users)

    for user in users:
        user_id = user[0]
        if user_id in blocked_ids:
            failed_count += 1
            continue

        try:
            if message_type == "Image" and photo_file:
                await context.bot.send_photo(chat_id=int(user_id), photo=photo_file, caption=message_content)
            elif message_type == "Video" and video_file:
                await context.bot.send_video(chat_id=int(user_id), video=video_file, caption=message_content)
            elif message_type == "Document" and document_file:
                await context.bot.send_document(chat_id=int(user_id), document=document_file, caption=message_content)
            else:
                await context.bot.send_message(chat_id=int(user_id), text=message_content)
            success_count += 1
        except telegram.error.Forbidden:
            log_user_blocked(user_id)
            failed_count += 1
        except:
            failed_count += 1

    broadcast_sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        message_type,
        message_content[:200],
        f"Success: {success_count}, Failed: {failed_count}, Total: {total_users}"
    ])

    await update.message.reply_text(
        f"📢 Broadcast finished!\n"
        f"✅ Success: {success_count}\n"
        f"❌ Failed: {failed_count}\n"
        f"👥 Total Users: {total_users}"
    )

# ------------------------
# MAIN FUNCTION
# ------------------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("block", block))
    app.add_handler(CommandHandler("unblock", unblock))
    app.add_handler(CommandHandler("blocked", view_blocked))
    app.add_handler(CommandHandler("broadcast", broadcast))

    app.add_handler(MessageHandler(filters.ALL & ~filters.User(user_id=ADMIN_IDS), forward_to_admins))
    app.add_handler(MessageHandler(filters.ALL & filters.User(user_id=ADMIN_IDS), handle_admin_reply))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
