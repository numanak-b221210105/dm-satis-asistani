"""Periyodik bakım işleri: Instagram token yenileme."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from app import meta
from app.crypto import decrypt, encrypt
from app.db import SessionLocal, Tenant

log = logging.getLogger(__name__)
REFRESH_BEFORE = timedelta(days=10)   # Bitişe 10 günden az kalan token'lar yenilenir
WARN_BEFORE = timedelta(days=3)       # Yenilenemezse ve 3 günden az kaldıysa esnaf uyarılır
INTERVAL_SECONDS = 12 * 3600


async def refresh_expiring_tokens(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    stats = {"yenilendi": 0, "hata": 0}
    async with SessionLocal() as s:
        tenants = list(await s.scalars(select(Tenant).where(
            Tenant.active.is_(True), Tenant.ig_token_enc.is_not(None),
            or_(Tenant.ig_token_expires_at.is_(None), Tenant.ig_token_expires_at < now + REFRESH_BEFORE))))
        for t in tenants:
            try:
                new_token, ttl = await meta.ig_refresh_token(decrypt(t.ig_token_enc))
                t.ig_token_enc = encrypt(new_token)
                t.ig_token_expires_at = now + timedelta(seconds=ttl)
                await s.commit()
                stats["yenilendi"] += 1
            except Exception:
                await s.rollback()
                stats["hata"] += 1
                log.exception("Token yenilenemedi (tenant=%s)", t.id)
                exp = t.ig_token_expires_at
                if exp is not None and exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp is not None and exp < now + WARN_BEFORE:
                    await meta.whatsapp_notify(
                        t.notify_whatsapp,
                        f"⚠️ {t.name}: Instagram bağlantınızın süresi dolmak üzere. Asistanın çalışmaya devam etmesi "
                        f"için panelden Instagram hesabınızı yeniden bağlayın.")
    if tenants:
        log.info("Token yenileme: %s", stats)
    return stats


async def maintenance_loop() -> None:
    while True:
        try:
            await refresh_expiring_tokens()
        except Exception:
            log.exception("Bakım döngüsü hatası")
        await asyncio.sleep(INTERVAL_SECONDS)
