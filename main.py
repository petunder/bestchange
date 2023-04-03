import requests
import telebot
import threading
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
import time
from telebot import types
from telebot import apihelper
from telebot.apihelper import ApiHTTPException
from telebot.apihelper import ApiTelegramException
from user import User
from bitcoin import Bitcoin
import ntplib
from ntplib import NTPException
from datetime import datetime
import pytz
import plotly.graph_objs as go
import requests
from io import BytesIO
from PIL import Image
from pycoingecko import CoinGeckoAPI
import numpy as np
from scipy.interpolate import make_interp_spline, BSpline
import pandas as pd
from scipy.stats import linregress
from scipy.interpolate import make_interp_spline, BSpline
from scipy.interpolate import interp1d
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import linregress
# Токен вашего бота
TOKEN = ''

def create_table():
    conn = sqlite3.connect('bitcoin_prices.db')
    c = conn.cursor()
#    c.execute("DROP TABLE IF EXISTS users")
#       conn.commit()
    c.execute('''CREATE TABLE IF NOT EXISTS bitcoin_prices
                 (id INTEGER PRIMARY KEY,
                  name TEXT,
                  price REAL,
                  timestamp TEXT)''')
    conn.commit()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY,
                   name TEXT,
                   timezone TEXT,
                   night_start INTEGER,
                   night_end INTEGER,
                   receive_notifications INTEGER DEFAULT 0,
                   notification_interval INTEGER DEFAULT 60,
                   last_notification TIMESTAMP,
                   sources TEXT DEFAULT '[]')''')
    conn.commit()
    conn.close()

def get_all_user_id_with_enabled_notifications():
    with sqlite3.connect('bitcoin_prices.db') as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE receive_notifications=1")
        return [row[0] for row in c.fetchall()]

def select_data():
    conn = sqlite3.connect('bitcoin_prices.db')
    c = conn.cursor()
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)
    c.execute("SELECT avg(price) FROM bitcoin_prices WHERE timestamp >= ? AND timestamp <= ? AND price IS NOT NULL AND price != 0 AND price != 'N/A'", (hour_ago, now,))
    result = c.fetchone()
    conn.close()
    if result[0] is not None:
        return round(result[0])
    else:
        return 0

def select_24hdata():
    conn = sqlite3.connect('bitcoin_prices.db')
    c = conn.cursor()
    now = datetime.now()
    day_ago = datetime.now() - timedelta(days=1)
    c.execute("SELECT avg(price) FROM bitcoin_prices WHERE timestamp >= ? AND timestamp <= ? AND price IS NOT NULL AND price != 0 AND price != 'N/A'", (day_ago, now,))
    result = c.fetchone()
    conn.close()
    if result[0] is not None:
        return result[0]
    else:
        return 0

def update_sources(user_id, sources):
    user = User(user_id)
    user.set_sources(sources)

def get_user_sources(user_id):
    conn = sqlite3.connect('bitcoin_prices.db')
    c = conn.cursor()
    c.execute("SELECT sources FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()

    if row:
        return json.loads(row[0])
    else:
        return []


def get_bitcoin_price():
    conn = sqlite3.connect('bitcoin_prices.db')
    c = conn.cursor()

    # Получаем список всех источников из таблицы
    c.execute("SELECT DISTINCT name FROM bitcoin_prices")
    sources = [row[0] for row in c.fetchall()]

    prices = []
    for source in sources:
        # Для каждого источника получаем последние данные
        c.execute("SELECT name, price, MAX(timestamp) FROM bitcoin_prices WHERE name=?", (source,))
        row = c.fetchone()
        if row:
            prices.append({'name': row[0], 'price': row[1]})

    conn.close()
    return prices

def get_price_change():
    try:
        url = "https://api.blockchain.com/v3/exchange/tickers/BTC-USD"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = json.loads(response.text)["last_trade_price"]
            current_price = float(data)
            data = json.loads(response.text)["price_24h"]
            prev_price = float(data)
            change = round(((current_price - prev_price) / prev_price) * 100, 2)
            if change < 0:
                # emoji for a down arrow
                emoji = u"\U00002198"
            else:
                # emoji for an up arrow
                emoji = u"\U00002197"
            return f"Bitcoin price 24h change: {change}% {emoji}"
        else:
            return "Error: unable to get price data"
    except requests.exceptions.Timeout:
        return "Error: request timed out"

def create_status_keyboard(user_id, receive_notifications):
    conn = sqlite3.connect('bitcoin_prices.db')
    c = conn.cursor()
    c.execute("SELECT name, timezone, night_start, night_end, notification_interval, sources FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()

    if row:
        name, timezone, night_start, night_end, notification_interval, sources = row
        name = name if name is not None else "Не задано"
        timezone = timezone if timezone is not None else "Не задано"
        night_start = night_start if night_start is not None else "Не задано"
        night_end = night_end if night_end is not None else "Не задано"
        notification_interval = notification_interval if notification_interval is not None else "Не задано"
    else:
        name, timezone, night_start, night_end, notification_interval, sources = "Не задано", "Не задано", "Не задано", "Не задано", "Не задано", "[]"

    check_emoji = "✅"
    cross_emoji = "❌"

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(f"{check_emoji if timezone != 'Не задано' else cross_emoji} Изменить часовой пояс ({timezone})", callback_data="change_timezone"))

    subscription_status_emoji = check_emoji if receive_notifications else cross_emoji
    if receive_notifications:
        keyboard.add(types.InlineKeyboardButton(f"{subscription_status_emoji} Отменить подписку", callback_data="unsubscribe"))
    else:
        keyboard.add(types.InlineKeyboardButton(f"{subscription_status_emoji} Возобновить подписку", callback_data="subscribe"))

    keyboard.add(types.InlineKeyboardButton(f"{check_emoji if name != 'Не задано' else cross_emoji} Изменить имя ({name})", callback_data="change_name"))
    keyboard.add(types.InlineKeyboardButton(f"{check_emoji if night_start != 'Не задано' else cross_emoji} Изменить время начала уведомлений ({night_start})", callback_data="change_night_start_time"))
    keyboard.add(types.InlineKeyboardButton(f"{check_emoji if night_end != 'Не задано' else cross_emoji} Изменить время окончания уведомлений ({night_end})", callback_data="change_night_end_time"))
    keyboard.add(types.InlineKeyboardButton(f"{check_emoji if notification_interval != 'Не задано' else cross_emoji} Изменить интервал уведомлений ({notification_interval})", callback_data="change_notification_interval"))
    keyboard.add(types.InlineKeyboardButton("Выбор источника данных", callback_data="choose_sources"))

    return keyboard

def create_welcome_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Начать настройку бота", callback_data="start_setup"))
    return keyboard

def create_sources_keyboard(user_id, user_sources):
    keyboard = types.InlineKeyboardMarkup()

    conn = sqlite3.connect('bitcoin_prices.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT name FROM bitcoin_prices")
    sources = [row[0] for row in c.fetchall()]
    conn.close()

    for source_name in sources:
        status = "Вкл" if source_name in user_sources else "Откл"
        keyboard.add(types.InlineKeyboardButton(f"{source_name} ({status})", callback_data=f"toggle_source_{source_name}"))

#    keyboard.add(types.InlineKeyboardButton("Средняя цена за час", callback_data="average_price_1h"))
#    keyboard.add(types.InlineKeyboardButton("Средняя цена за 24 часа", callback_data="average_price_24h"))
    keyboard.add(types.InlineKeyboardButton("Назад", callback_data="go_back"))  # Изменено

    return keyboard

def keyboard_equals(a, b):
    if len(a.keyboard) != len(b.keyboard):
        return False

    for i in range(len(a.keyboard)):
        if len(a.keyboard[i]) != len(b.keyboard[i]):
            return False

        for j in range(len(a.keyboard[i])):
            if a.keyboard[i][j].text != b.keyboard[i][j].text or a.keyboard[i][j].callback_data != b.keyboard[i][j].callback_data:
                return False

    return True

def get_receive_notifications(user_id):
    conn = sqlite3.connect('bitcoin_prices.db')
    c = conn.cursor()
    c.execute("SELECT receive_notifications FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()

    if row:
        return row[0]
    else:
        return 0

def update_receive_notifications(user_id, status):
    with sqlite3.connect('bitcoin_prices.db') as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET receive_notifications=? WHERE user_id=?", (status, user_id))
        conn.commit()

def create_timezone_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=3)

    timezone_buttons = []
    for i in range(-12, 15):
        timezone = f"UTC{'+' if i >= 0 else ''}{i}"
        timezone_buttons.append(types.InlineKeyboardButton(text=timezone, callback_data=f"set_timezone_{i}"))

    keyboard.add(*timezone_buttons)
    return keyboard

def update_timezone(user_id, timezone):
    with sqlite3.connect('bitcoin_prices.db') as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET timezone=? WHERE user_id=?", (timezone, user_id))
        conn.commit()

def get_local_notification_interval(user_id):
    """Return the notification interval in the user's local timezone."""
    with sqlite3.connect('bitcoin_prices.db') as conn:
        c = conn.cursor()
        c.execute("SELECT timezone, night_start, night_end, notification_interval FROM users WHERE user_id=?", (user_id,))
        user = c.fetchone()

    if not user:
        return "Пользователь не найден"

    timezone, night_start, night_end, notification_interval = user

    if night_start is None or night_end is None:
        return "Настройки времени не заданы"

    utc_offset = get_utc_offset(timezone)
    utc_time = get_utc_time()
    utc_now = utc_time.replace(tzinfo=None)
    local_now = utc_now + timedelta(hours=utc_offset)
    local_start = local_now.replace(hour=night_start, minute=0, second=0, microsecond=0)
    local_end = local_now.replace(hour=night_end, minute=0, second=0, microsecond=0)

    # Проверяем, приходят ли уведомления в текущее время
    if night_start < night_end:
        notifications_status = "приходят" if night_start <= local_now.hour < night_end else "не приходят"
    else:  # Если время начала уведомлений больше времени окончания, значит период уведомлений пересекает полночь
        notifications_status = "приходят" if not (night_end <= local_now.hour < night_start) else "не приходят"

    return f"Уведомления будут приходить каждые {notification_interval} минут с {local_start.time().strftime('%H:%M')} до {local_end.time().strftime('%H:%M')} по вашему времени. Сейчас у вас {local_now.time().strftime('%H:%M')} (UTC {utc_now.time().strftime('%H:%M')}, временная зона {utc_offset}). Уведомления {notifications_status}."

def update_night_start_time(message, night_start_time):
    user_id = message.chat.id
    with sqlite3.connect('bitcoin_prices.db') as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET night_start=? WHERE user_id=?", (night_start_time, user_id))
        conn.commit()

    bot.reply_to(message, f"Время начала уведомлений изменено на {night_start_time}:00")

def update_night_end_time(message, night_end_time):
    user_id = message.chat.id
    with sqlite3.connect('bitcoin_prices.db') as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET night_end=? WHERE user_id=?", (night_end_time, user_id))
        conn.commit()

    bot.reply_to(message, f"Время окончания уведомлений изменено на {night_end_time}:00")

def set_notification_interval(message):
    user_id = message.chat.id
    try:
        interval = int(message.text)
        if 1 <= interval <= 1440:
            with sqlite3.connect('bitcoin_prices.db') as conn:
                c = conn.cursor()
                c.execute("UPDATE users SET notification_interval=? WHERE user_id=?", (interval, user_id))
                conn.commit()
            bot.send_message(user_id, f"Интервал уведомлений изменен на {interval} минут.")
        else:
            bot.send_message(user_id, "Пожалуйста, введите число от 1 до 1440.")
            sent_message = bot.send_message(user_id, "Введите желаемый интервал уведомлений в минутах (например, 30):")
            bot.register_next_step_handler(sent_message, set_notification_interval)
    except ValueError:
        bot.send_message(user_id, "Пожалуйста, введите число от 1 до 1440.")
        sent_message = bot.send_message(user_id, "Введите желаемый интервал уведомлений в минутах (например, 30):")
        bot.register_next_step_handler(sent_message, set_notification_interval)

# обработчик ошибок TelegramError
def handle_telegram_error(exception):
    # если возникла ошибка HTTP 431, то вывести сообщение и вернуть True,
    # чтобы бот продолжил работу, игнорируя эту ошибку
    if isinstance(exception, apihelper.ApiTelegramException) and exception.result.status_code == 431:
        print('HTTP 431 Request Header Fields Too Large')
        return True
    # иначе вернуть False, чтобы обработать остальные ошибки
    else:
        return False

# Инициализация бота
bot = telebot.TeleBot(TOKEN)
bot.set_update_listener(handle_telegram_error)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    welcome_text = ("Этот бот умеет показывать цену биткойна из разных источников. "
                    "Вы можете настроить бот по своему желанию, включать и отключать источники данных, "
                    "а также подписаться на периодическую рассылку уведомлений о цене BTC/USD.")
    bot.send_message(user_id, welcome_text, reply_markup=create_welcome_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "start_setup")
def start_setup(call):
    subscribe_user(call.message)
    # Отправьте пользователю сообщение об успешной подписке или откройте меню настроек

@bot.callback_query_handler(func=lambda call: call.data == "change_night_start_time")
def change_night_start_time_handler(call):
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    sent_message = bot.send_message(user_id, "Введите новое время начала уведомлений (в формате 0-23):")
    bot.register_next_step_handler(sent_message, lambda message: update_night_start_time(message, int(message.text)))

@bot.callback_query_handler(func=lambda call: call.data == "change_night_end_time")
def change_night_end_time_handler(call):
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    sent_message = bot.send_message(user_id, "Введите новое время окончания уведомлений (в формате 0-23):")
    bot.register_next_step_handler(sent_message, lambda message: update_night_end_time(message, int(message.text)))

@bot.callback_query_handler(func=lambda call: call.data == "subscribe_new_user")
def callback_subscribe_new_user(call):
    subscribe_user(call.message)

@bot.message_handler(commands=['getpush'])
def subscribe_user(message):
    user_id = message.chat.id
    with sqlite3.connect('bitcoin_prices.db') as conn:
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
            bot.reply_to(message, 'Подписка оформлена! Но уведомления не активированы. Активируйте их в меню Status. Если вы не активируете уведомления, то они не будут вам поступать.')
        except sqlite3.IntegrityError:
            bot.reply_to(message, 'Вы уже подписаны.')

        # Request user's timezone using inline keyboard
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(f"UTC{i:+d}", callback_data=f"tz_{i}") for i in range(-12, 15)]
        markup.add(*buttons)

        # Add "Continue bot setup" button
        continue_setup_button = types.InlineKeyboardButton("Продолжить настройку бота", callback_data="continue_setup")
        markup.add(continue_setup_button)

        bot.send_message(user_id, "Выберите свой часовой пояс:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'continue_setup')
def continue_setup(call):
    bot.answer_callback_query(call.id)
    status(call.message)

def update_name(message, original_message):
    user_id = message.chat.id
    new_name = message.text

    with sqlite3.connect('bitcoin_prices.db') as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET name=? WHERE user_id=?", (new_name, user_id))
        conn.commit()

    bot.reply_to(original_message, f"Имя успешно изменено на {new_name}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_source_"))
def toggle_source(call):
    user_id = call.message.chat.id
    user = User(user_id)

    source_name = call.data[len("toggle_source_"):]

    user_sources = get_user_sources(user_id)
    if source_name in user_sources:
        user_sources.remove(source_name)
    else:
        user_sources.append(source_name)

    user.set_sources(user_sources)

    new_keyboard = create_sources_keyboard(user_id, user_sources)

    if not keyboard_equals(call.message.reply_markup, new_keyboard):
        bot.edit_message_text("Выберите источники данных для периодической рассылки (для разовых запросов курса эта настройка не работает):", user_id, call.message.message_id, reply_markup=new_keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "go_back")
def go_back(call):
    user_id = call.message.chat.id  # Изменено
    receive_notifications = get_receive_notifications(user_id)
    bot.edit_message_text("Статус", user_id, call.message.message_id, reply_markup=create_status_keyboard(user_id, receive_notifications))

@bot.callback_query_handler(func=lambda call: call.data == "choose_sources")
def choose_sources(call):
    user_id = call.message.chat.id
    user_sources = get_user_sources(user_id)
    keyboard = create_sources_keyboard(user_id, user_sources)
    bot.edit_message_text("Выберите источники данных для периодической рассылки (для разовых запросов курса эта настройка не работает):", user_id, call.message.message_id, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('tz_'))
def process_timezone(call):
    user_id = call.message.chat.id
    timezone = int(call.data[3:])
    with sqlite3.connect('bitcoin_prices.db') as conn:
        c = conn.cursor()
        c.execute('UPDATE users SET timezone = ? WHERE user_id = ?', (timezone, user_id))
        conn.commit()
    bot.answer_callback_query(call.id, f"Часовой пояс установлен на UTC{timezone:+d}")


@bot.message_handler(commands=['startpush'])
def start_push_notifications(message):
    user_id = message.chat.id
    with sqlite3.connect('bitcoin_prices.db') as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET receive_notifications = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    bot.reply_to(message, "Вы подписались на уведомления.")

def correct_timezone_format(tz):
    if tz:
        if not tz.startswith("Etc/GMT"):
            try:
                offset = int(tz)
                sign = '-' if offset > 0 else '+'
                return f"Etc/GMT{sign}{abs(offset)}"
            except ValueError:
                pass
    return tz


def get_utc_time():
    ntp_client = ntplib.NTPClient()
    try:
        response = ntp_client.request('europe.pool.ntp.org')
        ntp_time = datetime.fromtimestamp(response.tx_time, pytz.UTC)
        return ntp_time
    except NTPException as e:
        print(f"Ошибка: {e}")
        # Вернуть текущее время системы в UTC
        return datetime.utcnow().replace(tzinfo=pytz.UTC)

def get_utc_offset(timezone):
    try:
        offset = int(timezone)
        return timedelta(hours=offset)
    except ValueError:
        sign, hours, minutes = re.findall(r'([\+\-])(\d{1,2}):?(\d{2})?', correct_timezone_format(timezone))[0]
        hours = int(hours) if hours else 0
        minutes = int(minutes) if minutes else 0
        total_minutes = hours * 60 + minutes
        return timedelta(minutes=(total_minutes if sign == '+' else -total_minutes))



def generate_chart(prices_list):
    x = [i for i in range(len(prices_list))]
    y = prices_list
    num_segments = 5
    segment_len = len(x) // num_segments

    # plot original data
    fig = go.Figure(data=go.Scatter(x=x, y=y))

    # add EMA(90)
    ema_90 = pd.Series(y).ewm(span=90, adjust=False).mean()
    fig.add_trace(go.Scatter(x=x, y=ema_90, name='EMA(90)'))

    # add EMA(200)
    ema_200 = pd.Series(y).ewm(span=200, adjust=False).mean()
    fig.add_trace(go.Scatter(x=x, y=ema_200, name='EMA(200)'))

    # add linear interpolation for each segment
    for i in range(num_segments):
        x_seg = x[i * segment_len:(i + 1) * segment_len]
        y_seg = y[i * segment_len:(i + 1) * segment_len]
        slope, intercept, _, _, _ = linregress(x_seg, y_seg)
        y_pred = intercept + slope * np.array(x_seg)
        a_value = round(slope, 2)
        fig.add_trace(
            go.Scatter(x=x_seg, y=y_pred, name=f'a={a_value}', line=dict(color='orange', width=3)))

    fig.update_layout(
        xaxis_title='90 Day chart',
        yaxis_title='Price in USD',
        font=dict(
            family="Courier New, monospace",
            size=18,
            color="#7f7f7f"
        ),
        xaxis=dict(
            showticklabels=False
        )
    )

    img_bytes = fig.to_image(format='png')
    return img_bytes


def update_bitcoin_chart():
    while True:
        try:
            # создаем объект CoinGeckoAPI
            cg = CoinGeckoAPI()

            # получаем данные о курсе биткойна
            bitcoin_data = cg.get_coin_market_chart_by_id(id='bitcoin', vs_currency='usd', days=90)

            # получаем данные о ценах закрытия на каждый день
            bitcoin_prices = bitcoin_data['prices']

            # получаем список цен закрытия за последние 7 дней
            prices_list = [price[1] for price in bitcoin_prices]

            # генерируем график и сохраняем его локально на сервере
            img_bytes = generate_chart(prices_list)
            with open("bitcoin_chart.png", "wb") as f:
                f.write(img_bytes)
            print(f"График биткойна обновлен")
            # отправляем ответ с фото
            # bot.send_photo(chat_id, photo=open("bitcoin_chart.png", "rb"))

            time.sleep(3600)  # ждем 60 секунд перед следующим обновлением

        except (requests.exceptions.RequestException, KeyError) as e:
            print(f"Ошибка: {e}. Повторная попытка через 30 секунд.")
            time.sleep(30)
            continue

def send_notifications():
    while True:
        try:
            users = [218710953]
            print(f"Количество чатов в рассылке: {len(users)}")

            for user in users:
                user=User(user)
                sources=user.sources
                if user.receive_notifications != 1:
                    continue
                if user.timezone is None:
                    user.set_timezone(0)
                    pass

                if not user.check_user_notification_status():
                    continue
                else:
                    btc=Bitcoin()
                    print(btc.get_bitcoin_price_sources())
                    prices = btc.select_prices_by_sources(json.loads(sources))
                    print(f"{prices}")
                    change = btc.get_price_change()
    #                average_price = round(select_data())
    #                average_24hprice = round(select_24hdata())
                    message_text = f'Привет, {user.name}!\n\n'
                    for price in prices:
                        message_text += f'{price["name"]}: {price["price"] if price["price"] != "N/A" else "N/A"} USD\n'
                    message_text += change + '\n\n'
                    message_text += f'Average 1h price: {btc.average_1h()} USD\n'
                    message_text += f'Average 24h price: {btc.average_24h()} USD\n'
                    message_text += f'\n<i>Вы получили это сообщение потому что подписаны на периодические обновления. Интервал обновления {user.notification_interval} минут, ваше локальное время {user.local_time().strftime("%H:%M")}, начало уведомлений в {user.night_start}:00, окончание уведомлений в {user.night_end}:00.</i>'

                    try:
#                        bot.send_message(user.user_id, message_text, parse_mode='HTML')
                        bot.send_photo(chat_id=user.user_id, photo=open('bitcoin_chart.png', 'rb'), caption=message_text, parse_mode='HTML')
                    except ApiTelegramException as e:
                        print(f"Ошибка при отправке сообщения пользователю {user.user_id}: {e}")
                        print(f"{message_text}")
                        continue

                    next_message_time = datetime.now() + timedelta(minutes=user.notification_interval)
                    print(f"Следующее сообщение пользователю {user.user_id} будет отправлено в {next_message_time}")
                    user.set_last_notification(datetime.now())
            pass
        except Exception as e:
            print(f"Ошибка в обработке уведомлений: {e}")
        time.sleep(60)

@bot.message_handler(commands=['status'])
def status(message):
    user_id = message.chat.id
    print(f"Пользователь {user_id} запросил изменение настроек")
    try:
        user = User(user_id)
    except ValueError:
        not_subscribed_keyboard = types.InlineKeyboardMarkup()
        not_subscribed_keyboard.add(
            types.InlineKeyboardButton("Подписаться на обновления", callback_data="subscribe_new_user"))
        bot.send_message(user_id, "Вы не подписаны.", reply_markup=not_subscribed_keyboard)
        return

    status_text = f"Привет, {user.name}!\n"
    status_text += f"Статус подписки: {'Активна' if user.receive_notifications else 'Не активна'}\n"
    timezone_int = int(user.timezone)
    status_text += f"Часовой пояс: {('+' if timezone_int >= 0 else '')}{timezone_int}\n"
#    local_interval = get_local_notification_interval(user_id)
#    if local_interval:
#        status_text += str(local_interval)
#    else:
#        status_text += "Ошибка: не удалось вычислить временной интервал для уведомлений"
    bot.send_message(user.user_id, status_text, reply_markup=create_status_keyboard(user_id, user.receive_notifications))


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.message.chat.id
    if call.data == "change_timezone":
        bot.edit_message_text("Выберите новый часовой пояс:", user_id, call.message.message_id, reply_markup=create_timezone_keyboard())
    elif call.data.startswith("set_timezone_"):
        new_timezone_offset = int(call.data.split("_")[-1])
        new_timezone = f"UTC{'+' if new_timezone_offset >= 0 else ''}{new_timezone_offset}"
        update_timezone(user_id, new_timezone)
        bot.answer_callback_query(call.id, f"Часовой пояс изменен на {new_timezone}")
    elif call.data == "unsubscribe":
        update_receive_notifications(user_id, 0)
        bot.answer_callback_query(call.id, "Подписка отменена")
        bot.edit_message_reply_markup(user_id, call.message.message_id, reply_markup=create_status_keyboard(user_id, 0))
    elif call.data == "subscribe":
        update_receive_notifications(user_id, 1)
        bot.answer_callback_query(call.id, "Подписка возобновлена")
        bot.edit_message_reply_markup(user_id, call.message.message_id, reply_markup=create_status_keyboard(user_id, 1))
    elif call.data == "change_name":
        bot.answer_callback_query(call.id)
        sent_message = bot.send_message(user_id, "Введите новое имя:")
        bot.register_next_step_handler(sent_message, lambda message: update_name(message, call.message))
    elif call.data == "change_notification_interval":
        bot.answer_callback_query(call.id)
        sent_message = bot.send_message(user_id, "Введите желаемый интервал уведомлений в минутах (например, 30):")
        bot.register_next_step_handler(sent_message, lambda message: set_notification_interval(message))

# Обработка команды /getprice
@bot.message_handler(commands=['getprice'])
def get_price(message):
    print(f"Начало выполнения функции getprice")
    btc = Bitcoin()
    print(f"Инициализация объекта")
    prices = btc.get_latest_bitcoin_prices()
    print(f"get prices: {prices}")
    message_text = ''
    for price in prices:
        message_text += f'{price["name"]}: {price["price"] if price != "N/A" else "N/A"} USD\n'
    message_text += '\n'
    message_text += f'Average 1h price: {btc.average_1h()} USD\n'
    message_text += f'Average 24h price: {btc.average_24h()} USD\n'

    print(f"Вот текст сообщения: {message_text}")

    try:
        bot.reply_to(message, message_text or 'Failed to get the price')
    except ApiHTTPException as e:
        #error_message = f"Ошибка при отправке сообщения. Попробуйте позже. Текст ошибки: {e}"
        # bot.send_message(message.chat.id, error_message)
        print(f"Ошибка: {e}. Сообщение не отправлено пользователю {message.chat.id}.")

@bot.callback_query_handler(func=lambda call: call.data == "change_name")
def change_name_handler(call):
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    sent_message = bot.send_message(user_id, "Введите новое имя:")
    bot.register_next_step_handler(sent_message, lambda message: update_name(message, call.message))


def polling():
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except telebot.apihelper.ApiException as e:
            print(f"Ошибка: {e}. Перезапуск через 15 секунд.")
            time.sleep(15)

if __name__ == "__main__":
    create_table()
    threading.Thread(target=send_notifications).start()
    threading.Thread(target=update_bitcoin_chart).start()  # запускаем отдельный поток для обновления графика
    threading.Thread(target=polling).start()
