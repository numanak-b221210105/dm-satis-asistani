"""İnsansı gönderim: görüldü, yazıyor... göstergesi, okuma hızına göre bekleme, uzun mesajı bölme."""
import asyncio
import random
import re

from app import meta
from app.config import get_settings

TYPING_REFRESH_SECONDS = 8.0


def typing_delay(text: str) -> float:
    s = get_settings()
    return max(s.min_delay, min(s.max_delay, len(text) / s.chars_per_second))


def split_message(text: str) -> list[str]:
    """Eşikten uzun mesajı ortaya en yakın cümle sonundan ikiye böler."""
    s = get_settings()
    text = text.strip()
    if len(text) <= s.split_threshold:
        return [text]
    cuts = [m.end() for m in re.finditer(r"[.!?…]+[\"')\]]*\s+|\n+", text)]
    cuts = [c for c in cuts if 0 < c < len(text)]
    if not cuts:
        return [text]
    cut = min(cuts, key=lambda c: abs(c - len(text) / 2))
    return [p for p in (text[:cut].strip(), text[cut:].strip()) if p]


async def _sleep_with_typing(token: str, user_id: str, seconds: float) -> None:
    remaining = seconds
    while remaining > 0:
        await meta.ig_sender_action(token, user_id, "typing_on")
        step = min(TYPING_REFRESH_SECONDS, remaining)
        await asyncio.sleep(step)
        remaining -= step


async def send_humanized(token: str, user_id: str, text: str, enabled: bool = True) -> list[str]:
    """Mesajı gönderir; gönderilen mesaj ID'lerini döner."""
    s = get_settings()
    parts = split_message(text)
    mids: list[str] = []
    humanize = enabled and s.humanizer_enabled
    if humanize:
        await meta.ig_sender_action(token, user_id, "mark_seen")
    for i, part in enumerate(parts):
        if humanize:
            if i > 0:
                await asyncio.sleep(random.uniform(s.split_gap_min, s.split_gap_max))
            await _sleep_with_typing(token, user_id, typing_delay(part))
        mid = await meta.ig_send_text(token, user_id, part)
        if mid:
            mids.append(mid)
    if humanize:
        await meta.ig_sender_action(token, user_id, "typing_off")
    return mids
