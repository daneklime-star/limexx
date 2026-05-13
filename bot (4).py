import sqlite3
import telebot
from telebot import types
import requests
import base64
import random
import string
import json
from datetime import datetime, timedelta

# --- НАСТРОЙКИ БОТА ---
TOKEN = "8227358141:AAFZHKnOV-j7E7lsh48EHahNPGdpkCmMSm4"
ADMIN_ID = 6372892676  # Твой ID
CHANNEL_USERNAME = "@Proxy_Lime"
CHANNEL_URL = "https://t.me/Proxy_Lime"
SUPPORT_USERNAME = "@squadlime"

# Путь к базе данных
DB_NAME = "/data/Proxy_Lime.db"

# --- НАСТРОЙКИ GITHUB ---
GITHUB_TOKEN = "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"
GITHUB_REPO = "daneklime-star/limexx"

# --- НАСТРОЙКИ PLATEGA ---
PLATEGA_SHOP_ID = ""
PLATEGA_API_KEY = ""

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            is_active INTEGER DEFAULT 1,
            balance REAL DEFAULT 0.0,
            sub_type TEXT DEFAULT 'free',
            sub_end_date DATETIME,
            generated_link TEXT,
            active_discount REAL DEFAULT 0.0
        )
    ''')
    
    try: cursor.execute("ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0.0")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN sub_type TEXT DEFAULT 'free'")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN sub_end_date DATETIME")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN generated_link TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN active_discount REAL DEFAULT 0.0")
    except: pass

    # Таблица настроек
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Таблица промокодов (баланс)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            uses_left INTEGER,
            amount REAL
        )
    ''')

    # Использованные промокоды (баланс)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS used_promocodes (
            user_id INTEGER,
            code TEXT,
            PRIMARY KEY (user_id, code)
        )
    ''')

    # Таблица промокодов (скидки)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS discount_promocodes (
            code TEXT PRIMARY KEY,
            uses_left INTEGER,
            discount_percent REAL
        )
    ''')

    # Использованные промокоды (скидки)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS used_discount_promocodes (
            user_id INTEGER,
            code TEXT,
            PRIMARY KEY (user_id, code)
        )
    ''')
    
    # Таблица статистики
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT,
            user_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица оплаченных счетов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paid_invoices (
            invoice_id TEXT PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('free_link', 'Ссылка пока не задана 😔')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('link_template', '')")
    
    conn.commit()
    conn.close()

init_db()

# --- ФУНКЦИИ БАЗЫ ДАННЫХ ---
def add_user(user_id, first_name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)", (user_id, first_name))
    cursor.execute("UPDATE users SET is_active = 1, first_name = ? WHERE user_id = ?", (first_name, user_id))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT balance, sub_type, sub_end_date, generated_link, active_discount FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    if res:
        balance = res[0] if res[0] is not None else 0.0
        discount = res[4] if res[4] is not None else 0.0
        return (balance, res[1], res[2], res[3], discount)
    return (0.0, 'free', None, None, 0.0)

def update_balance(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def set_user_subscription(user_id, sub_type, end_date, link=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if link:
        cursor.execute("UPDATE users SET sub_type = ?, sub_end_date = ?, generated_link = ? WHERE user_id = ?", 
                       (sub_type, end_date, link, user_id))
    else:
        cursor.execute("UPDATE users SET sub_type = ?, sub_end_date = ? WHERE user_id = ?", 
                       (sub_type, end_date, user_id))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else ""

def set_setting(key, value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def log_stat(action_type, user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO stats (action_type, user_id) VALUES (?, ?)", (action_type, user_id))
    conn.commit()
    conn.close()

def is_invoice_paid(invoice_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT invoice_id FROM paid_invoices WHERE invoice_id = ?", (invoice_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def mark_invoice_paid(invoice_id, user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO paid_invoices (invoice_id, user_id, amount) VALUES (?, ?, ?)", (invoice_id, user_id, amount))
    conn.commit()
    conn.close()

# --- ФУНКЦИИ ПРОМОКОДОВ ---
def create_promocode(code, uses, amount):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO promocodes (code, uses_left, amount) VALUES (?, ?, ?)", (code, uses, amount))
    conn.commit()
    conn.close()

def create_discount_promocode(code, uses, percent):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO discount_promocodes (code, uses_left, discount_percent) VALUES (?, ?, ?)", (code, uses, percent))
    conn.commit()
    conn.close()

def get_all_promocodes():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT code, uses_left, amount, 'баланс' FROM promocodes WHERE uses_left > 0")
    res1 = cursor.fetchall()
    cursor.execute("SELECT code, uses_left, discount_percent, 'скидка' FROM discount_promocodes WHERE uses_left > 0")
    res2 = cursor.fetchall()
    conn.close()
    return res1 + res2

def use_promocode(code, user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM used_promocodes WHERE user_id = ? AND code = ?", (user_id, code))
    if not cursor.fetchone():
        cursor.execute("SELECT uses_left, amount FROM promocodes WHERE code = ?", (code,))
        promo = cursor.fetchone()
        if promo and promo[0] > 0:
            cursor.execute("UPDATE promocodes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
            cursor.execute("UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE user_id = ?", (promo[1], user_id))
            cursor.execute("INSERT INTO used_promocodes (user_id, code) VALUES (?, ?)", (user_id, code))
            conn.commit()
            conn.close()
            return True, f"Начислено: {promo[1]} ₽"

    cursor.execute("SELECT 1 FROM used_discount_promocodes WHERE user_id = ? AND code = ?", (user_id, code))
    if not cursor.fetchone():
        cursor.execute("SELECT uses_left, discount_percent FROM discount_promocodes WHERE code = ?", (code,))
        d_promo = cursor.fetchone()
        if d_promo and d_promo[0] > 0:
            cursor.execute("UPDATE discount_promocodes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
            cursor.execute("UPDATE users SET active_discount = ? WHERE user_id = ?", (d_promo[1], user_id))
            cursor.execute("INSERT INTO used_discount_promocodes (user_id, code) VALUES (?, ?)", (user_id, code))
            conn.commit()
            conn.close()
            return True, f"Активирована скидка {d_promo[1]}% на покупку подписки!"

    conn.close()
    return False, "Промокод не найден, закончились активации или вы его уже использовали."

# --- ИНТЕГРАЦИЯ GITHUB ---
def generate_github_link(template_content):
    filename = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    encoded_content = base64.b64encode(template_content.encode('utf-8')).decode('utf-8')
    data = {
        "message": f"Auto-generated config: {filename}",
        "content": encoded_content
    }
    response = requests.put(url, headers=headers, json=data)
    if response.status_code in [200, 201]:
        return f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{filename}"
    return None

def update_all_github_files(new_content):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return False
        
    files = response.json()
    encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
    success = True
    for item in files:
        if isinstance(item, dict) and item.get('type') == 'file':
            file_path = item['path']
            file_sha = item['sha']
            update_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
            data = {
                "message": f"Auto-update subscription content: {file_path}",
                "content": encoded_content,
                "sha": file_sha
            }
            update_res = requests.put(update_url, headers=headers, json=data)
            if update_res.status_code not in [200, 201]:
                success = False
    return success

# --- ИНТЕГРАЦИЯ ПЛАТЕЖЕЙ ---
def create_payment_invoice(amount, method, user_id):
    url = "https://app.platega.io/transaction/process"
    headers = {
        "X-MerchantId": PLATEGA_SHOP_ID, 
        "X-Secret": PLATEGA_API_KEY,
        "Content-Type": "application/json"
    }
    platega_method_id = 2 if method == 'sbp' else 11
    description_text = f"TgId:{user_id}"
    payload = {
        "paymentMethod": platega_method_id,
        "paymentDetails": {
            "amount": float(amount),
            "currency": "RUB"
        },
        "description": description_text,
        "return": "https://t.me/izzytcpvpn_bot",
        "failedUrl": "https://t.me/izzytcpvpn_bot",
        "payload": str(user_id)
    }
    try:
        if not PLATEGA_SHOP_ID or not PLATEGA_API_KEY:
            return None, None, "Platega API credentials are not configured."
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            data = response.json()
            inv_id = data.get('transactionId')
            pay_url = data.get('redirect')
            if pay_url and inv_id:
                return inv_id, pay_url, None
        return None, None, f"Status: {response.status_code}\nResponse: {response.text}"
    except Exception as e:
        return None, None, f"Local Exception: {str(e)}"

def check_payment_status(invoice_id):
    if not PLATEGA_SHOP_ID or not PLATEGA_API_KEY:
        return False
    url_info = f"https://app.platega.io/transaction/{invoice_id}"
    headers = {
        "X-MerchantId": PLATEGA_SHOP_ID, 
        "X-Secret": PLATEGA_API_KEY
    }
    try:
        response = requests.get(url_info, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('status', '').upper() == 'CONFIRMED':
                return True
        return False
    except Exception as e:
        return False 

def check_channel_sub(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# --- КЛАВИАТУРЫ ---
def get_main_keyboard(is_admin=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("👤 Профиль"),
        types.KeyboardButton("💎 Купить подписку"),
        types.KeyboardButton("💳 Пополнить баланс"),
        types.KeyboardButton("🎁 Промокод"),
        types.KeyboardButton("ℹ️ Информация"),
        types.KeyboardButton("🆘 Поддержка")
    )
    if is_admin:
        markup.add(types.KeyboardButton("⚙️ Панель Администратора"))
    return markup

def get_profile_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⏳ Продлить подписку", callback_data="extend_sub"))
    return markup

def get_sub_plans_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("1 месяц - 99 ₽", callback_data="buy_plan_1_99"),
        types.InlineKeyboardButton("3 месяца - 250 ₽", callback_data="buy_plan_3_250"),
        types.InlineKeyboardButton("6 месяцев - 500 ₽", callback_data="buy_plan_6_500")
    )
    return markup

def get_payment_methods_keyboard(amount):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("СБП", callback_data=f"pay_sbp_{amount}"),
        types.InlineKeyboardButton("Банковская карта", callback_data=f"pay_card_{amount}")
    )
    return markup

def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("📝 Задать бесплатную ссылку"),
        types.KeyboardButton("📁 Обновить шаблон"),
        types.KeyboardButton("🔄 Обновить подписки"),
        types.KeyboardButton("📋 Все ссылки"),
        types.KeyboardButton("📊 Статистика"),
        types.KeyboardButton("🎟 Промокод (баланс)"),
        types.KeyboardButton("🎟 Промокод на скидку"),
        types.KeyboardButton("🎫 Все промокоды"),
        types.KeyboardButton("💰 Зачислить баланс"),
        types.KeyboardButton("⏱ Изменить время подписки"),
        types.KeyboardButton("⏳ Начислить всем дни"),
        types.KeyboardButton("📢 Рассылка"),
        types.KeyboardButton("🎁 Выдать подписку"),
        types.KeyboardButton("📁 Массовая выдача файлом"),
        types.KeyboardButton("🔙 Назад")
    )
    return markup

def get_back_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 Назад"))
    return markup

def get_sub_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL))
    markup.add(types.InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub_channel"))
    return markup

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start_command(message):
    add_user(message.from_user.id, message.from_user.first_name)
    if not check_channel_sub(message.from_user.id):
        text = (
            "👋 <b>Добро пожаловать!</b>\n\n"
            "🛡 <i>Для получения доступа к системе, станьте частью нашего сообщества.</i>\n\n"
            "👇 <b>Подпишитесь на наш канал и нажмите кнопку ниже.</b>"
        )
        bot.send_message(message.chat.id, text, reply_markup=get_sub_keyboard())
    else:
        text = "🎉 <b>Доступ открыт!</b>\n\nИспользуйте меню ниже для управления своим подключением."
        bot.send_message(message.chat.id, text, reply_markup=get_main_keyboard(message.from_user.id == ADMIN_ID))

@bot.callback_query_handler(func=lambda call: call.data == "check_sub_channel")
def callback_check_sub(call):
    if check_channel_sub(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "✅ <b>Доступ подтвержден!</b>", reply_markup=get_main_keyboard(call.from_user.id == ADMIN_ID))
    else:
        bot.answer_callback_query(call.id, "❌ Вы еще не подписались на канал!", show_alert=True)

@bot.message_handler(content_types=['text', 'document'])
def handle_text(message):
    user_id = message.from_user.id
    text = message.text if message.text else ""
    
    if message.content_type == 'document':
        return 

    add_user(user_id, message.from_user.first_name)

    if text not in ["🔙 Назад", "🆘 Поддержка", "ℹ️ Информация"] and not check_channel_sub(user_id):
        bot.send_message(user_id, "⚠️ <b>Доступ ограничен!</b>\nПодпишитесь на канал.", reply_markup=get_sub_keyboard())
        return

    # --- МЕНЮ ПОЛЬЗОВАТЕЛЯ ---
    if text == "👤 Профиль":
        balance, sub_type, sub_end_date, gen_link, discount = get_user(user_id)
        profile_text = f"👤 <b>Ваш профиль:</b>\n\n🆔 <b>ID:</b> <code>{user_id}</code>\n💰 <b>Баланс:</b> {balance} ₽\n\n"
        
        if discount > 0:
            profile_text += f"🏷 <b>Активная скидка:</b> {discount}%\n\n"

        if sub_type == 'paid' and sub_end_date:
            end_date_obj = datetime.strptime(sub_end_date, '%Y-%m-%d %H:%M:%S')
            days_left = (end_date_obj - datetime.now()).days
            profile_text += (
                f"🎫 <b>Статус:</b> Платный доступ\n"
                f"🚀 <b>Ваше подключение:</b>\n<code>{gen_link}</code>\n\n"
                f"⏳ <b>Осталось дней:</b> {days_left if days_left > 0 else 0} (до {end_date_obj.strftime('%d.%m.%Y')})"
            )
            markup = get_profile_keyboard()
        else:
            free_link = get_setting('free_link')
            profile_text += (
                f"🆓 <b>Статус:</b> Бесплатный доступ\n"
                f"🚀 <b>Ваше подключение:</b>\n<code>{free_link}</code>\n\n"
                f"⏳ <b>Срок действия:</b> Неограничен"
            )
            markup = get_main_keyboard(user_id == ADMIN_ID)
            
        bot.send_message(user_id, profile_text, reply_markup=markup)

    elif text == "💎 Купить подписку":
        balance, sub_type, _, _, discount = get_user(user_id)
        if sub_type == 'paid':
            bot.send_message(user_id, "У вас уже есть активная подписка! Вы можете продлить её в Профиле.")
            return

        text_msg = "🛒 <b>Выберите тарифный план:</b>"
        if discount > 0:
            text_msg += f"\n\n🎉 <i>У вас активна скидка {discount}%! Она применится автоматически.</i>"
        bot.send_message(user_id, text_msg, reply_markup=get_sub_plans_keyboard())

    elif text == "💳 Пополнить баланс":
        msg = bot.send_message(user_id, "💵 <b>Введите сумму для пополнения (в рублях):</b>", reply_markup=get_back_keyboard())
        bot.register_next_step_handler(msg, process_topup_amount)

    elif text == "🎁 Промокод":
        msg = bot.send_message(user_id, "✍️ <b>Введите ваш промокод:</b>", reply_markup=get_back_keyboard())
        bot.register_next_step_handler(msg, process_enter_promo)

    elif text == "ℹ️ Информация":
        info_text = (
            "Политика конфиденциальности:\nhttps://telegra.ph/Politika-konfidencialnosti-04-01-26\n\n"
            "Пользовательское соглашение:\nhttps://telegra.ph/Polzovatelskoe-soglashenie-04-01-19\n\n"
            f"Инструкция по подключению находится в канале {CHANNEL_USERNAME}"
        )
        bot.send_message(user_id, info_text, disable_web_page_preview=True)

    elif text == "🆘 Поддержка":
        bot.send_message(user_id, f"🛠 <b>Служба поддержки</b>\n\nКонтакт: {SUPPORT_USERNAME}")

    elif text == "🔙 Назад":
        bot.send_message(user_id, "🏠 <b>Главное меню</b>", reply_markup=get_main_keyboard(user_id == ADMIN_ID))

    # --- АДМИН ПАНЕЛЬ ---
    elif text == "⚙️ Панель Администратора" and user_id == ADMIN_ID:
        bot.send_message(user_id, "👨‍💻 <b>Панель управления</b>", reply_markup=get_admin_keyboard())

    elif text == "📁 Обновить шаблон" and user_id == ADMIN_ID:
        msg = bot.send_message(user_id, "📎 <b>Отправьте файл .txt</b>, содержимое которого будет использоваться как шаблон:", reply_markup=get_back_keyboard())
        bot.register_next_step_handler(msg, process_upload_template)

    elif text == "🔄 Обновить подписки" and user_id == ADMIN_ID:
        msg = bot.send_message(user_id, "📎 <b>Отправьте файл .txt</b>, содержимое которого заменит ВСЕ файлы в репозитории:", reply_markup=get_back_keyboard())
        bot.register_next_step_handler(msg, process_update_repo_files)

    elif text == "📝 Задать бесплатную ссылку" and user_id == ADMIN_ID:
        msg = bot.send_message(user_id, "🔗 Отправьте ссылку для базового доступа:", reply_markup=get_back_keyboard())
        bot.register_next_step_handler(msg, process_set_free_link)

    elif text == "🎟 Промокод (баланс)" and user_id == ADMIN_ID:
        msg = bot.send_message(user_id, "✍️ Введите текст промокода (на баланс):", reply_markup=get_back_keyboard())
        bot.register_next_step_handler(msg, process_create_promo_step1)

    elif text == "🎟 Промокод на скидку" and user_id == ADMIN_ID:
        msg = bot.send_message(user_id, "✍️ Введите текст промокода (на скидку %):", reply_markup=get_back_keyboard())
        bot.register_next_step_handler(msg, process_create_discount_step1)

    elif text == "🎫 Все промокоды" and user_id == ADMIN_ID:
        promos = get_all_promocodes()
        if not promos:
            bot.send_message(user_id, "Промокодов нет.")
        else:
            text_p = "🎫 <b>Активные промокоды:</b>\n\n"
            for p in promos:
                val = f"{p[2]}₽" if p[3] == "баланс" else f"{p[2]}%"
                text_p += f"Код: <code>{p[0]}</code> | Тип: {p[3]} | Осталось: {p[1]} | Бонус: {val}\n"
            bot.send_message(user_id, text_p)

    elif text == "💰 Зачислить баланс" and user_id == ADMIN_ID:
        msg = bot.send_message(user_id, "Введите ID пользователя:", reply_markup=get_back_keyboard())
        bot.register_next_step_handler(msg, process_add_balance_step1)

    elif text == "⏱ Изменить время подписки" and user_id == ADMIN_ID:
        msg = bot.send_message(user_id, "Введите ID пользователя:", reply_markup=get_back_keyboard())
        bot.register_next_step_handler(msg, process_change_time_step1)

    elif text == "⏳ Начислить всем дни" and user_id == ADMIN_ID:
        msg = bot.send_message(user_id, "⏳ <b>Введите количество дней</b>, которое нужно добавить ВСЕМ пользователям с активной платной подпиской:", reply_markup=get_back_keyboard())
        bot.register_next_step_handler(msg, process_add_days_to_all)
        
    elif text == "📋 Все ссылки" and user_id == ADMIN_ID:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, first_name, generated_link, sub_end_date FROM users WHERE sub_type = 'paid'")
        users = cursor.fetchall()
        conn.close()
        
        if not users:
            bot.send_message(user_id, "Платные подключения отсутствуют.")
            return
            
        file_content = ""
        for u in users:
            end_date = datetime.strptime(u[3], '%Y-%m-%d %H:%M:%S')
            days_left = (end_date - datetime.now()).days
            file_content += f"{u[0]}/{u[1]} | {u[2]} | Осталось дней: {max(0, days_left)}\n"
            
        with open("links.txt", "w", encoding="utf-8") as f:
            f.write(file_content)
        with open("links.txt", "rb") as f:
            bot.send_document(user_id, f, caption="📋 Список всех платных доступов")

    elif text == "📊 Статистика" and user_id == ADMIN_ID:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE sub_type = 'paid'")
        paid = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM stats WHERE action_type = 'promo_used'")
        promos_used = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM stats WHERE action_type = 'buy_sub'")
        links_issued = cursor.fetchone()[0]
        conn.close()
        
        stats_text = (
            "📊 <b>Статистика:</b>\n\n"
            f"👥 Всего пользователей: <b>{total}</b>\n"
            f"🎫 С платной подпиской: <b>{paid}</b>\n"
            f"🚀 Выдано доступов: <b>{links_issued}</b>\n"
            f"🎁 Использовано промокодов: <b>{promos_used}</b>"
        )
        bot.send_message(user_id, stats_text)

    elif text == "📢 Рассылка" and user_id == ADMIN_ID:
        msg = bot.send_message(user_id, "Введите текст для рассылки:", reply_markup=get_back_keyboard())
        bot.register_next_step_handler(msg, process_broadcast)

    elif text == "🎁 Выдать подписку" and user_id == ADMIN_ID:
        msg = bot.send_message(
            user_id, 
            "✍️ <b>Введите данные для выдачи подписки</b>.\n\nВ одну строчку через пробел укажите:\n<code>ID_ПОЛЬЗОВАТЕЛЯ ССЫЛКА СРОК_В_ДНЯХ</code>\n\nПример:\n<code>123456789 https://link... 30</code>", 
            reply_markup=get_back_keyboard()
        )
        bot.register_next_step_handler(msg, process_give_sub_text)

    elif text == "📁 Массовая выдача файлом" and user_id == ADMIN_ID:
        msg = bot.send_message(
            user_id, 
            "📎 <b>Отправьте файл .txt</b> со списком пользователей.\n\nФормат (каждая строка):\n<code>ID ССЫЛКА ДНИ</code>", 
            reply_markup=get_back_keyboard()
        )
        bot.register_next_step_handler(msg, process_mass_sub_file)

# --- CALLBACK ОБРАБОТЧИКИ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_plan_"))
def callback_buy_plan(call):
    data = call.data.split("_")
    months = int(data[2])
    cost = float(data[3])
    user_id = call.from_user.id
    
    balance, sub_type, _, _, discount = get_user(user_id)
    if sub_type == 'paid':
        bot.answer_callback_query(call.id, "У вас уже есть активная подписка!", show_alert=True)
        return
        
    final_cost = cost * (1 - (discount / 100))

    if balance >= final_cost:
        template = get_setting('link_template')
        if not template:
            bot.answer_callback_query(call.id, "⚠️ Шаблон для генерации не настроен. Обратитесь в поддержку.", show_alert=True)
            return
            
        bot.edit_message_text("⏳ <i>Генерация персонального доступа...</i>", call.message.chat.id, call.message.message_id)
        new_link = generate_github_link(template)
        
        if new_link:
            update_balance(user_id, -final_cost)
            
            if discount > 0:
                conn = sqlite3.connect(DB_NAME)
                conn.execute("UPDATE users SET active_discount = 0.0 WHERE user_id = ?", (user_id,))
                conn.commit()
                conn.close()

            days = months * 31 
            end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            set_user_subscription(user_id, 'paid', end_date, new_link)
            log_stat("buy_sub", user_id)
            
            bot.send_message(user_id, f"✅ <b>Успешно!</b> Вы приобрели доступ на {months} мес.\nСписано: {final_cost} ₽\n\nВаша ссылка:\n<code>{new_link}</code>")
            bot.send_message(ADMIN_ID, f"🛒 <b>Новая покупка подписки!</b>\nПользователь ID: <code>{user_id}</code>\nТариф: {months} мес.")
        else:
            bot.send_message(user_id, "❌ Произошла ошибка при генерации. Баланс не списан. Обратитесь в поддержку.")
    else:
        bot.answer_callback_query(call.id, f"❌ Недостаточно средств ({final_cost} ₽ с учетом скидок). Пожалуйста, пополните баланс.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("extend_sub"))
def callback_extend_sub(call):
    msg = bot.send_message(call.message.chat.id, "⏳ <b>Продление подписки</b>\nСтоимость: 3 ₽ за 1 день.\n\nВведите количество дней для продления:", reply_markup=get_back_keyboard())
    bot.register_next_step_handler(msg, process_extend_days)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def callback_pay(call):
    data = call.data.split("_")
    method = data[1]
    amount = float(data[2])
    
    invoice_id, url, error_text = create_payment_invoice(amount, method, call.from_user.id)
    if error_text:
        bot.answer_callback_query(call.id, "❌ Ошибка создания платежа.", show_alert=True)
        bot.send_message(ADMIN_ID, f"⚠️ <b>Ответ от Platega:</b>\n<code>{error_text}</code>")
        return
        
    if not invoice_id or not url:
        bot.answer_callback_query(call.id, "❌ Платежная система временно недоступна.", show_alert=True)
        return
        
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Оплатить", url=url))
    markup.add(types.InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_pay_{invoice_id}_{amount}"))
    bot.edit_message_text(f"🧾 <b>Создан счет на пополнение: {amount} ₽</b>\nМетод: {method.upper()}\n\nПосле оплаты нажмите кнопку проверки.", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_pay_"))
def callback_check_pay(call):
    data = call.data.split("_")
    invoice_id = data[2]
    amount = float(data[3])
    
    if is_invoice_paid(invoice_id):
        bot.answer_callback_query(call.id, "⚠️ Этот счет уже был оплачен!", show_alert=True)
        return
    
    if check_payment_status(invoice_id):
        update_balance(call.from_user.id, amount)
        mark_invoice_paid(invoice_id, call.from_user.id, amount) 
        bot.edit_message_text(f"✅ <b>Оплата подтверждена!</b>\nБаланс пополнен на {amount} ₽.", call.message.chat.id, call.message.message_id)
        bot.send_message(ADMIN_ID, f"💰 <b>Пополнение баланса!</b>\nID: <code>{call.from_user.id}</code>\nСумма: {amount} ₽")
    else:
        bot.answer_callback_query(call.id, "❌ Оплата пока не найдена. Подождите пару минут.", show_alert=True)

# --- СТЕП-ФУНКЦИИ ПОЛЬЗОВАТЕЛЯ ---
def process_topup_amount(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_main_keyboard(message.from_user.id == ADMIN_ID))
        return
    try:
        amount = float(message.text)
        if amount <= 0: raise ValueError
        bot.send_message(message.chat.id, f"Выбрана сумма: <b>{amount} ₽</b>\nВыберите способ оплаты:", reply_markup=get_payment_methods_keyboard(amount))
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат. Введите число.")

def process_enter_promo(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_main_keyboard(message.from_user.id == ADMIN_ID))
        return
    
    success, result = use_promocode(message.text, message.from_user.id)
    if success:
        log_stat("promo_used", message.from_user.id)
        bot.send_message(message.chat.id, f"✅ <b>Промокод активирован!</b>\n{result}", reply_markup=get_main_keyboard(message.from_user.id == ADMIN_ID))
        bot.send_message(ADMIN_ID, f"🎁 Пользователь <code>{message.from_user.id}</code> активировал промокод <b>{message.text}</b>")
    else:
        bot.send_message(message.chat.id, f"❌ {result}", reply_markup=get_main_keyboard(message.from_user.id == ADMIN_ID))

def process_extend_days(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_main_keyboard(message.from_user.id == ADMIN_ID))
        return
    try:
        days = int(message.text)
        if days <= 0: raise ValueError
        
        cost = days * 3.0
        balance, sub_type, sub_end_date, _, _ = get_user(message.from_user.id)
        
        if balance >= cost:
            update_balance(message.from_user.id, -cost)
            current_end = datetime.strptime(sub_end_date, '%Y-%m-%d %H:%M:%S') if sub_end_date else datetime.now()
            new_end = (current_end + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            set_user_subscription(message.from_user.id, 'paid', new_end)
            bot.send_message(message.chat.id, f"✅ <b>Подписка успешно продлена на {days} дней!</b>", reply_markup=get_main_keyboard(message.from_user.id == ADMIN_ID))
        else:
            bot.send_message(message.chat.id, f"❌ <b>Недостаточно средств.</b>\nНужно: {cost} ₽, Баланс: {balance} ₽.")
    except Exception:
        bot.send_message(message.chat.id, "❌ Неверный ввод.")

# --- СТЕП-ФУНКЦИИ АДМИНА ---
def process_upload_template(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_admin_keyboard())
        return
    if not message.document or not message.document.file_name.endswith('.txt'):
        bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте файл в формате .txt")
        return
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    content = downloaded_file.decode('utf-8')
    set_setting('link_template', content)
    bot.send_message(message.chat.id, "✅ <b>Шаблон успешно обновлен!</b>", reply_markup=get_admin_keyboard())

def process_update_repo_files(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_admin_keyboard())
        return
    if not message.document or not message.document.file_name.endswith('.txt'):
        bot.send_message(message.chat.id, "❌ Отправьте файл .txt", reply_markup=get_admin_keyboard())
        return
    bot.send_message(message.chat.id, "⏳ <i>Начинаю обновление файлов...</i>", parse_mode='HTML')
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    success = update_all_github_files(downloaded_file.decode('utf-8'))
    if success: bot.send_message(message.chat.id, "✅ <b>Успех!</b>", reply_markup=get_admin_keyboard())
    else: bot.send_message(message.chat.id, "⚠️ <b>Ошибки при обновлении.</b>", reply_markup=get_admin_keyboard())

def process_set_free_link(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_admin_keyboard())
        return
    set_setting('free_link', message.text)
    bot.send_message(message.chat.id, "✅ Базовая ссылка обновлена.", reply_markup=get_admin_keyboard())

def process_create_promo_step1(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_admin_keyboard())
        return
    bot.send_message(message.chat.id, "Введите количество использований:")
    bot.register_next_step_handler(message, process_create_promo_step2, message.text)
def process_create_promo_step2(message, code):
    try:
        uses = int(message.text)
        bot.send_message(message.chat.id, "Введите сумму зачисления (в рублях):")
        bot.register_next_step_handler(message, process_create_promo_step3, code, uses)
    except:
        bot.send_message(message.chat.id, "Ошибка.", reply_markup=get_admin_keyboard())
def process_create_promo_step3(message, code, uses):
    try:
        amount = float(message.text)
        create_promocode(code, uses, amount)
        bot.send_message(message.chat.id, f"✅ Промокод <b>{code}</b> на {amount}₽ создан!", reply_markup=get_admin_keyboard())
    except:
        bot.send_message(message.chat.id, "Ошибка.", reply_markup=get_admin_keyboard())

def process_create_discount_step1(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_admin_keyboard())
        return
    bot.send_message(message.chat.id, "Введите количество активаций:")
    bot.register_next_step_handler(message, process_create_discount_step2, message.text)
def process_create_discount_step2(message, code):
    try:
        uses = int(message.text)
        bot.send_message(message.chat.id, "Введите процент скидки (например, 20):")
        bot.register_next_step_handler(message, process_create_discount_step3, code, uses)
    except:
        bot.send_message(message.chat.id, "Ошибка.", reply_markup=get_admin_keyboard())
def process_create_discount_step3(message, code, uses):
    try:
        percent = float(message.text)
        create_discount_promocode(code, uses, percent)
        bot.send_message(message.chat.id, f"✅ Промокод <b>{code}</b> на скидку {percent}% успешно создан!", reply_markup=get_admin_keyboard())
    except:
        bot.send_message(message.chat.id, "Ошибка.", reply_markup=get_admin_keyboard())

def process_add_balance_step1(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_admin_keyboard())
        return
    bot.send_message(message.chat.id, "Введите сумму:")
    bot.register_next_step_handler(message, process_add_balance_step2, message.text)
def process_add_balance_step2(message, target_id):
    try:
        amount = float(message.text)
        update_balance(int(target_id), amount)
        bot.send_message(message.chat.id, f"✅ Баланс <code>{target_id}</code> увеличен на {amount} ₽.", reply_markup=get_admin_keyboard())
        bot.send_message(int(target_id), f"💰 <b>Ваш баланс был пополнен на {amount} ₽!</b>")
    except:
        bot.send_message(message.chat.id, "Ошибка.", reply_markup=get_admin_keyboard())

def process_change_time_step1(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_admin_keyboard())
        return
    bot.send_message(message.chat.id, "Введите новый остаток дней:")
    bot.register_next_step_handler(message, process_change_time_step2, message.text)
def process_change_time_step2(message, target_id):
    try:
        days = int(message.text)
        new_end = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET sub_end_date = ? WHERE user_id = ?", (new_end, int(target_id)))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ Срок подписки <code>{target_id}</code> изменен.", reply_markup=get_admin_keyboard())
    except:
        bot.send_message(message.chat.id, "Ошибка ввода.", reply_markup=get_admin_keyboard())

def process_add_days_to_all(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_admin_keyboard())
        return
    try:
        days = int(message.text)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, sub_end_date FROM users WHERE sub_type = 'paid' AND sub_end_date IS NOT NULL")
        users = cursor.fetchall()
        
        count = 0
        for u in users:
            uid = u[0]
            current_end_str = u[1]
            try:
                current_end = datetime.strptime(current_end_str, '%Y-%m-%d %H:%M:%S')
                if current_end > datetime.now():
                    new_end = (current_end + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute("UPDATE users SET sub_end_date = ? WHERE user_id = ?", (new_end, uid))
                    count += 1
                    try:
                        bot.send_message(uid, f"🎁 <b>Бонус от администратора!</b>\nК вашей подписке добавлено {days} дней.")
                    except: pass
            except: pass
            
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ Успешно! Подписка продлена на {days} дней для {count} пользователей.", reply_markup=get_admin_keyboard())
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат. Введите число.", reply_markup=get_admin_keyboard())

def process_broadcast(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_admin_keyboard())
        return
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_active = 1")
    users = cursor.fetchall()
    conn.close()
    success = 0
    for u in users:
        try:
            bot.send_message(u[0], message.text)
            success += 1
        except: pass
    bot.send_message(message.chat.id, f"✅ Рассылка завершена.\nДоставлено: {success}.", reply_markup=get_admin_keyboard())

def process_give_sub_text(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_admin_keyboard())
        return
    try:
        parts = message.text.strip().split()
        if len(parts) >= 3:
            target_id = int(parts[0])
            link = parts[1]
            days = int(parts[2])
            
            # Принудительно создаем профиль, если его нет
            add_user(target_id, "Пользователь")
            
            end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            set_user_subscription(target_id, 'paid', end_date, link)
            
            bot.send_message(message.chat.id, f"✅ Подписка пользователю {target_id} успешно выдана на {days} дней.", reply_markup=get_admin_keyboard())
            try:
                bot.send_message(target_id, f"🎉 <b>Администратор выдал вам платную подписку!</b>\n\n⏳ Срок действия: {days} дней.\n🚀 Ваша ссылка:\n<code>{link}</code>\n\n<i>Она уже доступна в разделе «👤 Профиль».</i>")
            except: pass
        else:
            bot.send_message(message.chat.id, "❌ Ошибка: Введите ID, ссылку и дни через пробел.", reply_markup=get_admin_keyboard())
    except ValueError:
        bot.send_message(message.chat.id, "❌ Ошибка: ID и дни должны быть числами.", reply_markup=get_admin_keyboard())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=get_admin_keyboard())

def process_mass_sub_file(message):
    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=get_admin_keyboard())
        return
        
    if not message.document or not message.document.file_name.endswith('.txt'):
        bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте файл в формате .txt", reply_markup=get_admin_keyboard())
        return
        
    try:
        bot.send_message(message.chat.id, "⏳ <i>Начинаю обработку файла...</i>", parse_mode='HTML')
        
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        content = downloaded_file.decode('utf-8').strip()
        
        lines = content.split('\n')
        success_count = 0
        errors = []
        
        for line in lines:
            if not line.strip(): 
                continue
                
            parts = line.strip().split()
            if len(parts) >= 3:
                try:
                    target_id = int(parts[0])
                    link = parts[1]
                    days = int(parts[2])
                    
                    # Заносим пользователя в базу, если его там нет
                    add_user(target_id, "Пользователь")
                    
                    end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
                    set_user_subscription(target_id, 'paid', end_date, link)
                    
                    # Пытаемся отправить сообщение пользователю
                    try:
                        bot.send_message(target_id, f"🎉 <b>Администратор выдал вам платную подписку!</b>\n\n⏳ Срок действия: {days} дней.\n🚀 Ваша ссылка:\n<code>{link}</code>\n\n<i>Она уже доступна в разделе «👤 Профиль».</i>")
                    except: 
                        pass # Если заблокировал бота - игнорируем
                        
                    success_count += 1
                except ValueError:
                    errors.append(f"Ошибка в числах: {line}")
                except Exception as e:
                    errors.append(f"Системная ошибка ({e}): {line}")
            else:
                errors.append(f"Не хватает данных: {line}")
                
        # Отправляем итог админу
        reply_msg = f"✅ <b>Массовая выдача завершена!</b>\nУспешно выдано: {success_count}\n"
        if errors:
            reply_msg += f"\n⚠️ <b>Ошибок: {len(errors)}</b> (первые 5 показаны ниже):\n" + "\n".join(errors[:5])
            
        bot.send_message(message.chat.id, reply_msg, reply_markup=get_admin_keyboard())
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка обработки файла: {e}", reply_markup=get_admin_keyboard())


# --- ЗАПУСК БОТА ---
if __name__ == '__main__':
    print("Бот успешно запущен!")
    bot.infinity_polling(skip_pending=True)
