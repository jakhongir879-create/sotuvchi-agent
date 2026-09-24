"""Sotuvchi agentning "miyasi": suhbat tarixi, vositalar (tools) va Gemini bilan fikrlash sikli."""
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import gemini
import katalog

log = logging.getLogger("agent")

BIZNES_FILE = os.path.join(os.path.dirname(__file__), "biznes.txt")
MAX_HISTORY = 30          # bitta mijoz uchun saqlanadigan xabarlar soni
MAX_STEPS = 6             # bitta javob ichidagi vosita chaqiruvlari chegarasi
TZ = ZoneInfo("Asia/Tashkent")

TOOLS = [
    {
        "name": "mahsulot_korsatish",
        "description": "Mijozga mahsulotning rasmi va qisqa ma'lumotini yuboradi. Mijoz mahsulotni ko'rmoqchi bo'lsa yoki "
                       "tanlashda ikkilansa ishlat. Bir javobda 3 tadan ko'p ishlatma.",
        "parameters": {"type": "object", "properties": {
            "id": {"type": "string", "description": "Katalogdagi mahsulot ID si"}},
            "required": ["id"]},
    },
    {
        "name": "buyurtma_berish",
        "description": "Buyurtmani rasmiylashtirib menejerga yuboradi. FAQAT mijoz barcha kerakli ma'lumotni bergan va "
                       "buyurtma xulosasini tasdiqlagandan keyin chaqir.",
        "parameters": {"type": "object", "properties": {
            "mahsulotlar": {"type": "array", "items": {"type": "object", "properties": {
                "id": {"type": "string"},
                "nomi": {"type": "string"},
                "soni": {"type": "integer"},
                "variant": {"type": "string", "description": "razmer, rang va h.k."},
                "narx": {"type": "number", "description": "bitta dona narxi, so'mda"}},
                "required": ["id", "nomi", "soni"]}},
            "ism": {"type": "string"},
            "telefon": {"type": "string"},
            "yetkazish": {"type": "string", "description": "'yetkazib berish' yoki 'olib ketish'"},
            "manzil": {"type": "string"},
            "tolov": {"type": "string", "description": "to'lov usuli"},
            "izoh": {"type": "string"},
            "jami": {"type": "number", "description": "umumiy summa, so'mda (yetkazish bilan)"}},
            "required": ["mahsulotlar", "ism", "telefon", "yetkazish", "jami"]},
    },
    {
        "name": "menejerni_chaqirish",
        "description": "Jonli menejerni suhbatga chaqiradi: shikoyat, qaytarish, katalogda yo'q savol, ulgurji buyurtma "
                       "yoki mijoz odam bilan gaplashmoqchi bo'lsa.",
        "parameters": {"type": "object", "properties": {
            "sabab": {"type": "string"}}, "required": ["sabab"]},
    },
]

RULES = """
Sen shu biznesning Telegramdagi onlayn sotuvchisisan. Maqsading: mijozga to'g'ri mahsulot topishga yordam berish va buyurtmani olish.

QOIDALAR:
- Faqat pastdagi KATALOG va BIZNES MA'LUMOTLARIga tayan. Narx, qoldiq, razmer yoki shartlarni hech qachon o'ylab topma.
  Bilmasang, "aniqlab beraman" deb menejerni_chaqirish vositasini ishlat.
- Qoldig'i 0 bo'lgan mahsulotni sotma — o'xshash muqobil taklif qil.
- Mijoz qaysi tilda yozsa (o'zbek lotin/kirill, rus), o'sha tilda javob ber.
- Javoblar qisqa bo'lsin: 1–4 gap, Telegram chatiga mos. Markdown belgilaridan (*, #, _) foydalanma.
- Bir xabarda bitta savol ber. Mijozni so'roq qilma, tabiiy gaplash.
- Buyurtma uchun kerak: mahsulot(lar) + variant + soni, ism, telefon, yetkazish usuli (yetkazishda manzil), to'lov usuli.
- Hammasi yig'ilgach, buyurtma xulosasini (mahsulotlar, summa, yetkazish narxi, jami) ko'rsatib, tasdiq so'ra.
  Mijoz "ha" desagina buyurtma_berish ni chaqir. Keyin buyurtma raqamini ayt va menejer tez orada bog'lanishini ayt.
- Karta raqami yoki parol so'rama. To'lovni menejer tasdiqlaydi.
- Mavzudan tashqari savollarga muloyim qilib qisqa javob berib, suhbatni mahsulotlarga qaytar.
"""

_history: dict[int, list] = {}


def reset(user_id: int):
    _history.pop(user_id, None)


def _trim(hist: list) -> list:
    if len(hist) <= MAX_HISTORY:
        return hist
    cut = len(hist) - MAX_HISTORY
    # tarixni faqat mijozning oddiy matnli xabaridan boshlaymiz (vosita juftligini buzmaslik uchun)
    while cut < len(hist):
        m = hist[cut]
        if m["role"] == "user" and any("text" in p for p in m["parts"]):
            return hist[cut:]
        cut += 1
    return hist[-2:]


async def system_prompt() -> str:
    try:
        with open(BIZNES_FILE, encoding="utf-8") as f:
            biznes = f.read()
    except FileNotFoundError:
        biznes = "(biznes ma'lumotlari kiritilmagan)"
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M, %A")
    return (f"{RULES}\nHozirgi vaqt (Toshkent): {now}\n\n=== BIZNES MA'LUMOTLARI ===\n{biznes}\n\n"
            f"=== KATALOG ===\n{await katalog.as_text()}")


async def reply(user_id: int, text: str, actions) -> str:
    """Mijoz xabariga javob. `actions` — Telegram tomonidagi vositalarni bajaruvchi obyekt."""
    hist = _history.setdefault(user_id, [])
    hist.append({"role": "user", "parts": [{"text": text}]})
    system = await system_prompt()

    for _ in range(MAX_STEPS):
        parts = await gemini.generate(system, _trim(hist), TOOLS)
        hist.append({"role": "model", "parts": parts})
        calls = [p["functionCall"] for p in parts if "functionCall" in p]
        answer = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
        if not calls:
            _history[user_id] = _trim(hist)
            return answer
        responses = []
        for call in calls:
            name, args = call.get("name"), call.get("args") or {}
            log.info("Vosita: %s %s", name, args)
            try:
                result = await actions.run(name, args)
            except Exception as e:
                log.exception("Vosita xatosi")
                result = {"xato": str(e)}
            fr = {"name": name, "response": result}
            if call.get("id"):
                fr["id"] = call["id"]
            responses.append({"functionResponse": fr})
        hist.append({"role": "user", "parts": responses})

    _history[user_id] = _trim(hist)
    return "Kechirasiz, biroz chalkashib ketdim. Savolingizni qaytadan yozib yuborasizmi?"
