import sqlite3
from datetime import datetime, timedelta, timezone
import json

class User:
    def __init__(self, user_id):
        self.user_id = user_id
        self.name = None
        self.timezone = None
        self.night_start = None
        self.night_end = None
        self.receive_notifications = None
        self.notification_interval = None
        self.last_notification = None
        self.sources = None
        self._get_user_data()

    def _get_user_data(self):
        conn = sqlite3.connect('bitcoin_prices.db')
        c = conn.cursor()
        c.execute(
            "SELECT name, timezone, night_start, night_end, receive_notifications, notification_interval, last_notification, sources FROM users WHERE user_id=?", (self.user_id,))
        user_data = c.fetchone()
        conn.close()
        if user_data is not None:
            self.name, self.timezone, self.night_start, self.night_end, self.receive_notifications, self.notification_interval, self.last_notification, self.sources = user_data
        else:
            raise ValueError(f"User with ID {self.user_id} not found in database")

    def set_name(self, name):
        self.name = name
        with sqlite3.connect('bitcoin_prices.db') as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET name=? WHERE user_id=?", (name, self.user_id))

    def set_timezone(self, timezone):
        self.timezone = timezone
        with sqlite3.connect('bitcoin_prices.db') as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET timezone=? WHERE user_id=?", (timezone, self.user_id))

    def set_night_start(self, night_start):
        self.night_start = night_start
        with sqlite3.connect('bitcoin_prices.db') as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET night_start=? WHERE user_id=?", (night_start, self.user_id))

    def set_night_end(self, night_end):
        self.night_end = night_end
        with sqlite3.connect('bitcoin_prices.db') as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET night_end=? WHERE user_id=?", (night_end, self.user_id))

    def set_receive_notifications(self, receive_notifications):
        self.receive_notifications = receive_notifications
        with sqlite3.connect('bitcoin_prices.db') as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET receive_notifications=? WHERE user_id=?", (receive_notifications, self.user_id))

    def set_notification_interval(self, notification_interval):
        self.notification_interval = notification_interval
        with sqlite3.connect('bitcoin_prices.db') as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET notification_interval=? WHERE user_id=?", (notification_interval, self.user_id))

    def set_last_notification(self, last_notification):
        self.last_notification = last_notification
        with sqlite3.connect('bitcoin_prices.db') as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET last_notification=? WHERE user_id=?", (last_notification, self.user_id))

    def set_sources(self, sources):
        self.sources = sources
        with sqlite3.connect('bitcoin_prices.db') as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET sources=? WHERE user_id=?", (json.dumps(sources), self.user_id))

    def check_user_notification_status(self):
        #utc_time = datetime.now(timezone.utc)
        # Создание объекта timezone для указанного часового пояса
        #tz = timezone(timedelta(hours=int(self.timezone)))
        # Применение часового пояса к объекту datetime
        #local_time = utc_time.astimezone(tz)

#        local_time = get_user_local_time2(int(self.timezone))
        current_hour = self.local_time().hour

        if self.night_start is not None and self.night_end is not None:
            if (current_hour >= self.night_end) or (current_hour < self.night_start):
                print(f"Действует ночной интервал, уведомления не отправляются")
                return False

        if self.last_notification is not None:
            date_obj = datetime.strptime(self.last_notification, '%Y-%m-%d %H:%M:%S.%f')
            # Создание объекта timezone для указанного часового пояса
            tz = timezone(timedelta(hours=int(self.timezone)))
            # Применение часового пояса к объекту datetime
            date_obj_with_timezone = date_obj.replace(tzinfo=tz)

            print(
                f"5.1 Последнее уведомление было в {date_obj_with_timezone}")
            print(f"5.2 Интервал уведомлений установлен в {self.notification_interval} минут")
            last_notification_time = datetime.fromisoformat(self.last_notification)
            print(f"5.3 {last_notification_time}")
            local_last_notification_dif = self.local_time() - datetime.strptime(self.last_notification, '%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=tz)
            print(f"5.4 разница во времени между уведомлениями: {local_last_notification_dif}")
            local_last_notification_dif_minutes = int(local_last_notification_dif.total_seconds() // 60)
            print(f"5.5 разница в минутах между уведомлениями: {local_last_notification_dif_minutes}")
            if local_last_notification_dif_minutes < self.notification_interval:
                print(
                    f"уведомления не отправляются, интервал еще не достигнут: {local_last_notification_dif_minutes} < {self.notification_interval}")
                return False

        return True

    def local_time(self):
        utc_time = datetime.now(timezone.utc)
        # Создание объекта timezone для указанного часового пояса
        tz = timezone(timedelta(hours=int(self.timezone)))
        # Применение часового пояса к объекту datetime
        local_time = utc_time.astimezone(tz)
        return local_time

