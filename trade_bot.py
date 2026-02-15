import yfinance as yf
import pandas as pd
import ta
import asyncio
from telegram import Bot
import schedule
import time
from datetime import datetime
import os

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


bot = Bot(token=TOKEN)

# TEST MESSAGE
import asyncio

async def test_message():
    await bot.send_message(chat_id=CHAT_ID, text="Bot is alive and running 🚀")

asyncio.run(test_message())

sent_signals = set()

# ------------------------
# MARKET HOURS FILTER
# ------------------------

def market_open():
    now = datetime.now()
    return now.weekday() < 5 and 9 <= now.hour < 15


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

schedule.every(15).minutes.do(run_bot)

print("🔥 TESTING BOT RUNNING...")

while True:
    schedule.run_pending()
    time.sleep(1)


