import os
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask

# ================= ENVIRONMENT CONFIGURATION =================
# We fetch these from Render Environment Variables safely
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# Convert ADMIN_ID to integer (defaulting to 0 if not set)
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) 
START_IMAGE = "https://files.catbox.moe/1suz8b.jpg"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Dummy web server to keep Render Web Service happy
@app.route('/')
def home():
    return "Telegram Bot is running smoothly on Render!"

def run_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# In-memory storage (For production, use SQLite or MongoDB)
force_channels = {}  
users_db = set()
broadcasting_state = {} 

# ================= HELPER FUNCTIONS =================
def check_user_joined(user_id):
    if not force_channels:
        return True
    
    for channel_username in force_channels.keys():
        try:
            status = bot.get_chat_member(channel_username, user_id).status
            if status in ['left', 'kicked']:
                return False
        except Exception:
            pass 
    return True

def get_force_join_keyboard():
    markup = InlineKeyboardMarkup()
    for username, name in force_channels.items():
        markup.add(InlineKeyboardButton(text=f"Join {name}", url=f"https://t.me/{username[1:]}"))
    markup.add(InlineKeyboardButton(text="✅ I have joined", callback_data="check_joined"))
    return markup

# ================= USER COMMANDS =================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    users_db.add(user_id) 
    
    if not check_user_joined(user_id):
        bot.send_photo(
            message.chat.id, 
            photo=START_IMAGE,
            caption="⚠️ **Action Required!**\n\nYou must join all our official channels to use this bot.",
            reply_markup=get_force_join_keyboard(),
            parse_mode="Markdown"
        )
    else:
        bot.send_photo(
            message.chat.id,
            photo=START_IMAGE,
            caption=f"Hello {message.from_user.first_name}! Welcome to the bot. You have access to all features now.",
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data == "check_joined")
def verify_join(call):
    user_id = call.from_user.id
    if check_user_joined(user_id):
        bot.answer_callback_query(call.id, "✅ Verified! Welcome to the bot.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Verification complete. Send /start to begin.")
    else:
        bot.answer_callback_query(call.id, "❌ You haven't joined all channels yet!", show_alert=True)

# ================= ADMIN PANEL =================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ Add Channel", callback_data="admin_add"),
        InlineKeyboardButton("➖ Remove Channel", callback_data="admin_remove"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("📊 Stats", callback_data="admin_stats")
    )
    
    bot.send_message(message.chat.id, "🛡️ **Admin Control Panel**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        return

    action = call.data.split("_")[1]

    if action == "stats":
        bot.answer_callback_query(call.id)
        text = f"📊 **Bot Statistics**\n\nTotal Users: {len(users_db)}\nActive Force Channels: {len(force_channels)}"
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        
    elif action == "add":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Send the channel username (e.g., @mychannel):")
        bot.register_next_step_handler(msg, process_add_channel)
        
    elif action == "remove":
        bot.answer_callback_query(call.id)
        if not force_channels:
            bot.send_message(call.message.chat.id, "No channels to remove.")
            return
        
        markup = InlineKeyboardMarkup()
        for username in force_channels.keys():
            markup.add(InlineKeyboardButton(f"Remove {username}", callback_data=f"del_{username}"))
        bot.send_message(call.message.chat.id, "Select a channel to remove:", reply_markup=markup)
        
    elif action == "broadcast":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Send the message, photo, video, or sticker you want to broadcast. (Send /cancel to abort)")
        broadcasting_state[ADMIN_ID] = True
        bot.register_next_step_handler(msg, process_broadcast)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def process_remove_channel(call):
    if call.from_user.id != ADMIN_ID:
        return
    username = call.data.split("del_")[1]
    if username in force_channels:
        del force_channels[username]
        bot.answer_callback_query(call.id, f"Removed {username}")
        bot.edit_message_text(f"✅ Removed {username} from force join.", call.message.chat.id, call.message.message_id)

def process_add_channel(message):
    if message.text == '/cancel':
        return
    username = message.text.strip()
    if not username.startswith('@'):
        bot.send_message(message.chat.id, "Invalid format. Must start with @")
        return
    
    force_channels[username] = username 
    bot.send_message(message.chat.id, f"✅ Successfully added {username} to force join. **Make sure I am an admin in that channel!**", parse_mode="Markdown")

def process_broadcast(message):
    if message.text == '/cancel':
        broadcasting_state.pop(ADMIN_ID, None)
        bot.send_message(message.chat.id, "Broadcast cancelled.")
        return
    
    if not broadcasting_state.get(ADMIN_ID):
        return

    bot.send_message(message.chat.id, "🚀 Broadcasting started...")
    success = 0
    failed = 0
    
    for user_id in list(users_db):
        try:
            bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            success += 1
        except Exception:
            failed += 1
            
    broadcasting_state.pop(ADMIN_ID, None)
    bot.send_message(message.chat.id, f"✅ **Broadcast Complete!**\n\nSuccessful: {success}\nFailed (blocked bot): {failed}", parse_mode="Markdown")

# ================= RUNNER =================
if __name__ == "__main__":
    # Start the Flask web server in a separate thread for Render
    threading.Thread(target=run_web, daemon=True).start()
    
    # Start the Telegram bot polling
    print("Bot is starting...")
    bot.infinity_polling()
