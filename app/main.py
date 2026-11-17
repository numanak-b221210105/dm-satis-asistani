"""DM Satış Asistanı — çok müşterili Instagram DM satış botu (FastAPI)."""
import asyncio
import json
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import exists, select

from app import agent, humanizer, meta
from app.admin import router as admin_router
from app.config import get_settings
from app.crypto import decrypt
from app.maintenance import maintenance_loop
from app.db import (Conversation, Message, Product, SentMessage, SessionLocal, Tenant, get_history,
                    get_or_create_conversation, init_db, tenant_by_ig)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("dm-asistan")

_locks: dict[tuple[int, str], asyncio.Lock] = defaultdict(asyncio.Lock)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().auto_create_tables:
        await init_db()
    task = asyncio.create_task(maintenance_loop()) if get_settings().run_maintenance else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="DM Satış Asistanı", lifespan=lifespan)
app.include_router(admin_router)


@app.get("/health")
async def health():
    return {"ok": True}


# ---------- Webhook ayrıştırma ----------

@dataclass
class IncomingEvent:
    account_id: str     # Esnafın IG hesap ID'si (webhook entry.id)
    customer_id: str
    mid: str
    text: str
    is_echo: bool       # Esnaf tarafından gönderilen (bot veya elle) mesaj
    images: list[str] = field(default_factory=list)


ATTACHMENT_NOTES = {
    "audio": "[Müşteri sesli mesaj gönderdi.]",
    "video": "[Müşteri video gönderdi.]",
    "ig_reel": "[Müşteri bir Reels paylaştı.]",
    "reel": "[Müşteri bir Reels paylaştı.]",
    "share": "[Müşteri bir gönderi paylaştı.]",
    "story_mention": "[Müşteri hikayesinde işletmeden bahsetti.]",
}


def parse_events(payload: dict) -> list[IncomingEvent]:
    out: list[IncomingEvent] = []
    if payload.get("object") not in ("instagram", "page"):
        return out
    for entry in payload.get("entry", []):
        account_id = str(entry.get("id", ""))
        for ev in entry.get("messaging", []):
            msg = ev.get("message") or {}
            if not msg or msg.get("is_deleted") or not msg.get("mid"):
                continue
            echo = bool(msg.get("is_echo"))
            customer = (ev.get("recipient") if echo else ev.get("sender")) or {}
            text = (msg.get("text") or "").strip()
            images, notes = [], []
            for att in msg.get("attachments") or []:
                url = (att.get("payload") or {}).get("url")
                if att.get("type") == "image" and url:
                    images.append(url)
                else:
                    notes.append(ATTACHMENT_NOTES.get(att.get("type"), "[Müşteri desteklenmeyen bir içerik gönderdi.]"))
            if (msg.get("reply_to") or {}).get("story"):
                notes.append("[Bu mesaj işletmenin bir hikayesine yanıt olarak geldi.]")
            if images and not text:
                text = "[Müşteri görsel gönderdi.]"
            text = " ".join([text, *notes]).strip()
            if customer.get("id") and text:
                out.append(IncomingEvent(account_id, str(customer["id"]), msg["mid"], text, echo, images))
    return out


# ---------- Webhook uç noktaları ----------

@app.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(mode: str = Query(None, alias="hub.mode"),
                         token: str = Query(None, alias="hub.verify_token"),
                         challenge: str = Query(None, alias="hub.challenge")):
    if mode == "subscribe" and token == get_settings().meta_verify_token:
        return challenge
    raise HTTPException(status_code=403, detail="Doğrulama başarısız")


@app.post("/webhook")
async def receive_webhook(request: Request, background: BackgroundTasks,
                          x_hub_signature_256: str | None = Header(None)):
    body = await request.body()
    if not meta.verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Geçersiz imza")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Geçersiz JSON")
    for ev in parse_events(payload):
        background.add_task(handle_event, ev)
    return {"status": "ok"}


# ---------- İşleme ----------

