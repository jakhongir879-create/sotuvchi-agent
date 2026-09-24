"""Mahsulotlar katalogi: mahalliy mahsulotlar.csv yoki Google Sheets (CATALOG_URL) dan o'qiladi."""
import csv
import io
import logging
import os
import time

import httpx

log = logging.getLogger("katalog")

CATALOG_URL = os.getenv("CATALOG_URL", "").strip()
LOCAL_FILE = os.path.join(os.path.dirname(__file__), "mahsulotlar.csv")
REFRESH_SEC = 300

_cache: list[dict] = []
_loaded_at = 0.0


def _parse(text: str) -> list[dict]:
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        if row.get("id") and row.get("nomi"):
            rows.append(row)
    return rows


async def get() -> list[dict]:
    global _cache, _loaded_at
    if _cache and time.time() - _loaded_at < REFRESH_SEC:
        return _cache
    try:
        if CATALOG_URL:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
                r = await c.get(CATALOG_URL)
                r.raise_for_status()
                text = r.content.decode("utf-8-sig")
        else:
            with open(LOCAL_FILE, encoding="utf-8-sig") as f:
                text = f.read()
        _cache = _parse(text)
        _loaded_at = time.time()
        log.info("Katalog yuklandi: %d ta mahsulot", len(_cache))
    except Exception as e:  # eski nusxa bilan ishlashda davom etamiz
        log.error("Katalogni yuklab bo'lmadi: %s", e)
    return _cache


async def as_text() -> str:
    lines = []
    for p in await get():
        parts = [f"ID {p['id']}: {p['nomi']}"]
        for key, label in [("kategoriya", "turi"), ("narx", "narx"), ("razmerlar", "razmerlar"),
                           ("ranglar", "ranglar"), ("qoldiq", "qoldiq"), ("tavsif", "tavsif")]:
            if p.get(key):
                val = f"{p[key]} so'm" if key == "narx" else p[key]
                parts.append(f"{label}: {val}")
        parts.append("rasm bor" if p.get("rasm") else "rasm yo'q")
        lines.append(" | ".join(parts))
    return "\n".join(lines) or "(katalog bo'sh)"


async def find(pid: str) -> dict | None:
    for p in await get():
        if p["id"] == str(pid).strip():
            return p
    return None
