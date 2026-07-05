import os
import time
import random
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReactionTypeEmoji
from flask import Flask

# ================= ENVIRONMENT CONFIGURATION =================
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) 

# 100% Working Test Image (Aap isko baad mein apne .jpg link se replace kar sakte ho)
START_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/512px-Telegram_logo.svg.png"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ================= RENDER DUMMY SERVER =================
@app.route('/')
def home():
    return "Telegram Bot is running smoothly on Render! 🚀"

# ================= CHANNELS DATABASE =================
force_channels = {
    "-1003004738287": {
        "name": "Channel 1", 
        "url": "https://t.me/+Gouc7PsDosk4MTRl"
    },
    "-1003783215718": {
        "name": "Channel 2", 
        "url": "https://t.me/+ul-wxo5Tg7k0YWI9"
    }
}

users_db = set()
broadcasting_state = {}

# ================= HELPER FUNCTIONS =================
def check_user_joined(user_id):
    if not force_channels:
        return True
    
    for chat_id in force_channels.keys():
        try:
            status = bot.get_chat_member(chat_id, user_id).status
            if status in ['left', 'kicked']:
                return False
        except Exception as e:
            print(f"Error checking {chat_id}: {e}")
            return False 
    return True

def get_force_join_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    for chat_id, data in force_channels.items():
        markup.add(InlineKeyboardButton(text=f"📢 Join {data['name']}", url=data['url']))
    markup.add(InlineKeyboardButton(text="✅ I have joined", callback_data="check_joined"))
    return markup

# ================= USER COMMANDS =================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    users_db.add(user_id) 
    
    # --- AUTO REACTION FEATURE ---
    try:
        emojis = ['❤️‍🔥', '🎁', '🎉']
        reaction = ReactionTypeEmoji(random.choice(emojis))
        bot.set_message_reaction(message.chat.id, message.id, [reaction], is_big=False)
    except Exception as e:
        print(f"Reaction failed: {e}")
    # -----------------------------
    
    if not check_user_joined(user_id):
        # 1. Typing Indicator & Congrats Message
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(1.5) 
        
        bot.send_message(
            message.chat.id, 
            "Congratulations 🎉 Join Our Official Group To Start Your Task 🥳"
        )
        
        # 2. Photo Upload Indicator & Image with Buttons
        bot.send_chat_action(message.chat.id, 'upload_photo')
        time.sleep(0.5)
        
        bot.send_photo(
            message.chat.id, 
            photo=START_IMAGE,
            caption="⚠️ **Action Required!**\n\nAapko bot use karne ke liye pehle hamare official channels join karne honge.",
            reply_markup=get_force_join_keyboard(),
            parse_mode="Markdown"
        )
    else:
        bot.send_photo(
            message.chat.id,
            photo=START_IMAGE,
            caption=f"Hello [{message.from_user.first_name}](tg://user?id={user_id})! 🎉\n\nWelcome to the bot. Verification complete hai, ab aap bot ke features use kar sakte hain.",
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data == "check_joined")
def verify_join(call):
    user_id = call.from_user.id
    if check_user_joined(user_id):
        bot.answer_callback_query(call.id, "✅ Verified! Welcome to the bot.")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_photo(
            call.message.chat.id,
            photo=START_IMAGE,
            caption=f"Verification complete! 🎉\nWelcome [{call.from_user.first_name}](tg://user?id={user_id}). Aap bot use kar sakte hain.",
            parse_mode="Markdown"
        )
    else:
        bot.answer_callback_query(call.id, "❌ Aapne abhi tak sabhi channels join nahi kiye hain!", show_alert=True)

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
        text = f"📊 **Bot Statistics**\n\n👥 Total Users: {len(users_db)}\n📢 Active Force Channels: {len(force_channels)}"
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        
    elif action == "add":
        bot.answer_callback_query(call.id)
        text = (
            "Naya channel add karne ke liye is format mein message bhejein:\n\n"
            "`Chat_ID | Channel Name | Join Link`\n\n"
            "Example: `-100123456789 | VIP Channel | https://t.me/+abcde`\n\n"
            "(Send /cancel to abort)"
        )
        msg = bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_channel)
        
    elif action == "remove":
        bot.answer_callback_query(call.id)
        if not force_channels:
            bot.send_message(call.message.chat.id, "No channels to remove.")
            return
        
        markup = InlineKeyboardMarkup(row_width=1)
        for chat_id, data in force_channels.items():
            markup.add(InlineKeyboardButton(f"❌ Remove {data['name']}", callback_data=f"del_{chat_id}"))
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
    chat_id = call.data.split("del_")[1]
    if chat_id in force_channels:
        name = force_channels[chat_id]['name']
        del force_channels[chat_id]
        bot.answer_callback_query(call.id, f"Removed {name}")
        bot.edit_message_text(f"✅ Removed **{name}** from force join.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

def process_add_channel(message):
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "Action cancelled.")
        return
    
    try:
        parts = message.text.split('|')
        if len(parts) != 3:
            bot.send_message(message.chat.id, "❌ Galat format! Please `ID | Name | Link` format me bhejein.")
            return
            
        chat_id = parts[0].strip()
        name = parts[1].strip()
        url = parts[2].strip()
        
        force_channels[chat_id] = {"name": name, "url": url}
        bot.send_message(message.chat.id, f"✅ Successfully added **{name}** to force join.\n\n⚠️ **Make sure I am an admin in that channel!**", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

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
    bot.send_message(message.chat.id, f"✅ **Broadcast Complete!**\n\n👥 Successful: {success}\n❌ Failed (blocked bot): {failed}", parse_mode="Markdown")

# ================= RUNNER =================
def run_bot():
    try:
        bot.remove_webhook()
    except Exception:
        pass
    print("Telegram Bot is polling...")
    bot.infinity_polling(skip_pending=True, timeout=10, long_polling_timeout=5)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
