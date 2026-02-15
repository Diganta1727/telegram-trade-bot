import yfinance as yf
import pandas as pd
import ta
import asyncio
from telegram import Bot
import schedule
import time
from datetime import datetime
from datetime import datetime, timedelta
import os
from flask import Flask
import threading


TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


bot = Bot(token=TOKEN)

sent_signals = set()

# ------------------------
# MARKET HOURS FILTER
# ------------------------

def market_open():
    try:
        # Convert UTC to IST (+5:30)
        india_time = datetime.utcnow() + timedelta(hours=5, minutes=30)

        # Monday–Friday
        is_weekday = india_time.weekday() < 5

        # Between 9:15 AM and 3:30 PM
        is_market_hours = (
            (india_time.hour > 9 or (india_time.hour == 9 and india_time.minute >= 15)) and
            (india_time.hour < 15 or (india_time.hour == 15 and india_time.minute <= 30))
        )

        return is_weekday and is_market_hours

    except Exception as e:
        print("Market time error:", e)
        return False



# ------------------------
# ADVANCED STRATEGY
# ------------------------

def advanced_signal(symbol):
    data = yf.download(symbol, period="1mo", interval="15m")

    if len(data) < 100:
        return None

    data['ema20'] = ta.trend.ema_indicator(data['Close'], window=20)
    data['ema50'] = ta.trend.ema_indicator(data['Close'], window=50)
    data['rsi'] = ta.momentum.rsi(data['Close'], window=14)
    data['adx'] = ta.trend.adx(data['High'], data['Low'], data['Close'], window=14)
    data['volume_avg'] = data['Volume'].rolling(20).mean()
    data['atr'] = ta.volatility.average_true_range(data['High'], data['Low'], data['Close'], window=14)

    latest = data.iloc[-1]

    volume_breakout = latest['Volume'] > 1.5 * latest['volume_avg']
    strong_trend = latest['adx'] > 25

    price = latest['Close']
    strike = round(price / 50) * 50

    # Bullish Setup
    if (latest['ema20'] > latest['ema50'] and
        latest['rsi'] > 55 and
        strong_trend and
        volume_breakout):

        sl = price - latest['atr']
        target = price + (2 * latest['atr'])

        return f"""🔥 BUY SIGNAL
Symbol: {symbol}
Entry: {price:.2f}
SL: {sl:.2f}
Target: {target:.2f}

⚡ Option: {strike} CE
Trend: Strong
"""

    # Bearish Setup
    if (latest['ema20'] < latest['ema50'] and
        latest['rsi'] < 45 and
        strong_trend and
        volume_breakout):

        sl = price + latest['atr']
        target = price - (2 * latest['atr'])

        return f"""🔥 SELL SIGNAL
Symbol: {symbol}
Entry: {price:.2f}
SL: {sl:.2f}
Target: {target:.2f}

⚡ Option: {strike} PE
Trend: Strong
"""

    return None


# ------------------------
# TELEGRAM
# ------------------------

async def send_message(message):
    await bot.send_message(chat_id=CHAT_ID, text=message)


# ------------------------
# SCAN MARKET
# ------------------------

async def scan_market():
    if not market_open():
        return

    symbols = [
        "^NSEI",
        "^NSEBANK",
        "RELIANCE.NS",
        "TCS.NS",
        "HDFCBANK.NS",
        "ICICIBANK.NS",
        "INFY.NS"
    ]

    for symbol in symbols:
        signal = advanced_signal(symbol)

        if signal and symbol not in sent_signals:
            await send_message(signal)
            sent_signals.add(symbol)


# ------------------------
# RUN LOOP
# ------------------------

def run_bot():
    asyncio.run(scan_market())

app = Flask(__name__)

@app.route("/")
def home():
    return "Trading Bot Running 🚀"

def start_scheduler():
    schedule.every(15).minutes.do(run_bot)

    while True:
        print("Bot alive heartbeat...")
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # Run scheduler in background thread
    thread = threading.Thread(target=start_scheduler)
    thread.start()

    # Run Flask server (Keeps Railway alive)
    app.run(host="0.0.0.0", port=8000)







