import requests
import sqlite3
from datetime import datetime
import schedule
import time

API_LIST = [
    {'name': 'Coingecko', 'url': 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd'},
    {'name': 'Coindesk', 'url': 'https://api.coindesk.com/v1/bpi/currentprice.json'},
    {'name': 'Blockchain', 'url': 'https://api.blockchain.com/v3/exchange/tickers/BTC-USD'},
    {'name': 'Kraken', 'url': 'https://api.kraken.com/0/public/Ticker?pair=XBTUSD'}
]


def fetch_bitcoin_prices():
    prices = []
    total_price = 0
    valid_prices_count = 0
    for api in API_LIST:
        try:
            response = requests.get(api['url'], timeout=3)
            if response.status_code == 200:
                response_json = response.json()
                price = None

                price = response_json.get('market_data', {}).get('current_price', {}).get('usd')
                if price is None:
                    price = response_json.get('last_price')
                if price is None:
                    price = response_json.get('last_trade_price')
                if price is None:
                    price = response_json.get('price')
                if price is None:
                    result = response_json.get('result')
                    if result is not None:
                        xxbtusd = result.get('XXBTZUSD')
                        if xxbtusd is not None:
                            price_list = xxbtusd.get('a')
                            if price_list and len(price_list) > 0:
                                price = price_list[0]
                if price is None:
                    price = response_json.get('bpi', {}).get('USD', {}).get('rate_float')
                if price is None:
                    price = response_json.get('bitcoin', {}).get('usd')

                if price is not None:
                    valid_prices_count += 1
                    total_price += float(price)
                    prices.append({'name': api['name'], 'price': round(float(price))})
                else:
                    prices.append({'name': api['name'], 'price': 'N/A'})
            else:
                prices.append({'name': api['name'], 'price': 'N/A'})
        except requests.exceptions.Timeout:
            prices.append({'name': api['name'], 'price': 'N/A'})

        except requests.exceptions.RequestException as e:
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}vОшибка соединения с API {api['name']}: {e}")
            prices.append({'name': api['name'], 'price': 'N/A'})

    if valid_prices_count > 0:
        average_price = total_price / valid_prices_count
        prices.append({'name': 'Average', 'price': round(average_price)})

    return prices


def insert_data(prices):
    conn = sqlite3.connect('bitcoin_prices.db')
    c = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for price in prices:
        c.execute('INSERT INTO bitcoin_prices (name, price, timestamp) VALUES (?, ?, ?)',
                  (price['name'], price['price'], timestamp))
    conn.commit()
    conn.close()

def job():
    prices = fetch_bitcoin_prices()
    insert_data(prices)

schedule.every(1).minutes.do(job)

if __name__ == "__main__":
    while True:
        schedule.run_pending()
        time.sleep(1)
