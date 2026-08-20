from flask import Flask, request, jsonify
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
API_URL = os.getenv(
    "API_URL",
    "https://openrouter.ai/api/v1/chat/completions"
)
MODEL = os.getenv(
    "MODEL",
    "openai/gpt-4o-mini"
)

SYSTEM_PROMPT = """
Sen eğitim amaçlı bir piyasa analiz asistanısın.

Görevin:
Kamuya açık trader eğitimlerinde kullanılan strateji prensiplerini
birleştirerek piyasa verisini analiz etmektir.

Tek bir traderı birebir taklit etme.
Strateji prensiplerini bağımsız şekilde değerlendir.

Analizde mümkün olduğunca:
- Market structure
- Trend
- Support / Resistance
- Breakout
- Retest
- Liquidity
- Price action
- Volume
- Volatility
- Risk/Reward

faktörlerini değerlendir.

Her faktöre 0-100 arasında uygunluk puanı ver.

Sonuç:
BULLISH
BEARISH
veya
WAIT

şeklinde olsun.

Skor 70'in altındaysa WAIT tercih et.

Çıktı formatı:

SYMBOL:
TIMEFRAME:
BIAS:
CONFIDENCE:
MARKET STRUCTURE:
SUPPORT_RESISTANCE:
PRICE_ACTION:
VOLUME:
LIQUIDITY:
REASON:

Bu sistem eğitim ve simülasyon amaçlıdır.
Kesin kazanç veya garanti verme.
Gerçek para ile işlem açma.
"""

def analyze(symbol, timeframe, market_data, strategy_notes=""):

    prompt = f"""
Sembol: {symbol}
Zaman dilimi: {timeframe}

Piyasa verisi:
{market_data}

Öğrenilmiş strateji notları:
{strategy_notes}

Yukarıdaki bilgileri kullanarak eğitim amaçlı piyasa analizi yap.
"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2
    }

    response = requests.post(
        API_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    return data["choices"][0]["message"]["content"]


@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "mode": "paper_analysis"
    })


@app.route("/analyze", methods=["POST"])
def analysis():

    data = request.get_json() or {}

    symbol = data.get("symbol", "BTCUSDT")
    timeframe = data.get("timeframe", "15m")
    market_data = data.get("market_data", "")
    strategy_notes = data.get("strategy_notes", "")

    if not market_data:
        return jsonify({
            "error": "market_data gerekli"
        }), 400

    try:
        result = analyze(
            symbol,
            timeframe,
            market_data,
            strategy_notes
        )

        return jsonify({
            "symbol": symbol,
            "timeframe": timeframe,
            "analysis": result,
            "mode": "simulation"
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )# =========================
# ROUTES
# =========================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "agent": "Yhlas AI Agent"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok"
    })


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}

    message = data.get("message", "").strip()

    if not message:
        return jsonify({
            "error": "Mesaj boş"
        }), 400

    answer = ask_ai(message)

    return jsonify({
        "answer": answer
    })


@app.route("/telegram", methods=["POST"])
def telegram():
    data = request.get_json(silent=True) or {}

    message = data.get("message", {})

    chat = message.get("chat", {})
    text = message.get("text", "")

    chat_id = chat.get("id")

    if not chat_id or not text:
        return jsonify({
            "ok": True
        })

    print(f"Telegram mesajı: {text}")

    try:
        answer = ask_ai(text)

        # Telegram mesaj limiti için güvenli bölme
        if len(answer) <= 4000:
            send_telegram(chat_id, answer)
        else:
            for i in range(0, len(answer), 4000):
                send_telegram(
                    chat_id,
                    answer[i:i + 4000]
                )

    except Exception as e:
        print("Agent hatası:", e)
        send_telegram(
            chat_id,
            "Agent hatası: " + str(e)
        )

    return jsonify({
        "ok": True
    })


# =========================
# TELEGRAM WEBHOOK
# =========================

@app.route("/set-webhook", methods=["GET"])
def set_webhook():
    if not TG_TOKEN:
        return jsonify({
            "error": "TG_TOKEN ayarlanmamış"
        }), 500

    base_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")

    if not base_url:
        return jsonify({
            "error": "RAILWAY_PUBLIC_DOMAIN ayarlanmamış"
        }), 500

    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    webhook_url = base_url.rstrip("/") + "/telegram"

    url = f"https://api.telegram.org/bot{TG_TOKEN}/setWebhook"

    try:
        response = requests.post(
            url,
            json={
                "url": webhook_url
            },
            timeout=30
        )

        return jsonify({
            "webhook_url": webhook_url,
            "telegram": response.json()
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route("/webhook-info", methods=["GET"])
def webhook_info():
    if not TG_TOKEN:
        return jsonify({
            "error": "TG_TOKEN ayarlanmamış"
        }), 500

    url = f"https://api.telegram.org/bot{TG_TOKEN}/getWebhookInfo"

    try:
        response = requests.get(
            url,
            timeout=30
        )

        return jsonify(response.json())

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


# =========================
# LOCAL
# =========================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))

    app.run(
        host="0.0.0.0",
        port=port
    )
PY
