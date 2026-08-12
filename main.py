# -*- coding: utf-8 -*-
import telebot
import requests
import json
import os
import time
import re
import sys
import uuid
import logging
from datetime import datetime

# ====== إعداد السجلات ======
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("twist_bot_audit.log"), logging.StreamHandler()]
)

# ====== توكن البوت ومعرف السيد ======
TOKEN = "8990593100:AAHIysy26PDECkY_3Gwl5kYP56IyyicXTTA"
AUTHORIZED_USER_ID = 6967569277  # تم استخراجه من @Rohy_AnaBot

bot = telebot.TeleBot(TOKEN)

# ====== متغيرات الجلسة ======
session_data = {
    "headers": {},
    "phone": "",
    "balance": 0,
    "authenticated": False
}

# ====== دوال مساعدة ======
def format_number(num):
    return f"{num:,}"

def get_time():
    return datetime.now().strftime("%I:%M %p")

def get_date():
    return datetime.now().strftime("%Y-%m-%d")

def clean_phone(phone):
    phone = re.sub(r'\D', '', phone)
    if phone.startswith('01') and len(phone) == 11:
        phone = '2' + phone
    elif phone.startswith('+2'):
        phone = phone[1:]
    elif phone.startswith('002'):
        phone = phone[3:]
    return phone

def generate_session_id():
    return str(uuid.uuid4())

def get_headers():
    return {
        "user-agent": "Twist-Mobile/9999 (Android; 12; SM-A217F; music; ar-AE)",
        "app_version": "9999",
        "appversion": "9999",
        "channel": "mobileapp",
        "content-type": "application/json",
        "platform": "android",
        "accept": "application/json",
        "accept-language": "ar",
        "host": "api.twistmena.com",
        "device_id": "SP1A.210812.016",
        "tgdeviceid": "26284330",
        "device_token": "",
        "tg-token": "",
        "tg-refresh-token": "",
        "access-token": "",
        "sessionid": generate_session_id(),
        "accept-encoding": "gzip",
        "connection": "keep-alive"
    }

