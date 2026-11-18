import telebot
from telebot import types
import subprocess
import datetime
import os
import re
import socket
import random
import string
import time
import threading
import schedule
import json

from config import TOKEN, ADMIN_ID, CONFIG_PATH

bot = telebot.TeleBot(TOKEN)
LIMIT_FILE = "/etc/openvpn/server/user_limits.txt"
STATUS_LOG = "/etc/openvpn/server/openvpn-status.log"
TRAFFIC_FILE = "/etc/openvpn/server/traffic.json"

user_states = {}

def is_admin(user_id):
    return user_id == ADMIN_ID

# ------------------- توابع مدیریت ترافیک -------------------

def format_size(bytes_val):
    """تبدیل بایت به مگابایت یا گیگابایت خوانا"""
    if bytes_val < 1024 * 1024:
        return f"{round(bytes_val / 1024, 1)} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{round(bytes_val / (1024 * 1024), 2)} MB"
    else:
        return f"{round(bytes_val / (1024 * 1024 * 1024), 2)} GB"

def get_stored_traffic():
    """خواندن حجم مصرفی ذخیره شده کاربران"""
    if not os.path.exists(TRAFFIC_FILE):
        return {}
    try:
        with open(TRAFFIC_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def reset_user_traffic(username):
    data = get_stored_traffic()
    if username in data:
        data[username] = {'rx': 0, 'tx': 0}
        with open(TRAFFIC_FILE, 'w') as f:
            json.dump(data, f)

def get_online_users():
    """استخراج کاربران آنلاین و میزان مصرف نشست فعلی"""
    online = []
    if not os.path.exists(STATUS_LOG):
        return online
    with open(STATUS_LOG, 'r') as f:
        lines = f.readlines()
    
    in_client_list = False
    for line in lines:
        if line.startswith("Common Name,Real Address"):
            in_client_list = True
            continue
        if line.startswith("ROUTING TABLE"):
            break
        if in_client_list and ',' in line:
            parts = line.strip().split(',')
            if len(parts) >= 4 and parts[0] != "UNDEF":
                uname = parts[0]
                real_ip = parts[1].split(':')[0]
                rx_bytes = int(parts[2])
                tx_bytes = int(parts[3])
                online.append({
                    'user': uname,
                    'ip': real_ip,
                    'rx_bytes': rx_bytes,
                    'tx_bytes': tx_bytes
                })
    return online

def get_user_total_usage(username):
    """محاسبه مجموع مصرف کل (ذخیره شده + آنلاین فعلی)"""
    stored = get_stored_traffic().get(username, {'rx': 0, 'tx': 0})
    total_rx = stored.get('rx', 0)
    total_tx = stored.get('tx', 0)
    
    for item in get_online_users():
        if item['user'] == username:
            total_rx += item['rx_bytes']
            total_tx += item['tx_bytes']
            
    return total_rx, total_tx

# ------------------- توابع کمکی سیستم -------------------

def kill_openvpn_session(username):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect(('127.0.0.1', 7505))
            s.recv(1024)
            s.sendall(f"kill {username}\n".encode())
            time.sleep(0.2)
            s.sendall(b"quit\n")
        return True
    except Exception:
        return False

def get_all_vpn_users():
    users_data = []
    with open('/etc/passwd', 'r') as f:
        users = [line.split(':')[0] for line in f if '/usr/sbin/nologin' in line]
    
    valid_users = [u for u in users if u not in ['nobody', 'messagebus', 'sshd', '_apt'] and not u.startswith('systemd-')]
    
    for u in valid_users:
        try:
            chage_output = subprocess.check_output(['chage', '-l', u]).decode()
            exp_date = "نامشخص"
            for line in chage_output.split('\n'):
                if "Account expires" in line:
                    exp_date = line.split(':')[1].strip()
                    break
            users_data.append({'username': u, 'expiry': exp_date})
        except Exception:
            pass
    return users_data

def get_user_limit(username):
    if os.path.exists(LIMIT_FILE):
        with open(LIMIT_FILE, 'r') as f:
            for line in f:
                if line.startswith(f"{username}:"):
                    return line.strip().split(':')[1]
    return "2"

def set_user_limit(username, limit):
    lines = []
    if os.path.exists(LIMIT_FILE):
        with open(LIMIT_FILE, 'r') as f:
            lines = [l for l in f if not l.startswith(f"{username}:")]
    lines.append(f"{username}:{limit}\n")
    with open(LIMIT_FILE, 'w') as f:
        f.writelines(lines)

def generate_password(length=8):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# ------------------- کیبوردهای شیشه‌ای -------------------

def main_menu_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ ساخت کاربر جدید", callback_data="menu_add"),
        types.InlineKeyboardButton("👥 مدیریت کاربران", callback_data="menu_users"),
        types.InlineKeyboardButton("🟢 کاربران آنلاین", callback_data="menu_online"),
        types.InlineKeyboardButton("📊 آمار مصرف ترافیک", callback_data="menu_traffic"),
        types.InlineKeyboardButton("📁 دریافت فایل کانفیگ", callback_data="menu_config"),
        types.InlineKeyboardButton("💾 بکاپ‌گیری کامل", callback_data="menu_backup"),
        types.InlineKeyboardButton("🖥 وضعیت سرور", callback_data="menu_status")
    )
    return markup

