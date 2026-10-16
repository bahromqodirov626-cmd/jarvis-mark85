# JARVIS — O'zbek Tilidagi Shaxsiy Aqlli Yordamchi

Ushbu loyiha **OmniRoute AI**, **Microsoft Edge Neural TTS** va **Open-Meteo API** asosida ishlaydigan zamonaviy, tiniq va sof o'zbek tilidagi ovozli yordamchi tizimidir.

## Xususiyatlari

- **Sof O'zbek Tili**: Begona so'zlarsiz, adabiy va ravon o'zbek tilida muloqot qiladi
- **Tabiiy Ovoz (Edge-TTS)**: Robotdek emas, haqiqiy inson talaffuziga yaqin `Sardor` (erkak) ovozi
- **Cyberpunk / Sci-Fi Interfeys**: Stark Industries uslubidagi aylanuvchi Arc Reactor, ovoz to'lqinlari, yozish va mikrofondan gapirish imkoniyati
- **Haqiqiy Vaqt Ma'lumotlari**: Namangan ob-havosi va USD kursi
- **Xavfsiz API**: Kalit `.gitignore` da saqlandi, API timeout va error handling qo'shildi

## O'rnatish

```bash
pip install -r requirements.txt
```

## Ishga tushirish

### Windows (start.bat orqali)
```batch
start.bat
```

### Terminal orqali
```bash
python app.py
```

Brauzeringizda `http://127.0.0.1:5000` manzilini oching.

## Konfiguratsiya

### Environment Variables
`.env` faylida qo'yish yoki terminal orqali o'rnatish:

```bash
set JARVIS_API_KEY=your_api_key_here
set OMNIROUTE_URL=http://127.0.0.1:20128/v1/chat/completions
set ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:5000
```

Yoki `kalit.txt` faylida API kalitni to'g'ridan-to'g'ri saqlang.

## API Endpoints

- `GET /` — asosiy sahifa (index.html)
- `GET /api/health` — server sog'ligi
- `GET /api/live` — ob-havo va USD kursi
- `GET /api/system` — CPU, RAM, Disk ma'lumoti
- `GET /api/greeting` — boshlang'ich salom
- `POST /api/ask` — AI dan savol so'rash
- `POST /api/tts` — matndan ovoz generatsiya

## Xavfsizlik

- `kalit.txt`, `.env` va `__pycache__/` `.gitignore` da yashiringan
- Barcha API so'rovlariga timeout va error handling qo'shildi
- Frontend xatolarida foydalanuvchiga bildirishnoma ko'rsatiladi

## Texnologiyalar

- **Backend**: Flask + Python
- **Frontend**: Tailwind CSS + Vanilla JavaScript
- **TTS**: Edge-TTS + gTTS
- **AI**: OmniRoute API
- **API**: Open-Meteo (ob-havo), CBU (valyuta kurslar)

## Royalti

JARVIS Mark-85 — Bahromjon uchun yaratildi. ⚔️🤖