async def handle_event(ev: IncomingEvent) -> None:
    try:
        async with SessionLocal() as s:
            tenant = await tenant_by_ig(s, ev.account_id)
        if tenant is None or not tenant.active or not tenant.ig_token_enc:
            log.info("Kayıtlı/aktif olmayan hesap için olay atlandı: %s", ev.account_id)
            return
        lock = _locks[(tenant.id, ev.customer_id)]

        if ev.is_echo:
            # Bot gönderimi kilit içinde bitip mid kaydedilene kadar bekle; yoksa kendi mesajını esnafınki sanabilir.
            async with lock, SessionLocal() as s:
                if await s.scalar(select(exists().where(Message.mid == ev.mid))):
                    return
                conv = await get_or_create_conversation(s, tenant.id, ev.customer_id)
                await _handle_echo(s, ev, conv)
            return

        async with SessionLocal() as s:
            if await s.scalar(select(exists().where(Message.mid == ev.mid))):
                return  # tekrar gelen webhook
            conv = await get_or_create_conversation(s, tenant.id, ev.customer_id)
            msg = Message(conversation_id=conv.id, role="user", content=ev.text, mid=ev.mid, images=ev.images)
            s.add(msg)
            await s.commit()
            msg_id = msg.id

        # Müşteri art arda yazıyorsa son mesajı bekle (tek ve toplu cevap)
        await asyncio.sleep(get_settings().debounce_seconds)
        async with lock:
            await _reply(tenant, conv.id, msg_id)
    except Exception:
        log.exception("Olay işlenemedi: %s", ev)


async def _handle_echo(s, ev: IncomingEvent, conv) -> None:
    """Esnafın hesabından giden mesaj. Bot göndermediyse esnaf elle yazmıştır → bot o sohbette susar."""
    if await s.get(SentMessage, ev.mid):
        return
    s.add(Message(conversation_id=conv.id, role="staff", content=ev.text, mid=ev.mid))
    if not conv.bot_paused:
        conv.bot_paused = True
        conv.paused_reason = "esnaf_yazdi"
        log.info("Esnaf sohbete dahil oldu, bot durdu (conv=%s)", conv.id)
    await s.commit()


async def _reply(tenant: Tenant, conversation_id: int, msg_id: int) -> None:
    s_cfg = get_settings()
    async with SessionLocal() as s:
        tenant = await s.get(Tenant, tenant.id)
        conv = await s.get(Conversation, conversation_id)
        if conv.bot_paused:
            return
        # Daha yeni bir müşteri mesajı varsa onu işleyen görev cevap verecek;
        # bu mesajdan sonra zaten bir cevap gönderildiyse tekrar cevap verme.
        newer = await s.scalar(select(exists().where(
            Message.conversation_id == conversation_id, Message.id > msg_id,
            Message.role.in_(["user", "assistant", "staff"]))))
        if newer:
            return
        if conv.customer_username is None:
            conv.customer_username = await meta.ig_get_username(decrypt(tenant.ig_token_enc), conv.customer_id)
            await s.commit()
        history = await get_history(s, conversation_id, s_cfg.history_limit)
        products = list(await s.scalars(select(Product).where(Product.tenant_id == tenant.id)))

    runner = agent.ToolRunner(tenant=tenant, conversation=conv)
    try:
        reply = await agent.generate_reply(tenant, products, history, runner)
    except Exception:
        log.exception("LLM hatası (tenant=%s)", tenant.id)
        await meta.whatsapp_notify(tenant.notify_whatsapp,
                                   f"⚠️ Asistan hata verdi, bir müşteri cevapsız kalmış olabilir ({runner.who}).")
        return
    if not reply:
        return

    token = decrypt(tenant.ig_token_enc)
    mids = await humanizer.send_humanized(token, conv.customer_id, reply, enabled=tenant.humanizer_enabled)
    async with SessionLocal() as s:
        for mid in mids:
            s.add(SentMessage(mid=mid))
        s.add(Message(conversation_id=conversation_id, role="assistant", content=reply))
        await s.commit()
