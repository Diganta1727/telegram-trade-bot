import yfinance as yf
import pandas as pd
import ta
import asyncio
from telegram import Bot
from datetime import datetime, timedelta
import os
from flask import Flask
import threading
import time

# ------------------------
# TELEGRAM CONFIG
# ------------------------
TOKEN = os.getenv("BOT_TOKEN")
USER_CHAT_ID = os.getenv("USER_CHAT_ID")   # Your personal chat id
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID") # Your group chat id

bot = Bot(token=TOKEN)

sent_signals = {}  # store last sent time for each symbol


# ------------------------
# MARKET HOURS FILTER
# ------------------------
def market_open():
    try:
        india_time = datetime.utcnow() + timedelta(hours=5, minutes=30)

        is_weekday = india_time.weekday() < 5

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
    try:
        data = yf.download(symbol, period="1mo", interval="15m", auto_adjust=True)

        if data is None or len(data) < 100:
            return None

        # Fix MultiIndex columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        # Convert to 1D series
        close = data["Close"].squeeze()
        high = data["High"].squeeze()
        low = data["Low"].squeeze()
        volume = data["Volume"].squeeze()

        data["ema20"] = ta.trend.ema_indicator(close, window=20)
        data["ema50"] = ta.trend.ema_indicator(close, window=50)
        data["rsi"] = ta.momentum.rsi(close, window=14)
        data["adx"] = ta.trend.adx(high, low, close, window=14)
        data["volume_avg"] = volume.rolling(20).mean()
        data["atr"] = ta.volatility.average_true_range(high, low, close, window=14)

        latest = data.iloc[-1]

        volume_breakout = latest["Volume"] > 1.5 * latest["volume_avg"]
        strong_trend = latest["adx"] > 25

        price = latest["Close"]
        strike = round(price / 50) * 50

        # BUY SIGNAL
        if (latest["ema20"] > latest["ema50"] and
            latest["rsi"] > 55 and
            strong_trend and
            volume_breakout):

            sl = price - latest["atr"]
            target = price + (2 * latest["atr"])

            return f"""🔥 BUY SIGNAL
Symbol: {symbol}
Entry: {price:.2f}
SL: {sl:.2f}
Target: {target:.2f}

⚡ Option: {strike} CE
Trend: Strong
"""

        # SELL SIGNAL
        if (latest["ema20"] < latest["ema50"] and
            latest["rsi"] < 45 and
            strong_trend and
            volume_breakout):

            sl = price + latest["atr"]
            target = price - (2 * latest["atr"])

            return f"""🔥 SELL SIGNAL
Symbol: {symbol}
Entry: {price:.2f}
SL: {sl:.2f}
Target: {target:.2f}

⚡ Option: {strike} PE
Trend: Strong
"""

        return None

    except Exception as e:
        print("Strategy error:", symbol, e)
        return None


# ------------------------
# TELEGRAM MESSAGE
# ------------------------
async def send_message(message):
    try:
        await bot.send_message(chat_id=USER_CHAT_ID, text=message)
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=message)
        print("Message sent successfully!")

    except Exception as e:
        print("Telegram error:", e)


# ------------------------
# SCAN MARKET
# ------------------------
async def scan_market():
    if not market_open():
        print("Market closed, skipping scan...")
        return

    print("Scanning market now...")

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

        if signal:
            now = datetime.utcnow()

            # Avoid spamming same symbol again within 1 hour
            if symbol in sent_signals:
                last_time = sent_signals[symbol]
                if (now - last_time).seconds < 3600:
                    continue

            await send_message(signal)

            # ✅ store only when message is sent
            sent_signals[symbol] = now


# ------------------------
# MAIN LOOP (NO SCHEDULE LIBRARY)
# ------------------------
def bot_loop():
    while True:
        try:
            asyncio.run(scan_market())
        except Exception as e:
            print("Bot loop error:", e)

        print("Bot alive heartbeat...")
        time.sleep(900)  # 900 sec = 15 minutes


# ------------------------
# FLASK APP (KEEP RAILWAY ALIVE)
# ------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Trading Bot Running 🚀"


if __name__ == "__main__":
    thread = threading.Thread(target=bot_loop, daemon=True)
    thread.start()

    app.run(host="0.0.0.0", port=8000)

