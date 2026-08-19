cd ~/myagent

cat > agent.py <<'PY'
import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# =========================
# ENV
# =========================

AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_API_URL = os.getenv(
    "AI_API_URL",
    "https://openrouter.ai/api/v1/chat/completions"
)
AI_MODEL = os.getenv(
    "AI_MODEL",
    "deepseek/deepseek-chat"
)

TG_TOKEN = os.getenv("TG_TOKEN", "")


# =========================
# AI
# =========================

def ask_ai(message):
    if not AI_API_KEY:
        return "AI_API_KEY Railway Variables bölümünde ayarlanmamış."

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": AI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Sen Yhlas AI Agent'sın. "
                    "Türkçe cevap ver. "
                    "Kısa, anlaşılır ve yardımcı ol."
                )
            },
            {
                "role": "user",
                "content": message
            }
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(
            AI_API_URL,
            headers=headers,
            json=data,
            timeout=60
        )

        if response.status_code != 200:
            return f"AI API hatası ({response.status_code}): {response.text[:500]}"

        result = response.json()

        return result["choices"][0]["message"]["content"]

    except Exception as e:
        return f"AI bağlantı hatası: {str(e)}"


# =========================
# TELEGRAM
# =========================

def send_telegram(chat_id, text):
    if not TG_TOKEN:
        print("TG_TOKEN ayarlanmamış.")
        return False

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

    try:
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text
            },
            timeout=30
        )

        print("Telegram:", response.status_code, response.text[:300])

        return response.ok

    except Exception as e:
        print("Telegram gönderme hatası:", e)
        return False


# =========================
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
