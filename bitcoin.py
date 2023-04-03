import sqlite3
from datetime import datetime, timedelta, timezone
import requests
import json

class Bitcoin:
    def __init__(self, id=None, name=None, price=None, timestamp=None):
        self.id = id
        self.name = name
        self.price = price
        self.timestamp = timestamp
        self.get_bitcoin_price_sources()

    def set_name(self, name):
        self.name = name

    def set_price(self, price):
        self.price = price

    def set_timestamp(self, timestamp):
        self.timestamp = timestamp

    def save_to_database(self):
        conn = sqlite3.connect('bitcoin_prices.db')
        c = conn.cursor()

        if self.id is None:
            # Если id не задан, создаем новую запись
            c.execute("INSERT INTO bitcoin_prices (name, price, timestamp) VALUES (?, ?, ?)",
                      (self.name, self.price, self.timestamp))
            self.id = c.lastrowid
        else:
            # Если id задан, обновляем существующую запись
            c.execute("UPDATE bitcoin_prices SET name=?, price=?, timestamp=? WHERE id=?",
                      (self.name, self.price, self.timestamp, self.id))

        conn.commit()
        conn.close()

    @classmethod
    def get_bitcoin_by_id(cls, id):
        conn = sqlite3.connect('bitcoin_prices.db')
        c = conn.cursor()
        c.execute("SELECT * FROM bitcoin_prices WHERE id=?", (id,))
        row = c.fetchone()
        conn.close()

        if row is not None:
            return cls(id=row[0], name=row[1], price=row[2], timestamp=row[3])
        else:
            return None

    def get_bitcoin_price_sources(self):
        conn = sqlite3.connect('bitcoin_prices.db')
        c = conn.cursor()
        c.execute("SELECT DISTINCT name FROM bitcoin_prices")
        all_sources = [row[0] for row in c.fetchall()]
        conn.close()
        return all_sources


    @staticmethod
    def average_1h():
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

    @staticmethod
    def average_24h():
        conn = sqlite3.connect('bitcoin_prices.db')
        c = conn.cursor()
        now = datetime.now()
        day_ago = datetime.now() - timedelta(days=1)
        c.execute("SELECT avg(price) FROM bitcoin_prices WHERE timestamp >= ? AND timestamp <= ? AND price IS NOT NULL AND price != 0 AND price != 'N/A'", (day_ago, now,))
        result = c.fetchone()
        conn.close()
        if result[0] is not None:
            return round(result[0])
        else:
            return 0

    @staticmethod
    def select_prices_by_sources(source_names):
        if isinstance(source_names, str):
            source_names = [source_names]

        conn = sqlite3.connect('bitcoin_prices.db')
        c = conn.cursor()
        results = []
        for source_name in source_names:
            c.execute(
                "SELECT price, timestamp FROM bitcoin_prices WHERE name=? AND price IS NOT NULL AND price != 0 AND price != 'N/A' ORDER BY timestamp DESC LIMIT 1",
                (source_name,))
            result = c.fetchone()
            if result is not None:
                results.append({'name': source_name, 'price': result[0], 'timestamp': result[1]})
            else:
                results.append({'name': source_name, 'price': None, 'timestamp': None})
        conn.close()
        return results

    @staticmethod
    def get_latest_bitcoin_prices():
        print("Connecting to the database...")
        conn = sqlite3.connect('bitcoin_prices.db')
        c = conn.cursor()

        print("Getting the list of sources...")
        c.execute("SELECT DISTINCT name FROM bitcoin_prices WHERE name != 'Average'")
        sources = [row[0] for row in c.fetchall()]

        print("Fetching the latest prices for each source...")
        latest_prices = []
        for source in sources:
            if source != "Average":
                c.execute(
                    "SELECT price, timestamp FROM bitcoin_prices WHERE name=? AND price IS NOT NULL AND price != 0 AND price != 'N/A' ORDER BY timestamp DESC LIMIT 1",
                    (source,)
                )
                result = c.fetchone()
                if result is not None:
                    latest_prices.append({'name': source, 'price': result[0], 'timestamp': result[1]})

        conn.close()

        print("Returning the latest prices...")
        return latest_prices

    @staticmethod
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
                return f"<b>Bitcoin price 24h change:</b> {change}% {emoji} ({format(current_price - prev_price, '+.2f')})"
            else:
                return "Error: unable to get price data"
        except requests.exceptions.Timeout:
            return "Error: request timed out"
