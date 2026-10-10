import os
import re
import io
import asyncio
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(BASE_DIR, "kalit.txt")

app = Flask(__name__, static_folder=None)
CORS(app)

def get_saved_api_key():
    if os.path.exists(KEY_FILE):
        try:
            with open(KEY_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

SESSION_HISTORIES = {}

SYSTEM_INSTRUCTION = """
Siz — Stark Industries yaratgan J.A.R.V.I.S aqlli tizimisiz. Foydalanuvchi — Bahromjon.
TALABLAR:
1. Bahromjonga hurmat bilan, do'stona va sof o'zbek adabiy tilida gapiring.
2. Ruscha so'zlarni aralashtirmang.
3. Yulduzcha (*), panjara (#), tagchiziq (_), tire va emojilarni HECH QACHON yozmang.
4. Javoblaringiz 1 ta yoki ko'pi bilan 2 ta qisqa jumlada lo'nda va aniq bo'lsin.
5. Agar kamera yoki ko'rish haqida so'ralsa, optik sensor orqali ko'rib turganingizni tasdiqlang.
"""

TASHKENT_TZ = timezone(timedelta(hours=5))
NAMANGAN_LAT, NAMANGAN_LON = 41.00, 71.67
WEEKDAYS = ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"]
MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]

SONLAR = {
    "0": "nol", "00": "nol", "01": "bir", "02": "ikki", "03": "uch", "04": "to'rt", "05": "besh",
    "06": "olti", "07": "yetti", "08": "sakkiz", "09": "to'qqiz", "1": "bir", "2": "ikki", "3": "uch",
    "4": "to'rt", "5": "besh", "6": "olti", "7": "yetti", "8": "sakkiz", "9": "to'qqiz", "10": "o'n",
    "11": "o'n bir", "12": "o'n ikki", "13": "o'n uch", "14": "o'n to'rt", "15": "o'n besh",
    "16": "o'n olti", "17": "o'n yetti", "18": "o'n sakkiz", "19": "o'n to'qqiz", "20": "yigirma",
    "21": "yigirma bir", "22": "yigirma ikki", "23": "yigirma uch", "24": "yigirma to'rt",
    "25": "yigirma besh", "26": "yigirma olti", "27": "yigirma yetti", "28": "yigirma sakkiz",
    "29": "yigirma to'qqiz", "30": "o'ttiz", "31": "o'ttiz bir", "40": "qirq", "50": "ellik"
}

def get_namangan_weather():
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": NAMANGAN_LAT,
                "longitude": NAMANGAN_LON,
                "current": "temperature_2m,weather_code",
                "timezone": "Asia/Tashkent"
            },
            timeout=3
        )
        r.raise_for_status()
        cur = r.json()["current"]
        return round(cur["temperature_2m"]), int(cur["weather_code"])
    except Exception:
        return 21, 0

def weather_desc(code: int) -> str:
    if code == 0: return "ochiq va musaffo"
    if code in (1, 2): return "asosan musaffo"
    if code == 3: return "bulutli"
    if code in (45, 48): return "tumanli"
    if code in (51, 53, 55, 56, 57): return "mayda yomg'irli"
    if code in (61, 63, 65, 66, 67, 80, 81, 82): return "yomg'irli"
    if code in (71, 73, 75, 77, 85, 86): return "qorli"
    return "mo'tadil"

def build_custom_greeting() -> str:
    now = datetime.now(TASHKENT_TZ)
    h = now.hour
    if 5 <= h < 11: vaqt_salom = "Xayrli tong"
    elif 11 <= h < 17: vaqt_salom = "Xayrli kun"
    elif 17 <= h < 22: vaqt_salom = "Xayrli kech"
    else: vaqt_salom = "Tungi vaqtingiz xayrli bo'lsin"

    yil = "ikki ming yigirma oltinchi"
    oy = MONTHS[now.month - 1]
    kun = SONLAR.get(str(now.day), str(now.day))
    hafta_kuni = WEEKDAYS[now.weekday()]

    soat_soz = SONLAR.get(str(h), str(h))
    daqiqa_soz = SONLAR.get(now.strftime("%M"), now.strftime("%M"))

    temp, code = get_namangan_weather()
    havo = weather_desc(code)
    t_abs = SONLAR.get(str(abs(temp)), str(abs(temp)))
    t_soz = f"nol pastida {t_abs}" if temp < 0 else f"{t_abs}"

    return (
        f"Assalomu alaykum, Bahromjon! {vaqt_salom}. "
        f"Bugun {yil} yil, {kun} {oy}, {hafta_kuni}. "
        f"Hozir soat {soat_soz} dan {daqiqa_soz} daqiqa o'tdi. "
        f"Namanganda ob-havo {havo}, harorat {t_soz} daraja. "
        f"Optik sensor va audio aloqa faollashtirildi, sizni tinglamoqdaman."
    )