def back_to_main_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu"))
    return markup

# ------------------- هندلرهای اصلی -------------------

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    if not is_admin(message.from_user.id):
        return
    user_states.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        "🛡 **پنل مدیریت پیشرفته OpenVPN**\n\nیکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if not is_admin(call.from_user.id):
        return
    
    uid = call.from_user.id
    data = call.data

    if data == "main_menu":
        user_states.pop(uid, None)
        bot.edit_message_text(
            "🛡 **پنل مدیریت پیشرفته OpenVPN**\n\nیکی از گزینه‌های زیر را انتخاب کنید:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown"
        )

    elif data == "menu_add":
        user_states[uid] = {'step': 'ask_username'}
        bot.edit_message_text(
            "👤 **ساخت کاربر جدید**\n\nلطفاً **نام کاربری (Username)** را وارد کنید (فقط حروف انگلیسی و اعداد):",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_to_main_keyboard(),
            parse_mode="Markdown"
        )

    elif data == "menu_users":
        users = get_all_vpn_users()
        if not users:
            bot.edit_message_text(
                "⚠️ هیچ کاربری در سیستم ثبت نشده است.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=back_to_main_keyboard()
            )
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        for u in users:
            rx, tx = get_user_total_usage(u['username'])
            total_str = format_size(rx + tx)
            markup.add(types.InlineKeyboardButton(f"👤 {u['username']} ({total_str})", callback_data=f"user_detail:{u['username']}"))
        markup.add(types.InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu"))
        
        bot.edit_message_text(
            f"👥 **لیست کاربران ({len(users)} نفر)**\nبرای مدیریت هر کاربر روی نام آن کلیک کنید:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif data.startswith("user_detail:"):
        uname = data.split(":")[1]
        users = get_all_vpn_users()
        user_info = next((item for item in users if item["username"] == uname), None)
        if not user_info:
            bot.answer_callback_query(call.id, "کاربر یافت نشد!")
            return
        
        limit = get_user_limit(uname)
        online_list = get_online_users()
        active_conns = sum(1 for x in online_list if x['user'] == uname)
        rx, tx = get_user_total_usage(uname)
        
        text = (
            f"👤 **مدیریت کاربر:** `{uname}`\n"
            f"📅 **تاریخ انقضا:** `{user_info['expiry']}`\n"
            f"📱 **محدودیت اتصال:** `{active_conns} / {limit}` دستگاه\n"
            f"📊 **مجموع مصرف کل:** `{format_size(rx + tx)}`\n"
            f"   └ ⬇️ دریافت: `{format_size(rx)}` | ⬆️ ارسال: `{format_size(tx)}`"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ تمدید 30 روز", callback_data=f"renew:{uname}:30"),
            types.InlineKeyboardButton("➕ تمدید 60 روز", callback_data=f"renew:{uname}:60"),
            types.InlineKeyboardButton("🔑 تغییر رمز عبور", callback_data=f"chpass:{uname}"),
            types.InlineKeyboardButton("📱 تغییر محدودیت", callback_data=f"chlimit:{uname}"),
            types.InlineKeyboardButton("🔄 ریست حجم مصرفی", callback_data=f"reset_tr:{uname}"),
            types.InlineKeyboardButton("🔌 قطع اتصال (Kick)", callback_data=f"kick:{uname}"),
            types.InlineKeyboardButton("🗑 حذف کامل کاربر", callback_data=f"del_confirm:{uname}")
        )
        markup.add(types.InlineKeyboardButton("🔙 بازگشت به لیست کاربران", callback_data="menu_users"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("reset_tr:"):
        uname = data.split(":")[1]
        reset_user_traffic(uname)
        bot.answer_callback_query(call.id, f"✅ حجم مصرفی {uname} صفر شد.")
        call.data = f"user_detail:{uname}"
        handle_callbacks(call)

    elif data == "menu_traffic":
        users = get_all_vpn_users()
        if not users:
            bot.edit_message_text("⚠️ هیچ کاربری وجود ندارد.", call.message.chat.id, call.message.message_id, reply_markup=back_to_main_keyboard())
            return
        
        usage_list = []
        grand_total = 0
        for u in users:
            rx, tx = get_user_total_usage(u['username'])
            tot = rx + tx
            grand_total += tot
            usage_list.append((u['username'], rx, tx, tot))
        
        # مرتب‌سازی بر اساس بیشترین مصرف
        usage_list.sort(key=lambda x: x[3], reverse=True)
        
        text = f"📊 **گزارش مصرف ترافیک کاربران**\n🌐 **مجموع کل مصرف سرور:** `{format_size(grand_total)}`\n〰️〰️〰️〰️〰️〰️〰️\n\n"
        for idx, (uname, rx, tx, tot) in enumerate(usage_list, 1):
            text += f"{idx}. 👤 `{uname}` ➔ **{format_size(tot)}**\n   (⬇️ {format_size(rx)} | ⬆️ {format_size(tx)})\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 بروزرسانی آمار", callback_data="menu_traffic"))
        markup.add(types.InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("renew:"):
        _, uname, days = data.split(":")
        days = int(days)
        new_expiry = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime('%Y-%m-%d')
        subprocess.run(['chage', '-E', new_expiry, uname])
        bot.answer_callback_query(call.id, f"✅ اشتراک {uname} به مدت {days} روز تمدید شد!")
        call.data = f"user_detail:{uname}"
        handle_callbacks(call)

    elif data.startswith("chpass:"):
        uname = data.split(":")[1]
        user_states[uid] = {'step': 'ask_new_pass', 'target_user': uname}
        bot.edit_message_text(
            f"🔑 رمز عبور جدید برای کاربر `{uname}` را وارد کنید:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=back_to_main_keyboard(),
            parse_mode="Markdown"
        )

    elif data.startswith("chlimit:"):
        uname = data.split(":")[1]
        markup = types.InlineKeyboardMarkup(row_width=4)
        markup.add(
            types.InlineKeyboardButton("1 کاربر", callback_data=f"setlimit:{uname}:1"),
            types.InlineKeyboardButton("2 کاربر", callback_data=f"setlimit:{uname}:2"),
            types.InlineKeyboardButton("3 کاربر", callback_data=f"setlimit:{uname}:3"),
            types.InlineKeyboardButton("5 کاربر", callback_data=f"setlimit:{uname}:5")
        )
        markup.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data=f"user_detail:{uname}"))
        bot.edit_message_text(
            f"📱 حداکثر تعداد دستگاه همزمان برای `{uname}` را انتخاب کنید:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif data.startswith("setlimit:"):
        _, uname, limit = data.split(":")
        set_user_limit(uname, limit)
        bot.answer_callback_query(call.id, f"✅ محدودیت کاربر {uname} روی {limit} دستگاه تنظیم شد.")
        call.data = f"user_detail:{uname}"
        handle_callbacks(call)

    elif data.startswith("kick:"):
        uname = data.split(":")[1]
        if kill_openvpn_session(uname):
            bot.answer_callback_query(call.id, f"🔌 اتصال {uname} با موفقیت قطع شد.")
        else:
            bot.answer_callback_query(call.id, "⚠️ کاربر آنلاین نبود یا خطایی رخ داد.")

    elif data.startswith("del_confirm:"):
        uname = data.split(":")[1]
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"del_exec:{uname}"),
            types.InlineKeyboardButton("❌ انصراف", callback_data=f"user_detail:{uname}")
        )
        bot.edit_message_text(
            f"⚠️ آیا از حذف دائمی کاربر `{uname}` مطمئن هستید؟",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif data.startswith("del_exec:"):
        uname = data.split(":")[1]
        kill_openvpn_session(uname)
        subprocess.run(['userdel', '-r', uname], stderr=subprocess.DEVNULL)
        data_tr = get_stored_traffic()
        if uname in data_tr:
            del data_tr[uname]
            with open(TRAFFIC_FILE, 'w') as f:
                json.dump(data_tr, f)
        bot.answer_callback_query(call.id, f"🗑 کاربر {uname} حذف شد.")
        call.data = "menu_users"
        handle_callbacks(call)

    elif data == "menu_online":
        online_users = get_online_users()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 بروزرسانی لیست", callback_data="menu_online"))
        markup.add(types.InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu"))
        
        if not online_users:
            msg_text = "🟢 در حال حاضر هیچ کاربری آنلاین نیست."
        else:
            msg_text = f"🟢 **کاربران آنلاین ({len(online_users)} اتصال فعال):**\n\n"
            for item in online_users:
                msg_text += f"👤 `{item['user']}` | 🌐 `{item['ip']}`\n⬇️ {format_size(item['rx_bytes'])} | ⬆️ {format_size(item['tx_bytes'])}\n〰️〰️〰️〰️〰️\n"
                
        bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "menu_config":
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'rb') as f:
                bot.send_document(call.message.chat.id, f, caption="🌐 **فایل اتصال عمومی (Universal OVPN)**\nاین فایل برای تمام کاربران یکسان است.", parse_mode="Markdown")
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, "❌ فایل کانفیگ یافت نشد!")

    elif data == "menu_backup":
        bot.answer_callback_query(call.id, "در حال ساخت فایل پشتیبان...")
        backup_name = f"/tmp/openvpn_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.zip"
        subprocess.run(['zip', '-r', backup_name, '/etc/openvpn', '/etc/passwd', '/etc/shadow'], stdout=subprocess.DEVNULL)
        if os.path.exists(backup_name):
            with open(backup_name, 'rb') as f:
                bot.send_document(call.message.chat.id, f, caption="💾 **فایل پشتیبان کامل سرور و کاربران**")
            os.remove(backup_name)

    elif data == "menu_status":
        uptime = subprocess.check_output(['uptime', '-p']).decode().strip()
        service_status = subprocess.run(['systemctl', 'is-active', 'openvpn-server@server'], stdout=subprocess.PIPE).stdout.decode().strip()
        total_users = len(get_all_vpn_users())
        online_count = len(get_online_users())
        
        status_text = (
            "🖥 **وضعیت لحظه‌ای سرور OpenVPN**\n\n"
            f"⚙️ وضعیت سرویس: `{'فعال ✅' if service_status == 'active' else 'غیرفعال ❌'}`\n"
            f"⏱ آپتایم سرور: `{uptime}`\n"
            f"👥 کل کاربران ثبت‌شده: `{total_users}`\n"
            f"🟢 اتصالات آنلاین فعلی: `{online_count}`"
        )
        bot.edit_message_text(status_text, call.message.chat.id, call.message.message_id, reply_markup=back_to_main_keyboard(), parse_mode="Markdown")

