import os
import json
import urllib.request
import urllib.parse
import urllib.error
import html
import re
import ast
import operator
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

# =========================
# AYARLAR
# =========================

def load_env():
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_env()

AI_KEY = os.getenv("OPENROUTER_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

MEMORY_FILE = "memory.json"
FILES_DIR = "files"

if not AI_KEY:
    print("HATA: OPENROUTER_API_KEY bulunamadı.")
    raise SystemExit

if not TG_TOKEN:
    print("HATA: TELEGRAM_BOT_TOKEN bulunamadı.")
    raise SystemExit

# =========================
# HAFIZA
# =========================

def load_memory():
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

memory = load_memory()

def save_memory():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def add_memory(chat_id, role, text):
    key = str(chat_id)

    if key not in memory:
        memory[key] = []

    memory[key].append({
        "role": role,
        "content": text
    })

    memory[key] = memory[key][-20:]
    save_memory()

def get_history(chat_id):
    return memory.get(str(chat_id), [])

# =========================
# AI
# =========================

def ask_ai(message, chat_id=None, extra=""):

    messages = [
        {
            "role": "system",
            "content": """Sen Yhlas AI Agent'sın.
Türkçe konuş.
Kısa ama faydalı cevaplar ver.
Gerektiğinde adım adım anlat.
Kullanıcı senden bir şey yapmanı istediğinde mümkün olduğunca yardımcı ol."""
        }
    ]

    if chat_id:
        messages += get_history(chat_id)

    if extra:
        message = message + "\n\nAraç sonucu:\n" + extra

    messages.append({
        "role": "user",
        "content": message
    })

    data = {
        "model": "openrouter/free",
        "messages": messages
    }

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + AI_KEY
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=90) as response:
        result = json.loads(response.read().decode("utf-8"))

    answer = result["choices"][0]["message"]["content"]

    if chat_id:
        add_memory(chat_id, "user", message)
        add_memory(chat_id, "assistant", answer)

    return answer

# =========================
# TELEGRAM
# =========================

def telegram_request(method, data=None):

    url = f"https://api.telegram.org/bot{TG_TOKEN}/{method}"

    body = json.dumps(data or {}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))

def telegram_send(chat_id, text):

    telegram_request(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text
        }
    )

# =========================
# WEB ARAMA
# =========================

def web_search(query):

    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        page = response.read().decode("utf-8", errors="ignore")

    results = []

    pattern = r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'

    for match in re.findall(pattern, page):
        link = html.unescape(match[0])
        title = re.sub("<.*?>", "", match[1])
        title = html.unescape(title)

        results.append({
            "title": title,
            "url": link
        })

        if len(results) >= 5:
            break

    if not results:
        return "Arama sonucu bulunamadı."

    text = ""

    for i, r in enumerate(results, 1):
        text += f"{i}. {r['title']}\n{r['url']}\n\n"

    return text

# =========================
# DOSYA ARAÇLARI
# =========================

def list_files():

    files = []

    for root, dirs, names in os.walk(FILES_DIR):

        for name in names:

            path = os.path.relpath(
                os.path.join(root, name),
                FILES_DIR
            )

            files.append(path)

    if not files:
        return "files klasörü boş."

    return "\n".join("📄 " + x for x in files)

def read_file(name):

    name = os.path.normpath(name)

    if name.startswith(".."):
        return "Geçersiz dosya."

    path = os.path.join(FILES_DIR, name)

    if not os.path.isfile(path):
        return "Dosya bulunamadı."

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        return content[:12000]

    except Exception as e:
        return "Dosya okunamadı: " + str(e)

# =========================
# HESAP MAKİNESİ
# =========================

OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg
}

def calc_node(node):

    if isinstance(node, ast.Num):
        return node.n

    if isinstance(node, ast.UnaryOp):
        return OPS[type(node.op)](calc_node(node.operand))

    if isinstance(node, ast.BinOp):
        return OPS[type(node.op)](
            calc_node(node.left),
            calc_node(node.right)
        )

    raise ValueError("Desteklenmeyen işlem")

def calculate(expression):

    tree = ast.parse(expression, mode="eval")

    result = calc_node(tree.body)

    return str(result)

# =========================
# TELEGRAM KOMUTLARI
# =========================

