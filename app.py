import os
import re
import io
import time
import asyncio
import logging
import psutil
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(BASE_DIR, "kalit.txt")

app = Flask(__name__, static_folder=None)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:5000").split(",")
CORS(
    app,
    resources={r"/api/*": {"origins": ALLOWED_ORIGINS}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

ALLOWED_STATIC_EXT = {
    ".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".gif",
    ".svg", ".ico", ".webp", ".woff", ".woff2", ".ttf", ".mp3", ".wav"
}

def get_saved_api_key():
    key = os.getenv("JARVIS_API_KEY")
    if key:
        return key
    if os.path.exists(KEY_FILE):
        try:
            with open(KEY_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.warning(f"Kalit faylini o'qiyishda xatolik: {e}")
    return ""

SESSION_HISTORIES = {}

SYSTEM_INSTRUCTION = """
Siz — Stark Industries yaratgan J.A.R.V.I.S aqlli tizimisiz. Foydalanuvchi — Bahromjon.
TALABLAR:
1. Bahromjonga hurmat bilan, do'stona va sof o'zbek adabiy tilida gapiring.
2. Faqat o'zbek lotin alifbosida yozing. Kirill harflari, rus yoki ingliz so'zlarini ishlatmang. Agar bilmasangiz, o'zbekcha sodda so'z tanlang.
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

def _fetch_namangan_weather():
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": NAMANGAN_LAT,
                "longitude": NAMANGAN_LON,
                "current": "temperature_2m,weather_code",
                "timezone": "Asia/Tashkent"
            },
            timeout=5
        )
        r.raise_for_status()
        cur = r.json()["current"]
        return round(cur["temperature_2m"]), int(cur["weather_code"])
    except requests.Timeout:
        logger.warning("Open-Meteo: API time out")
        return None
    except requests.RequestException as e:
        logger.warning(f"Open-Meteo xatosi: {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.warning(f"Open-Meteo: Ma'lumot tahlil xatosi: {e}")
        return None
    except Exception as e:
        logger.warning(f"Open-Meteo: Noma'lum xatolik: {e}")
        return None

_CACHE = {"weather": (0, None), "usd": (0, None)}

def get_namangan_weather():
    ts, val = _CACHE["weather"]
    if val is not None and time.time() - ts < 300:
        return val
    fresh = _fetch_namangan_weather()
    if fresh:
        _CACHE["weather"] = (time.time(), fresh)
        return fresh
    return val if val else (21, 0)

def get_usd_rate():
    ts, val = _CACHE["usd"]
    if val is not None and time.time() - ts < 1800:
        return val
    try:
        r = requests.get(
            "https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/",
            timeout=5
        )
        r.raise_for_status()
        data = r.json()
        if data and len(data) > 0:
            val = float(data[0].get("Rate", 0))
            _CACHE["usd"] = (time.time(), val)
            return val
    except requests.Timeout:
        logger.warning("CBU API: Time out")
    except requests.RequestException as e:
        logger.warning(f"CBU API xatosi: {e}")
    except (ValueError, KeyError, IndexError) as e:
        logger.warning(f"CBU API: Ma'lumot tahlil xatosi: {e}")
    except Exception as e:
        logger.warning(f"CBU API: Noma'lum xatolik: {e}")
    return val if val else 0

def live_info() -> str:
    temp, code = get_namangan_weather()
    usd = get_usd_rate()
    usd_txt = f"{usd:,.0f} so'm".replace(",", " ") if usd else "noma'lum"
    return (
        f"JONLI MA'LUMOT (shu javoblarda foydalaning): Namangan hozir {weather_desc(code)}, "
        f"harorat {temp} daraja. AQSH dollari Markaziy bank kursi: {usd_txt}. "
        f"Shahar so'ralmasa, Namangan deb hisoblang va qayta so'ramang."
    )

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

def num_to_words(n: int) -> str:
    ONES = ["nol", "bir", "ikki", "uch", "to'rt", "besh", "olti", "yetti", "sakkiz", "to'qqiz"]
    TENS = ["", "o'n", "yigirma", "o'ttiz", "qirq", "ellik", "oltmish", "yetmish", "sakson", "to'qson"]
    if n < 0:
        return "minus " + num_to_words(-n)
    if n < 10:
        return ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return TENS[t] + ("" if o == 0 else " " + ONES[o])
    if n < 1000:
        h, lo = divmod(n, 100)
        s = ("" if h == 1 else ONES[h] + " ") + "yuz"
        return s + ("" if lo == 0 else " " + num_to_words(lo))
    for val, name in ((10**9, "milliard"), (10**6, "million"), (1000, "ming")):
        if n >= val:
            hi, lo = divmod(n, val)
            s = num_to_words(hi) + " " + name
            return s + ("" if lo == 0 else " " + num_to_words(lo))
    return str(n)

# --- MADINA AI LOTIN FONETIKASI (100% ISHONCHLI) ---
CYR_MAP = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'j','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'x','ц':'ts','ч':'ch','ш':'sh','ъ':'','ы':'i','ь':'','э':'e','ю':'yu','я':'ya','ў':"o'",'қ':'q','ғ':"g'",'ҳ':'h'}

def cyr_to_latin(s: str) -> str:
    out = []
    for ch in s:
        low = ch.lower()
        if low in CYR_MAP:
            rep = CYR_MAP[low]
            out.append(rep.capitalize() if ch.isupper() and rep else rep)
        else:
            out.append(ch)
    return ''.join(out)

def clean_uzbek_latin_tts(text: str) -> str:
    if not text: return ""
    t = cyr_to_latin(text)
    t = re.sub(r"[\*_#`~|>\[\]\(\)\{\}\\]+", " ", t)
    t = t.replace("2026", "ikki ming yigirma oltinchi")
    t = t.replace("°C", " daraja")
    t = t.replace("UZS", "so’m")

    t = re.sub(r"\d{1,3}(?:,\d{3})+", lambda m: num_to_words(int(m.group().replace(",", ""))), t)
    t = re.sub(r"\d+(?:\.\d+)?", lambda m: " nuqta ".join(num_to_words(int(p)) for p in m.group().split(".")), t)

    t = re.sub(r"[‘ʻʼ`´]", "’", t)
    t = t.replace("–", " ").replace("—", " ").replace("-", " ")
    return re.sub(r"\s+", " ", t).strip()

def generate_voice(text: str) -> bytes:
    clean_text = clean_uzbek_latin_tts(text)
    if not clean_text:
        clean_text = "Eshitaman Bahromjon."

    logger.info(f"[TTS] Boshlash: '{clean_text[:60]}'")

    try:
        import edge_tts
        logger.info("[TTS] edge_tts import qilindi, async event loop ochish...")

        async def get_edge_audio():
            try:
                logger.info("[TTS] Edge-TTS: Communicate ob'ekti yaratish...")
                communicate = edge_tts.Communicate(
                    clean_text,
                    "uz-UZ-SardorNeural",
                    rate="-4%",
                    pitch="-12Hz"
                )
                logger.info("[TTS] Edge-TTS: stream() chaqirish...")

                buf = bytearray()
                chunk_count = 0
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        buf.extend(chunk["data"])
                        chunk_count += 1

                logger.info(f"[TTS] Edge-TTS: {chunk_count} ta audio chunk olindi, total: {len(buf)} bytes")
                return bytes(buf) if buf else b""

            except Exception as e:
                logger.error(f"[TTS] Edge-TTS ichki xatosi: {type(e).__name__}: {e}")
                return b""

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio = loop.run_until_complete(get_edge_audio())
            loop.close()

            if audio and len(audio) > 100:
                logger.info(f"[TTS] ✓ Edge-TTS muvaffaqiyatli: {len(audio)} bytes")
                return audio
            else:
                logger.warning(f"[TTS] Edge-TTS: Audio kichik yoki bo'sh ({len(audio) if audio else 0} bytes)")

        except Exception as e:
            logger.error(f"[TTS] Event loop xatosi: {type(e).__name__}: {e}")

    except ImportError:
        logger.warning("[TTS] edge_tts o'rnatilmagan, gTTS'ga o'tish...")
    except Exception as e:
        logger.error(f"[TTS] Edge-TTS import xatosi: {type(e).__name__}: {e}")

    logger.info("[TTS] gTTS fallback bilan urinish...")
    try:
        from gtts import gTTS
        logger.info("[TTS] gTTS import qilindi, audio yaratish...")

        fp = io.BytesIO()
        logger.info(f"[TTS] gTTS ob'ekti yaratilsh: text='{clean_text[:40]}', lang='uz'")

        tts = gTTS(text=clean_text, lang="uz", slow=False)
        logger.info("[TTS] gTTS: write_to_fp() chaqirish...")

        tts.write_to_fp(fp)
        file_size = fp.tell()
        logger.info(f"[TTS] gTTS: write_to_fp tugadi, BytesIO size: {file_size} bytes")

        fp.seek(0)
        audio = fp.read()
        logger.info(f"[TTS] gTTS: Audio o'qildi, size: {len(audio)} bytes")

        if audio and len(audio) > 100:
            logger.info(f"[TTS] ✓ gTTS muvaffaqiyatli: {len(audio)} bytes")
            return audio
        else:
            logger.error(f"[TTS] gTTS: Audio kichik yoki bo'sh ({len(audio) if audio else 0} bytes)")
            return b""

    except ImportError:
        logger.error("[TTS] gTTS o'rnatilmagan: pip install gtts")
        return b""
    except Exception as e:
        logger.error(f"[TTS] gTTS xatosi: {type(e).__name__}: {e}", exc_info=True)
        return b""

def call_omniroute(query: str, session_id: str):
    key = get_saved_api_key()
    if not key:
        logger.warning("API kalit topilmadi")
        return "API kalit sozlanmagan, Bahromjon.", None

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    now = datetime.now(TASHKENT_TZ)
    sys_prompt = (
        f"{SYSTEM_INSTRUCTION}\n"
        f"Hozirgi vaqt: {now.strftime('%H:%M')}, sana: {now.day}-{MONTHS[now.month-1]} {now.year} yil.\n"
        f"{live_info()}\n"
        f"Savolga bevosita, 1-2 ta jumlada lo'nda va aniq javob qaytaring."
    )

    if session_id not in SESSION_HISTORIES:
        SESSION_HISTORIES[session_id] = []

    history = SESSION_HISTORIES[session_id]
    messages = [{"role": "system", "content": sys_prompt}]
    for item in history[-4:]:
        messages.append(item)
    messages.append({"role": "user", "content": query})

    api_url = os.getenv("OMNIROUTE_URL", "http://127.0.0.1:20128/v1/chat/completions")

    try:
        res = requests.post(
            api_url,
            headers=headers,
            json={"model": "auto", "messages": messages, "temperature": 0.4},
            timeout=20
        )
        if res.status_code == 200:
            try:
                reply = res.json()["choices"][0]["message"]["content"]
                if reply:
                    clean_reply = clean_uzbek_latin_tts(reply).strip()
                    history.append({"role": "user", "content": query})
                    history.append({"role": "assistant", "content": clean_reply})
                    SESSION_HISTORIES[session_id] = history[-20:]
                    return clean_reply, None
            except (KeyError, IndexError, ValueError) as e:
                logger.error(f"API javob tahlil xatosi: {e}")
                return "Javob tahlil qilinmadi, Bahromjon.", None
        else:
            logger.error(f"API status: {res.status_code}")
    except requests.Timeout:
        logger.error(f"API timeout: {api_url}")
        return "API ulanishida vaqt tugadi, Bahromjon.", None
    except requests.ConnectionError:
        logger.error(f"API ulanish xatosi: {api_url}")
        return "API serveriga ulanib bo'lmadi, Bahromjon.", None
    except Exception as e:
        logger.error(f"API chaqiruvida xatolik: {type(e).__name__}: {e}")

    q_low = query.lower()
    if any(w in q_low for w in ["ko'r", "kor", "kamera", "tasvir"]):
        return "Albatta Bahromjon! Optik sensor orqali sizni ko'rib turibman.", None

    if any(w in q_low for w in ["dollar", "kurs", "valyuta"]):
        usd = get_usd_rate()
        if usd:
            return f"Bahromjon, Markaziy bank kursi bo'yicha bir dollar {usd:,.0f} so'm.".replace(",", " "), None
    if any(w in q_low for w in ["ob-havo", "havo", "harorat", "yomg'ir", "yomgir", "issiq", "sovuq"]):
        temp, code = get_namangan_weather()
        return f"Bahromjon, Namanganda hozir havo {weather_desc(code)}, harorat {temp} daraja.", None

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
    # Faqat xavfsiz kengaytmalar beriladi (app.py, kalit.txt va h.k. yopiq)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_STATIC_EXT:
        return jsonify({"ok": False, "reply": "Topilmadi."}), 404
    return send_from_directory(BASE_DIR, filename)

@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({"ok": True, "status": "online"})

@app.route("/api/live", methods=["GET"])
def api_live():
    temp, code = get_namangan_weather()
    usd = get_usd_rate()
    return jsonify({
        "ok": True,
        "temp": temp,
        "weather": weather_desc(code),
        "usd": usd,
    })

@app.route("/api/system", methods=["GET"])
def api_system():
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        vm = psutil.virtual_memory()

        disk_path = 'C:' if os.name == 'nt' else '/'
        disk_usage = psutil.disk_usage(disk_path)

        return jsonify({
            "ok": True,
            "cpu_percent": round(cpu_percent, 1),
            "ram_used_gb": round(vm.used / (1024**3), 2),
            "ram_total_gb": round(vm.total / (1024**3), 2),
            "ram_percent": round(vm.percent, 1),
            "disk_percent": round(disk_usage.percent, 1)
        })
    except Exception as e:
        logger.error(f"Sistem ma'lumoti olishda xatolik: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/greeting", methods=["GET"])
def api_greeting():
    return jsonify({"greeting": build_custom_greeting()})

@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    query = str(data.get("message") or data.get("query") or "").strip()

    if not isinstance(query, str) or len(query) == 0 or len(query) > 4000:
        return jsonify({"ok": False, "reply": "Buyruq noto'g'ri yoki uzun."}), 400

    session_id = str(data.get("session_id", "default")).strip()

    try:
        reply, err = call_omniroute(query, session_id)
    except Exception as e:
        logger.error(f"API ask xatosi: {e}")
        return jsonify({"ok": False, "reply": "Ichki xatolik yuz berdi, Bahromjon."}), 500
    return jsonify({"ok": True, "reply": reply})

@app.route("/api/tts", methods=["POST"])
def tts():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()

    if not isinstance(text, str) or len(text) == 0:
        logger.warning("TTS: Matn berilmadi")
        return jsonify({"ok": False, "error": "Matn berilmadi"}), 400

    if len(text) > 1000:
        logger.warning(f"TTS: Matn uzun ({len(text)} chars)")
        return jsonify({"ok": False, "error": "Matn juda uzun"}), 400

    logger.info(f"TTS so'rovi: {text[:60]}...")

    try:
        audio_bytes = generate_voice(text)
        if not audio_bytes or len(audio_bytes) < 100:
            logger.error("TTS: Audio bo'sh yoki kichik")
            return jsonify({"ok": False, "error": "Audio generatsiya qilinmadi"}), 500

        logger.info(f"TTS: Audio qaytarildi ({len(audio_bytes)} bytes)")

        response = Response(audio_bytes, mimetype="audio/mpeg")
        response.headers["Content-Type"] = "audio/mpeg"
        response.headers["Content-Length"] = str(len(audio_bytes))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    except Exception as e:
        logger.error(f"TTS xatosi: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)