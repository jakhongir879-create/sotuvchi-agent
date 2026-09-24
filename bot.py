"""Telegram sotuvchi AI agent — ishga tushirish fayli."""
import asyncio
import csv
import html
import json
import logging
import os
from collections import defaultdict
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher, F  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.enums import ChatAction, ParseMode  # noqa: E402
from aiogram.filters import Command, CommandStart  # noqa: E402
from aiogram.types import Message  # noqa: E402

import agent  # noqa: E402
import gemini  # noqa: E402
import katalog  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

BOT_TOKEN = os.environ["BOT_TOKEN"]
MANAGER_CHAT_ID = os.getenv("MANAGER_CHAT_ID", "").strip()
MANAGER_CODE = os.getenv("MANAGER_CODE", "").strip()   # /menejer <kod> — menejer chatini bot orqali ulash
MANAGER_FILE = os.path.join(os.path.dirname(__file__), "menejer.txt")
if not MANAGER_CHAT_ID and os.path.exists(MANAGER_FILE):
    MANAGER_CHAT_ID = open(MANAGER_FILE).read().strip()
WELCOME = os.getenv("WELCOME_TEXT", "Assalomu alaykum! Men do'konimizning onlayn yordamchisiman. "
                    "Nima qidiryapsiz? Yozing, tanlashga yordam beraman.")
ORDERS_FILE = os.path.join(os.path.dirname(__file__), "buyurtmalar.csv")

_session = None
if os.getenv("TG_PROXY"):  # faqat proksi orqali ishlaydigan serverlar uchun
    from aiogram.client.session.aiohttp import AiohttpSession
    _session = AiohttpSession(proxy=os.environ["TG_PROXY"])
bot = Bot(BOT_TOKEN, session=_session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def fmt_sum(x) -> str:
    try:
        return f"{int(float(x)):,}".replace(",", " ") + " so'm"
    except (TypeError, ValueError):
        return str(x)


def next_order_no() -> str:
    n = 1
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, encoding="utf-8") as f:
            n = max(sum(1 for _ in f), 1)
    return f"{datetime.now():%m%d}-{n:03d}"


class Actions:
    """Agent chaqiradigan vositalarning Telegramdagi bajarilishi."""

    def __init__(self, msg: Message):
        self.msg = msg

    async def run(self, name: str, args: dict) -> dict:
        fn = getattr(self, name, None)
        if not fn:
            return {"xato": f"noma'lum vosita {name}"}
        return await fn(**args)

    def _customer(self) -> str:
        u = self.msg.from_user
        who = html.escape(u.full_name)
        link = f"@{u.username}" if u.username else f'<a href="tg://user?id={u.id}">profil</a>'
        return f"{who} ({link}, id <code>{u.id}</code>)"

    async def _notify(self, text: str) -> bool:
        if not MANAGER_CHAT_ID:
            log.warning("MANAGER_CHAT_ID yo'q, xabar menejerga yuborilmadi:\n%s", text)
            return False
        try:
            await bot.send_message(MANAGER_CHAT_ID, text, disable_web_page_preview=True)
            return True
        except Exception as e:
            log.error("Menejerga yuborib bo'lmadi: %s", e)
            return False

    async def mahsulot_korsatish(self, id: str, **_) -> dict:
        p = await katalog.find(id)
        if not p:
            return {"xato": "bunday ID li mahsulot yo'q"}
        cap = f"<b>{html.escape(p['nomi'])}</b>"
        if p.get("narx"):
            cap += f"\nNarxi: {fmt_sum(p['narx'])}"
        for key, label in [("razmerlar", "Razmerlar"), ("ranglar", "Ranglar")]:
            if p.get(key):
                cap += f"\n{label}: {html.escape(p[key])}"
        if p.get("rasm"):
            try:
                await self.msg.answer_photo(p["rasm"], caption=cap)
                return {"natija": "rasm yuborildi"}
            except Exception as e:
                log.warning("Rasm yuborilmadi (%s): %s", p["rasm"], e)
        await self.msg.answer(cap)
        return {"natija": "rasmsiz ma'lumot yuborildi"}

    async def buyurtma_berish(self, mahsulotlar, ism, telefon, yetkazish, jami,
                              manzil="", tolov="", izoh="", **_) -> dict:
        no = next_order_no()
        lines = []
        for m in mahsulotlar:
            line = f"• {html.escape(str(m.get('nomi')))} (ID {m.get('id')})"
            if m.get("variant"):
                line += f", {html.escape(str(m['variant']))}"
            line += f" — {m.get('soni', 1)} dona"
            if m.get("narx"):
                line += f" × {fmt_sum(m['narx'])}"
            lines.append(line)
        text = (f"🛒 <b>YANGI BUYURTMA #{no}</b>\n\n" + "\n".join(lines) +
                f"\n\n<b>Jami:</b> {fmt_sum(jami)}"
                f"\n<b>Ism:</b> {html.escape(ism)}\n<b>Telefon:</b> {html.escape(telefon)}"
                f"\n<b>Yetkazish:</b> {html.escape(yetkazish)}")
        if manzil:
            text += f"\n<b>Manzil:</b> {html.escape(manzil)}"
        if tolov:
            text += f"\n<b>To'lov:</b> {html.escape(tolov)}"
        if izoh:
            text += f"\n<b>Izoh:</b> {html.escape(izoh)}"
        text += f"\n\n<b>Mijoz:</b> {self._customer()}"
        sent = await self._notify(text)

        new_file = not os.path.exists(ORDERS_FILE)
        with open(ORDERS_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["raqam", "vaqt", "tg_id", "ism", "telefon", "mahsulotlar", "jami", "yetkazish",
                            "manzil", "tolov", "izoh"])
            w.writerow([no, datetime.now().isoformat(timespec="seconds"), self.msg.from_user.id, ism, telefon,
                        json.dumps(mahsulotlar, ensure_ascii=False), jami, yetkazish, manzil, tolov, izoh])
        log.info("Buyurtma #%s qabul qilindi (menejerga yuborildi: %s)", no, sent)
        return {"natija": "buyurtma qabul qilindi", "buyurtma_raqami": no}

    async def menejerni_chaqirish(self, sabab: str, **_) -> dict:
        ok = await self._notify(f"🙋 <b>Mijoz menejerni kutyapti</b>\n\n<b>Sabab:</b> {html.escape(sabab)}"
                                f"\n<b>Mijoz:</b> {self._customer()}")
        return {"natija": "menejerga xabar berildi" if ok else "menejer hozir mavjud emas, mijozdan telefon raqamini ol"}