# --- MADINA AI LOTIN FONETIKASI (100% ISHONCHLI) ---
def clean_uzbek_latin_tts(text: str) -> str:
    if not text: return ""
    t = text
    # Markdown va belgilar
    t = re.sub(r"[*_#`~|>\[\]\(\)\{\}\\\/]+", " ", t)
    t = t.replace("2026", "ikki ming yigirma oltinchi")
    t = t.replace("°C", " daraja")
    t = t.replace("UZS", "so'm").replace("so'm", "som")

    # Sonlarni almashtirish
    for k, v in sorted(SONLAR.items(), key=lambda x: len(x[0]), reverse=True):
        t = re.sub(r"\b" + k + r"\b", v, t)

    # Edge-TTS to'xtab qolmasligi uchun tutuq belgilarini soddalashtirish
    t = re.sub(r"[‘ʻʼ`´]", "'", t)
    t = t.replace("o'", "o").replace("O'", "O")
    t = t.replace("g'", "g").replace("G'", "G")
    t = t.replace("–", " ").replace("—", " ").replace("-", " ")
    return re.sub(r"\s+", " ", t).strip()

async def synthesize_madina_tts(text: str) -> bytes:
    import edge_tts
    clean_text = clean_uzbek_latin_tts(text) or "Eshitaman Bahromjon."
    communicate = edge_tts.Communicate(clean_text, "uz-UZ-MadinaNeural", rate="+8%", pitch="+0Hz")
    buf = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.extend(chunk["data"])
    return bytes(buf)

def generate_voice(text: str) -> bytes:
    try:
        audio = asyncio.run(synthesize_madina_tts(text))
        if audio and len(audio) > 100:
            return audio
    except Exception as e:
        print(f"[Edge-TTS Xatosi]: {e}")

    # Zaxira gTTS
    try:
        from gtts import gTTS
        fp = io.BytesIO()
        gTTS(text=clean_uzbek_latin_tts(text), lang="uz").write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception as e2:
        print(f"[gTTS Xatosi]: {e2}")
        return b""

def call_omniroute(query: str, session_id: str):
    key = get_saved_api_key()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    now = datetime.now(TASHKENT_TZ)
    sys_prompt = (
        f"{SYSTEM_INSTRUCTION}\n"
        f"Hozirgi vaqt: {now.strftime('%H:%M')}, sana: {now.day}-{MONTHS[now.month-1]} {now.year} yil.\n"
        f"Savolga bevosita, 1-2 ta jumlada lo'nda va aniq javob qaytaring."
    )

    if session_id not in SESSION_HISTORIES:
        SESSION_HISTORIES[session_id] = []

    history = SESSION_HISTORIES[session_id]
    messages = [{"role": "system", "content": sys_prompt}]
    for item in history[-4:]:
        messages.append(item)
    messages.append({"role": "user", "content": query})

    endpoints = [
        "http://127.0.0.1:20128/v1/chat/completions",
        "http://localhost:20128/v1/chat/completions"
    ]

    for url in endpoints:
        try:
            res = requests.post(
                url,
                headers=headers,
                json={"model": "auto", "messages": messages, "temperature": 0.4},
                timeout=10
            )
            if res.status_code == 200:
                reply = res.json()["choices"][0]["message"]["content"]
                if reply:
                    clean_reply = reply.strip().replace("*", "")
                    history.append({"role": "user", "content": query})
                    history.append({"role": "assistant", "content": clean_reply})
                    SESSION_HISTORIES[session_id] = history[-6:]
                    return clean_reply, None
        except Exception:
            continue

    q_low = query.lower()
    if any(w in q_low for w in ["ko'r", "kor", "kamera", "tasvir"]):
        return "Albatta Bahromjon! Optik sensor orqali sizni ko'rib turibman.", None

    return "Labbay Bahromjon, buyrug'ingizni qabul qildim.", None

@app.route("/")
def index():
    paths = [
        os.path.join(BASE_DIR, "index.html"),
        os.path.join(BASE_DIR, "templates", "index.html"),
        os.path.join(os.getcwd(), "index.html")
    ]
    for p in paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    return "<h1>Xatolik: index.html topilmadi!</h1>", 404

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(BASE_DIR, filename)

@app.route("/api/greeting", methods=["GET"])
def api_greeting():
    return jsonify({"greeting": build_custom_greeting()})

@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    query = str(data.get("message") or data.get("query") or "").strip()[:4000]
    session_id = data.get("session_id", "default")

    if not query:
        return jsonify({"ok": False, "reply": "Buyruq berilmadi."}), 400

    reply, err = call_omniroute(query, session_id)
    return jsonify({"ok": True, "reply": reply})

@app.route("/api/tts", methods=["POST"])
def tts():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"ok": False, "reply": "Matn kiritilmadi."}), 400

    audio_bytes = generate_voice(text)
    if not audio_bytes:
        return jsonify({"ok": False, "reply": "Audio generatsiya qilinmadi"}), 500

    return Response(audio_bytes, mimetype="audio/mpeg")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)