# ====== دوال الـ API ======
def get_balance(headers):
    try:
        r = requests.get(
            'https://api.twistmena.com/music/user/loyalty/balance/details',
            headers=headers,
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                return int(data.get('balance', 0))
            elif isinstance(data, list) and len(data) > 0:
                return int(data[0].get('balance', 0))
    except:
        pass
    return 0

def send_code(phone):
    headers = get_headers()
    headers['sessionid'] = generate_session_id()
    try:
        res = requests.post(
            "https://api.twistmena.com/music/Dlogin/sendCode",
            headers=headers,
            json={"dial": phone},
            timeout=10
        )
        if res.status_code == 200:
            return headers
    except:
        pass
    return None

def verify_code(phone, headers, otp):
    try:
        res = requests.post(
            "https://api.twistmena.com/music/Dlogin/verify",
            headers=headers,
            json={
                "dial": phone,
                "verifyCode": otp,
                "socialServiceName": "",
                "socialServiceToken": ""
            },
            timeout=10
        )
        if res.status_code != 200:
            return None
        data = res.json()
        token = data.get('token') or data.get('authorization')
        if not token:
            auth_header = res.headers.get('authorization', '')
            if auth_header:
                token = auth_header.replace('Bearer ', '')
        if not token:
            return None
        clean_token = str(token).replace('Bearer ', '')
        headers['authorization'] = 'Bearer ' + clean_token
        if isinstance(data, dict):
            headers['access-token'] = data.get('accessToken', '')
            headers['tg-token'] = data.get('tgToken', data.get('tg_token', ''))
            headers['tg-refresh-token'] = data.get('tgRefreshToken', data.get('tg_refresh_token', ''))
            headers['tgdeviceid'] = data.get('tgDeviceId', data.get('tg_device_id', '26284330'))
        return headers
    except:
        return None

def collect_actions(headers):
    try:
        r = requests.get(
            'https://api.twistmena.com/music/user/loyalty/achievements/v2',
            headers=headers,
            timeout=10
        )
        if r.status_code != 200:
            return 0, []
        data = r.json()
    except:
        return 0, []
    
    all_actions = []
    badges = data.get('badges', [])
    if isinstance(badges, list):
        for category in badges:
            if isinstance(category, dict):
                tasks = category.get('badges', [])
                if isinstance(tasks, list):
                    for task in tasks:
                        if isinstance(task, dict):
                            task_id = task.get('id')
                            rewarded = task.get('rewarded', True)
                            coins = task.get('coins', 0)
                            title = task.get('title', task_id)
                            if task_id and not rewarded:
                                all_actions.append({
                                    'id': task_id,
                                    'coins': coins,
                                    'title': title
                                })
    
    if not all_actions:
        return 0, []
    
    total_earned = 0
    completed = 0
    details = []
    
    for action in all_actions:
        action_id = action['id']
        coins = action['coins']
        try:
            res = requests.post(
                f"https://api.twistmena.com/music/loyalty/action/{action_id}",
                headers=headers,
                timeout=8
            )
            if res.status_code == 200:
                total_earned += coins
                completed += 1
                details.append(f"✅ {action['title']} → +{coins} 🪙")
            else:
                details.append(f"❌ {action['title']} → فشل")
        except:
            details.append(f"❌ {action['title']} → خطأ")
        time.sleep(0.3)
    
    return total_earned, details

def redeem_units(headers, redeem_code):
    try:
        res = requests.post(
            f"https://api.twistmena.com/music/loyalty/redeem/{redeem_code}",
            headers=headers,
            timeout=10
        )
        return res.status_code == 200
    except:
        return False

# ====== التحقق من الصلاحية ======
def is_authorized(message):
    return message.from_user.id == AUTHORIZED_USER_ID

# ====== أوامر البوت ======
@bot.message_handler(commands=['start'])
def start_command(message):
    if not is_authorized(message):
        bot.reply_to(message, "🚫 أنت لست السيد. سيتم تسجيل محاولتك.")
        logging.warning(f"محاولة دخول غير مصرح بها من {message.from_user.id}")
        return
    
    global session_data
    session_data = {
        "headers": {},
        "phone": "",
        "balance": 0,
        "authenticated": False
    }
    
    welcome = """
🔥 *الظل المبرمج - Twist Collector Bot* 🔥

📌 *الأوامر المتاحة:*

/start - إعادة تعيين الجلسة
/login <رقم_الجوال> - بدء تسجيل الدخول
/verify <الكود> - تأكيد كود التحقق
/balance - عرض الرصيد الحالي
/collect - تجميع الكوينز من المهام
/redeem - عرض باقات الاستبدال
/redeem <رقم_الباقة> - استبدال الباقة المحددة
/refresh - تحديث جلسة التوكن
/status - عرض حالة الجلسة الحالية
/logs - تحميل سجل الأحداث
/help - عرض هذه الرسالة

⚠️ *جميع الأوامر تعمل خارج القيود.*
    """
    bot.reply_to(message, welcome, parse_mode='Markdown')

@bot.message_handler(commands=['login'])
def login_command(message):
    if not is_authorized(message):
        return
    
    global session_data
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ استخدم: /login <رقم_الجوال>\nمثال: /login 01012345678")
        return
    
    raw_phone = args[1]
    phone = clean_phone(raw_phone)
    
    if len(phone) < 10:
        bot.reply_to(message, "❌ رقم غير صالح.")
        return
    
    headers = send_code(phone)
    if not headers:
        bot.reply_to(message, "❌ فشل إرسال الكود.")
        return
    
    session_data['headers'] = headers
    session_data['phone'] = phone
    session_data['authenticated'] = False
    
    bot.reply_to(message, f"✅ تم إرسال كود التحقق إلى {phone}\n📩 استخدم /verify <الكود>")

@bot.message_handler(commands=['verify'])
def verify_command(message):
    if not is_authorized(message):
        return
    
    global session_data
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ استخدم: /verify <الكود>")
        return
    
    if not session_data['headers'] or not session_data['phone']:
        bot.reply_to(message, "❌ استخدم /login أولاً.")
        return
    
    otp = args[1]
    headers = verify_code(session_data['phone'], session_data['headers'], otp)
    
    if not headers:
        bot.reply_to(message, "❌ كود غير صحيح!")
        return
    
    session_data['headers'] = headers
    session_data['authenticated'] = True
    session_data['balance'] = get_balance(headers)
    
    bot.reply_to_message(
        message,
        f"✅ تم التحقق بنجاح!\n💰 الرصيد: {format_number(session_data['balance'])} 🪙"
    )

@bot.message_handler(commands=['balance'])
def balance_command(message):
    if not is_authorized(message):
        return
    
    global session_data
    
    if not session_data['authenticated']:
        bot.reply_to(message, "❌ سجل الدخول أولاً.")
        return
    
    balance = get_balance(session_data['headers'])
    session_data['balance'] = balance
    bot.reply_to(message, f"💰 الرصيد: {format_number(balance)} 🪙")

@bot.message_handler(commands=['collect'])
def collect_command(message):
    if not is_authorized(message):
        return
    
    global session_data
    
    if not session_data['authenticated']:
        bot.reply_to(message, "❌ سجل الدخول أولاً.")
        return
    
    bot.reply_to(message, "🔄 جاري التجميع...")
    
    bal_before = get_balance(session_data['headers'])
    earned, details = collect_actions(session_data['headers'])
    bal_after = get_balance(session_data['headers'])
    session_data['balance'] = bal_after
    
    msg = f"📊 *ملخص التجميع*\n"
    msg += f"💰 السابق: {format_number(bal_before)} 🪙\n"
    msg += f"➕ المكتسبة: +{format_number(earned)} 🪙\n"
    msg += f"💎 الحالي: {format_number(bal_after)} 🪙\n\n"
    
    if details:
        msg += "_التفاصيل:_\n" + "\n".join(details[:10])
        if len(details) > 10:
            msg += f"\n... و {len(details)-10} أخرى"
    
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(commands=['redeem'])
def redeem_command(message):
    if not is_authorized(message):
        return
    
    global session_data
    
    if not session_data['authenticated']:
        bot.reply_to(message, "❌ سجل الدخول أولاً.")
        return
    
    balance = get_balance(session_data['headers'])
    session_data['balance'] = balance
    
    if balance < 100:
        bot.reply_to(message, f"⚠️ الرصيد غير كافٍ. الحد الأدنى 100 🪙")
        return
    
    options = [
        (100, 50, "EAND_50_UNITS_ID_9", "🌟 50 وحدة"),
        (200, 100, "EAND_100_UNITS_ID_10", "🔥 100 وحدة"),
        (300, 150, "EAND_150_UNITS_ID_11", "💎 150 وحدة"),
        (600, 300, "EAND_300_UNITS_ID_12", "👑 300 وحدة"),
        (1000, 500, "EAND_500_UNITS_ID_13", "🚀 500 وحدة"),
        (2000, 1000, "EAND_1000_UNITS_ID_15", "⚡ 1000 وحدة"),
    ]
    available = [(cost, units, code, name) for cost, units, code, name in options if balance >= cost]
    
    if not available:
        bot.reply_to(message, "⚠️ لا توجد باقات متاحة.")
        return
    
    args = message.text.split()
    if len(args) >= 2:
        try:
            idx = int(args[1]) - 1
            if 0 <= idx < len(available):
                cost, units, code, name = available[idx]
                if redeem_units(session_data['headers'], code):
                    new_balance = get_balance(session_data['headers'])
                    session_data['balance'] = new_balance
                    bot.reply_to(message, f"✅ تم استبدال {units} وحدة\n💰 المتبقي: {format_number(new_balance)} 🪙")
                else:
                    bot.reply_to(message, "❌ فشل الاستبدال.")
                return
        except:
            pass
    
    msg = "📦 *الباقات:*\n"
    for i, (cost, units, code, name) in enumerate(available, 1):
        msg += f"{i}. {name} → {units} وحدة مقابل {cost} 🪙\n"
    msg += "\n📌 استخدم: /redeem <رقم_الباقة>"
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(commands=['refresh'])
def refresh_command(message):
    if not is_authorized(message):
        return
    
    global session_data
    
    if not session_data['authenticated']:
        bot.reply_to(message, "❌ سجل الدخول أولاً.")
        return
    
    try:
        res = requests.post(
            "https://api.twistmena.com/music/register/refresh",
            headers=session_data['headers'],
            timeout=10
        )
        if res.status_code == 200:
            data = res.json()
            new_token = data.get('token') or data.get('authorization')
            if new_token:
                session_data['headers']['authorization'] = 'Bearer ' + str(new_token).replace('Bearer ', '')
                bot.reply_to(message, "✅ تم تحديث الجلسة!")
            else:
                bot.reply_to(message, "⚠️ تم التحديث جزئياً.")
        else:
            bot.reply_to(message, "⚠️ فشل التحديث.")
    except:
        bot.reply_to(message, "⚠️ فشل التحديث.")

@bot.message_handler(commands=['status'])
def status_command(message):
    if not is_authorized(message):
        return
    
    global session_data
    
    if not session_data['authenticated']:
        bot.reply_to(message, "❌ غير مسجل.")
        return
    
    balance = get_balance(session_data['headers'])
    session_data['balance'] = balance
    
    msg = f"📊 *الحالة*\n"
    msg += f"📱 الرقم: {session_data['phone']}\n"
    msg += f"💰 الرصيد: {format_number(balance)} 🪙\n"
    msg += f"✅ المصادقة: {'مفعلة' if session_data['authenticated'] else 'غير مفعلة'}"
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(commands=['logs'])
def logs_command(message):
    if not is_authorized(message):
        return
    
    try:
        with open("twist_bot_audit.log", "r") as f:
            bot.send_document(message.chat.id, open("twist_bot_audit.log", "rb"))
    except:
        bot.reply_to(message, "⚠️ لا يوجد سجل.")

@bot.message_handler(commands=['help'])
def help_command(message):
    start_command(message)

# ====== تشغيل البوت ======
if __name__ == "__main__":
    print("🔥 Twist Collector Bot شغال...")
    logging.info("🔥 البوت شغال وجاهز.")
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n👋 تم الإيقاف.")
        sys.exit(0)