def handle_message(chat_id, text):

    if text == "/start":

        return """🤖 Yhlas AI Agent aktif!

Komutlar:

/web arama
🌐 İnternette ara

/calc 25*18
🧮 Hesaplama yap

/files
📁 Dosyaları göster

/read dosya.txt
📖 Dosya oku

/clear
🧠 Hafızayı temizle

Normal mesaj gönder:
💬 AI ile konuş"""

    if text == "/files":

        return list_files()

    if text.startswith("/read "):

        return read_file(text[6:].strip())

    if text.startswith("/calc "):

        try:
            return "🧮 Sonuç: " + calculate(text[6:].strip())
        except Exception as e:
            return "Hesaplama hatası: " + str(e)

    if text.startswith("/web "):

        query = text[5:].strip()

        if not query:
            return "Örnek: /web Bitcoin fiyatı"

        try:
            result = web_search(query)

            return "🌐 Arama sonuçları:\n\n" + result

        except Exception as e:
            return "Web arama hatası: " + str(e)

    if text == "/clear":

        memory[str(chat_id)] = []
        save_memory()

        return "🧠 Hafızan temizlendi."

    # Normal AI mesajı
    return ask_ai(text, chat_id)

# =========================
# TELEGRAM LOOP
# =========================

def telegram_loop():

    print("Telegram Agent başlatıldı...")

    offset = 0

    while True:

        try:

            result = telegram_request(
                "getUpdates",
                {
                    "offset": offset,
                    "timeout": 30
                }
            )

            for update in result.get("result", []):

                offset = update["update_id"] + 1

                message = update.get("message", {})

                chat = message.get("chat", {})

                text = message.get("text")

                if not text:
                    continue

                chat_id = chat.get("id")

                print("Mesaj:", text)

                try:

                    answer = handle_message(
                        chat_id,
                        text
                    )

                    telegram_send(
                        chat_id,
                        answer
                    )

                except Exception as e:

                    print("Hata:", e)

                    telegram_send(
                        chat_id,
                        "❌ Hata: " + str(e)
                    )

        except Exception as e:

            print("Telegram bağlantı hatası:", e)

# =========================
# WEB PANEL
# =========================

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Yhlas AI Agent</title>
<style>
body{
font-family:Arial;
background:#111;
color:white;
margin:0;
padding:20px;
}
.container{
max-width:700px;
margin:auto;
}
h1{
text-align:center;
}
textarea{
width:100%;
height:100px;
background:#222;
color:white;
border:1px solid #444;
border-radius:10px;
padding:12px;
box-sizing:border-box;
}
button{
margin-top:10px;
padding:12px 20px;
border:0;
border-radius:10px;
cursor:pointer;
}
#answer{
margin-top:20px;
background:#222;
padding:15px;
border-radius:10px;
white-space:pre-wrap;
}
</style>
</head>
<body>
<div class="container">

<h1>🤖 Yhlas AI Agent</h1>

<textarea id="msg" placeholder="Agent'a mesaj yaz..."></textarea>

<button onclick="send()">Gönder</button>

<div id="answer"></div>

</div>

<script>
async function send(){

let msg=document.getElementById("msg").value;

document.getElementById("answer").innerText="⏳ Düşünüyor...";

try{

let r=await fetch("/chat",{
method:"POST",
headers:{
"Content-Type":"application/json"
},
body:JSON.stringify({
message:msg
})
});

let data=await r.json();

document.getElementById("answer").innerText=
data.answer || data.error;

}catch(e){

document.getElementById("answer").innerText=
"Bağlantı hatası: "+e;

}

}
</script>

</body>
</html>
"""

class WebHandler(BaseHTTPRequestHandler):

    def send_data(self, data, content_type="text/html"):

        body = data.encode("utf-8")

        self.send_response(200)

        self.send_header(
            "Content-Type",
            content_type + "; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.end_headers()

        self.wfile.write(body)

    def do_GET(self):

        if self.path == "/":

            self.send_data(HTML_PAGE)

        else:

            self.send_data(
                json.dumps({"error":"Not found"}),
                "application/json"
            )

    def do_POST(self):

        if self.path != "/chat":

            self.send_data(
                json.dumps({"error":"Not found"}),
                "application/json"
            )

            return

        length = int(
            self.headers.get(
                "Content-Length",
                0
            )
        )

        body = self.rfile.read(length)

        try:

            data = json.loads(
                body.decode("utf-8")
            )

            message = data.get(
                "message",
                ""
            )

            answer = ask_ai(message)

            self.send_data(
                json.dumps(
                    {
                        "answer":answer
                    },
                    ensure_ascii=False
                ),
                "application/json"
            )

        except Exception as e:

            self.send_data(
                json.dumps(
                    {
                        "error":str(e)
                    },
                    ensure_ascii=False
                ),
                "application/json"
            )

def web_server():

    server = HTTPServer(
        ("0.0.0.0",8080),
        WebHandler
    )

    print("🌐 Web panel:")
    print("http://127.0.0.1:8080")

    server.serve_forever()

# =========================
# BAŞLAT
# =========================

if __name__ == "__main__":

    Thread(
        target=web_server,
        daemon=True
    ).start()

    telegram_loop()
