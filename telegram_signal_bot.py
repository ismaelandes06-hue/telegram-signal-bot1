from flask import Flask, request, jsonify
import os
import requests
import time
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')

app = Flask(__name__)

RECENT_ALERTS = {}
DEDUP_WINDOW_SECONDS = 6

def dedupe_key(payload: dict):
    return f"{payload.get('symbol')}|{payload.get('action')}|{payload.get('timeframe')}"

def send_telegram_message(text: str):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {'chat_id': TELEGRAM_CHAT_ID,'text': text,'parse_mode': 'Markdown'}
    r = requests.post(url, data=data, timeout=8)
    r.raise_for_status()
    return r.json()

@app.route('/')
def index():
    return 'Telegram Signal Bot is running'

@app.route('/webhook', methods=['POST'])
def webhook():
    if not request.is_json:
        return jsonify({'ok': False, 'error': 'Expected JSON payload'}), 400

    payload = request.get_json()
    if payload.get('secret') != WEBHOOK_SECRET:
        return jsonify({'ok': False, 'error': 'Invalid secret'}), 403

    key = dedupe_key(payload)
    now = time.time()
    if key in RECENT_ALERTS and (now - RECENT_ALERTS[key]) < DEDUP_WINDOW_SECONDS:
        return jsonify({'ok': True, 'skipped': 'duplicate'}), 200
    RECENT_ALERTS[key] = now

    symbol = payload.get('symbol', 'UNKNOWN')
    action = payload.get('action', 'BUY').upper()
    exchange = payload.get('exchange', '')
    timeframe = payload.get('timeframe', '')
    expiry = payload.get('expiry_minutes', None)
    confidence = payload.get('confidence', None)
    note = payload.get('note', '')

    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    emoji = '🔴' if action == 'SELL' else '🟢'

    lines = [
        f"{emoji} *{action} SIGNAL!* {emoji}",
        f"*{symbol}* {exchange}",
        f"Timeframe: `{timeframe}`" if timeframe else "",
        f"Suggested expiry: {expiry} min" if expiry else "",
        f"Confidence: {float(confidence)*100:.0f}%" if confidence else "",
        f"Note: {note}" if note else "",
        f"Timestamp: {ts}"
    ]

    message = "\n".join([x for x in lines if x])
    send_telegram_message(message)

    return jsonify({'ok': True, 'sent': True}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
  
