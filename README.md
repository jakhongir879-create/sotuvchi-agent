# Sotuvchi AI agent (Telegram + Gemini)

Mijozlarga katalog bo'yicha javob beradi, mahsulot rasmini ko'rsatadi, buyurtmani yig'ib menejerga yuboradi.

## Fayllar

| Fayl | Nima uchun |
|---|---|
| `biznes.txt` | Do'kon ma'lumotlari: yetkazish, to'lov, ish vaqti, ohang. **Mijoz ma'lumotiga almashtiring.** |
| `mahsulotlar.csv` | Katalog (Excel'da ochib tahrirlash mumkin). Ustunlar: id, nomi, kategoriya, narx, razmerlar, ranglar, qoldiq, tavsif, rasm |
| `bot.py` | Telegram qismi (ishga tushirish fayli) |
| `agent.py` | Agent qoidalari va fikrlash sikli |
| `gemini.py` | Gemini API (model band bo'lsa, keyingisiga o'tadi) |
| `katalog.py` | Katalogni CSV yoki Google Sheets'dan o'qiydi |

## Sozlamalar (Environment variables)

- `BOT_TOKEN`: @BotFather'dan olingan token
- `GEMINI_API_KEY`: aistudio.google.com'dan olingan kalit
- `MANAGER_CODE`: maxfiy so'z. Menejer botga `/menejer <so'z>` yozsa, buyurtmalar o'sha chatga keladi
- `MANAGER_CHAT_ID`: menejer chat ID si (botga `/id` yozib bilib olinadi). Doimiy ishlash uchun shuni kiritgan ma'qul
- `CATALOG_URL`: ixtiyoriy. Google Sheets katalog havolasi (quyida)

## Katalogni Google Sheets'da yuritish (tavsiya)

Shunda mijoz narx yoki qoldiqni o'zi o'zgartiradi, bot 5 daqiqada yangilanadi.

1. `mahsulotlar.csv` ni Google Sheets'ga import qiling (ustun nomlari o'zgarmasin).
2. Fayl → Ulashish → Internetda chop etish → varaqni tanlang → **CSV** → Chop etish.
3. Chiqqan havolani `CATALOG_URL` ga qo'ying.

## Render.com'ga bepul joylash

1. github.com'da yangi **private** repository oching va shu papkadagi fayllarni yuklang (`.env` faylini YUKLAMANG).
2. render.com → Sign up (GitHub bilan) → **New → Web Service** → repository'ni tanlang.
3. Sozlamalar:
   - Runtime: **Python**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
   - Instance type: **Free**
4. **Environment** bo'limiga `BOT_TOKEN`, `GEMINI_API_KEY`, `MANAGER_CODE` (va bo'lsa `MANAGER_CHAT_ID`, `CATALOG_URL`) ni kiriting.
5. **Deploy** tugmasini bosing. Logda `Webhook o'rnatildi` chiqsa, bot ishlayapti.
6. Menejer botga `/id` yozadi, chiqqan raqamni Render'da `MANAGER_CHAT_ID` ga qo'shasiz.

**Muhim:** Render'ning bepul serveri 15 daqiqa jim tursa "uxlab qoladi" va birinchi javob ~1 daqiqa kechikadi.
Buning oldini olish uchun cron-job.org'da bepul vazifa oching: har 10 daqiqada `https://SIZNING-SERVIS.onrender.com/` manzilini ochib tursin.

## Kompyuterda sinash

```
pip install -r requirements.txt
cp .env.example .env     # ichini to'ldiring
python bot.py
```

## Buyruqlar

- `/start`: salomlashish
- `/yangi`: suhbatni boshidan boshlash
- `/id`: chat ID ni ko'rsatadi
- `/menejer <kod>`: shu chatni menejer chati qilib ulaydi