# ------------------- مدیریت پیام‌های متنی -------------------

@bot.message_handler(func=lambda message: True)
def handle_text_inputs(message):
    if not is_admin(message.from_user.id):
        return
    
    uid = message.from_user.id
    if uid not in user_states:
        return
    
    state = user_states[uid]
    text = message.text.strip()

    if state['step'] == 'ask_username':
        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', text):
            bot.reply_to(message, "❌ نام کاربری نامعتبر است! فقط از حروف انگلیسی، اعداد و `_` (حداقل ۳ کاراکتر) استفاده کنید:")
            return
        
        check_user = subprocess.run(['id', text], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check_user.returncode == 0:
            bot.reply_to(message, f"⚠️ کاربر `{text}` از قبل وجود دارد! نام دیگری وارد کنید:", parse_mode="Markdown")
            return
        
        state['username'] = text
        state['step'] = 'ask_password'
        
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add("🎲 تولید رمز خودکار")
        bot.send_message(
            message.chat.id,
            f"🔑 رمز عبور برای `{text}` را وارد کنید (یا دکمه تولید خودکار را بزنید):",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif state['step'] == 'ask_password':
        pwd = generate_password() if text == "🎲 تولید رمز خودکار" else text
        state['password'] = pwd
        state['step'] = 'ask_days'
        
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add("30", "60", "90", "365")
        bot.send_message(
            message.chat.id,
            "📅 مدت اعتبار اکانت را به **روز** وارد کنید (مثلاً 30):",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    elif state['step'] == 'ask_days':
        if not text.isdigit() or int(text) <= 0:
            bot.reply_to(message, "❌ لطفاً یک عدد معتبر (مثلاً 30) وارد کنید:")
            return
        
        days = int(text)
        uname = state['username']
        pwd = state['password']
        
        subprocess.run(['useradd', '-M', '-s', '/usr/sbin/nologin', uname])
        p = subprocess.Popen(['chpasswd'], stdin=subprocess.PIPE)
        p.communicate(input=f"{uname}:{pwd}".encode())
        
        expiry_date = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime('%Y-%m-%d')
        subprocess.run(['chage', '-E', expiry_date, uname])
        set_user_limit(uname, 2)
        
        user_states.pop(uid, None)
        
        customer_msg = (
            "✅ **اشتراک جدید با موفقیت ساخته شد!**\n"
            "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
            f"👤 **نام کاربری:** `{uname}`\n"
            f"🔑 **رمز عبور:** `{pwd}`\n"
            f"📅 **تاریخ انقضا:** `{expiry_date}` ({days} روزه)\n"
            f"📱 **تعداد کاربر همزمان:** 2 دستگاه\n"
            "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
            "📌 *فایل زیر را دانلود کرده و در برنامه OpenVPN Connect وارد کنید.*"
        )
        
        bot.send_message(message.chat.id, customer_msg, reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'rb') as f:
                bot.send_document(message.chat.id, f, reply_markup=main_menu_keyboard())

    elif state['step'] == 'ask_new_pass':
        uname = state['target_user']
        p = subprocess.Popen(['chpasswd'], stdin=subprocess.PIPE)
        p.communicate(input=f"{uname}:{text}".encode())
        kill_openvpn_session(uname)
        user_states.pop(uid, None)
        bot.send_message(
            message.chat.id,
            f"✅ رمز عبور کاربر `{uname}` به `{text}` تغییر یافت و اتصال قبلی قطع شد.",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown"
        )

# ------------------- کرون‌جاب بررسی انقضا -------------------

def check_expired_users():
    today = datetime.datetime.now().date()
    users = get_all_vpn_users()
    for u in users:
        exp_str = u['expiry']
        if exp_str in ["never", "نامشخص"]:
            continue
        try:
            exp_date = datetime.datetime.strptime(exp_str, "%b %d, %Y").date()
            days_left = (exp_date - today).days
            
            if days_left < 0:
                kill_openvpn_session(u['username'])
                subprocess.run(['userdel', '-r', u['username']], stderr=subprocess.DEVNULL)
                bot.send_message(ADMIN_ID, f"🗑 اشتراک کاربر `{u['username']}` به پایان رسید و به صورت خودکار حذف شد.", parse_mode="Markdown")
            elif days_left == 2:
                bot.send_message(ADMIN_ID, f"⚠️ هشدار انقضا: تنها **۲ روز** تا پایان اشتراک کاربر `{u['username']}` باقی مانده است.", parse_mode="Markdown")
        except Exception:
            pass

def run_scheduler():
    schedule.every().day.at("09:00").do(check_expired_users)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    threading.Thread(target=run_scheduler, daemon=True).start()
    bot.infinity_polling()