@dp.message(CommandStart())
async def on_start(msg: Message):
    agent.reset(msg.from_user.id)
    await msg.answer(html.escape(WELCOME))


@dp.message(Command("yangi"))
async def on_new(msg: Message):
    agent.reset(msg.from_user.id)
    await msg.answer("Suhbat yangidan boshlandi. Qanday yordam bera olaman?")


@dp.message(Command("id"))
async def on_id(msg: Message):
    await msg.answer(f"Bu chat ID: <code>{msg.chat.id}</code>\nUni MANAGER_CHAT_ID ga yozing.")


@dp.message(Command("menejer"))
async def on_manager(msg: Message):
    global MANAGER_CHAT_ID
    code = (msg.text or "").split(maxsplit=1)[1:] or [""]
    if not MANAGER_CODE or code[0].strip() != MANAGER_CODE:
        return  # oddiy mijozlarga bu buyruq ko'rinmaydi
    MANAGER_CHAT_ID = str(msg.chat.id)
    with open(MANAGER_FILE, "w") as f:
        f.write(MANAGER_CHAT_ID)
    await msg.answer("✅ Bu chat menejer chati sifatida ulandi. Buyurtmalar shu yerga keladi.")


@dp.message(F.text & (F.chat.type == "private"))
async def on_text(msg: Message):
    uid = msg.from_user.id
    log.info("Xabar %s (%s): %s", uid, msg.from_user.full_name, msg.text[:80])
    async with _locks[uid]:
        typing = asyncio.create_task(_keep_typing(msg.chat.id))
        try:
            answer = await agent.reply(uid, msg.text, Actions(msg))
        except gemini.GeminiBusy:
            answer = "Kechirasiz, hozir tizim band. Bir daqiqadan keyin qayta yozib ko'ring 🙏"
        except Exception:
            log.exception("Javobda xato")
            answer = "Kechirasiz, xatolik yuz berdi. Iltimos, qayta yozib ko'ring."
        finally:
            typing.cancel()
    if answer:
        await msg.answer(html.escape(answer))


@dp.message(F.chat.type == "private")
async def on_other(msg: Message):
    await msg.answer("Hozircha faqat matnli xabarlarni tushunaman. Iltimos, savolingizni yozib yuboring 🙂")


async def _keep_typing(chat_id: int):
    try:
        while True:
            await bot.send_chat_action(chat_id, ChatAction.TYPING)
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass


def main():
    base = (os.getenv("WEBHOOK_BASE") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
    if not base:
        log.info("Polling rejimida ishga tushdi")
        asyncio.run(_polling())
        return

    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    secret = BOT_TOKEN.split(":")[-1][:20].replace("-", "x").replace("_", "x")
    path = f"/tg/{secret}"

    async def on_startup(_bot: Bot):
        await _bot.set_webhook(base + path, drop_pending_updates=False)
        log.info("Webhook o'rnatildi: %s/tg/***", base)

    dp.startup.register(on_startup)
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="ok"))
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=path)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", "10000")))


async def _polling():
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)


if __name__ == "__main__":
    main()
