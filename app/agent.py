"""LangChain + OpenAI satış ajanı. Araç şemaları her esnafın sipariş alanlarına göre dinamik üretilir."""
import logging
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app import languages as L
from app import meta
from app.config import get_settings
from app.whatsapp_link import wa_link
from app.db import Conversation, Handoff, Order, Product, SessionLocal, Tenant, UsageLog
from app.prompts import system_prompt

log = logging.getLogger(__name__)
MAX_TOOL_ROUNDS = 3


def build_tools(tenant: Tenant) -> list[dict]:
    """OpenAI function-calling şemaları. siparis_olustur'un alanları esnafın order_fields ayarından gelir."""
    lang_prop = {"type": "string", "description": "Müşterinin yazdığı dilin ISO 639-1 kodu (tr, en, sr, ro...)"}
    props = {"urun_adi": {"type": "string", "description": "Katalogdaki tam ürün adı (katalogdaki haliyle)"},
             "musteri_dili": lang_prop,
             "ozet": {"type": "string", "description": "Siparişin işletme sahibinin dilinde kısa özeti / ek notlar"}}
    required = ["urun_adi", "musteri_dili"]
    for f in tenant.order_fields:
        props[f["key"]] = {"type": "string", "description": f["label"]}
        if f.get("required"):
            required.append(f["key"])
    tools = [
        {"type": "function", "function": {
            "name": "siparis_olustur",
            "description": "Ürün ve zorunlu bilgiler tamamlanıp müşteri onay verdiğinde sipariş oluşturur "
                           "ve işletme sahibine WhatsApp ile iletir.",
            "parameters": {"type": "object", "properties": props, "required": required},
        }},
        {"type": "function", "function": {
            "name": "insana_aktar",
            "description": "Cevaplanamayan soru, şikayet, ısrar veya yetkili talebinde sohbeti işletme "
                           "sahibine aktarır ve acil WhatsApp bildirimi gönderir.",
            "parameters": {"type": "object", "properties": {
                "sebep": {"type": "string", "description": "Aktarma sebebi ve müşterinin talebinin özeti "
                                                         "(işletme sahibinin dilinde)"},
                "musteri_dili": lang_prop},
                "required": ["sebep", "musteri_dili"]},
        }},
    ]
    if tenant.customer_whatsapp:
        tools.append({"type": "function", "function": {
            "name": "whatsappa_yonlendir",
            "description": "Satıcının fikri/kararı gereken durumlarda (özel ölçü, pazarlık, toptan, katalog dışı ürün, "
                           "ürün yorumu, bilinmeyen soru) müşteriye satıcının WhatsApp hattı için hazır mesajlı bir "
                           "bağlantı üretir. Dönen bağlantıyı müşteriye aynen ilet.",
            "parameters": {"type": "object", "properties": {
                "konu": {"type": "string", "description": "Konunun işletme sahibinin dilinde kısa özeti"},
                "on_mesaj": {"type": "string", "description": "Müşterinin WhatsApp'ta göndereceği hazır mesaj, "
                                                             "MÜŞTERİNİN DİLİNDE, birinci tekil şahıs, 1-2 cümle"},
                "musteri_dili": lang_prop},
                "required": ["konu", "on_mesaj", "musteri_dili"]},
        }})
    return tools


@dataclass
class ToolRunner:
    tenant: Tenant
    conversation: Conversation
    handed_off: bool = False
    orders: list[int] = field(default_factory=list)

    @property
    def who(self) -> str:
        c = self.conversation
        return f"@{c.customer_username}" if c.customer_username else f"IG ID {c.customer_id}"

    @property
    def language(self) -> str | None:
        return self.conversation.language

    async def _remember_language(self, code) -> None:
        code = str(code or "").strip().lower()[:8]
        if not code or code == self.conversation.language:
            return
        self.conversation.language = code
        async with SessionLocal() as s:
            conv = await s.get(Conversation, self.conversation.id)
            if conv is not None:
                conv.language = code
                await s.commit()

    def _lang_line(self) -> str:
        own = self.tenant.owner_language or "tr"
        if not self.language or self.language == own:
            return f"Dil: {L.label(self.language or own)}"
        return f"Dil: {L.label(self.language)} — müşteriye bu dilde yazın"

    async def run(self, name: str, args: dict) -> str:
        await self._remember_language(args.pop("musteri_dili", None))
        if name == "siparis_olustur":
            return await self.siparis_olustur(args)
        if name == "insana_aktar":
            return await self.insana_aktar(args.get("sebep", "belirtilmedi"))
        if name == "whatsappa_yonlendir" and self.tenant.customer_whatsapp:
            return await self.whatsappa_yonlendir(args.get("konu", ""), args.get("on_mesaj", ""))
        return f"Bilinmeyen araç: {name}"

    async def siparis_olustur(self, args: dict) -> str:
        product = str(args.pop("urun_adi", "")).strip()
        summary = str(args.pop("ozet", "") or "").strip()
        missing = [f["label"] for f in self.tenant.order_fields
                   if f.get("required") and not str(args.get(f["key"], "")).strip()]
        if not product or missing:
            return "Eksik bilgi var, sipariş oluşturulmadı. Müşteriden şunları al: " + ", ".join(
                (["ürün"] if not product else []) + missing)
        labels = {f["key"]: f["label"] for f in self.tenant.order_fields}
        details = {k: str(v) for k, v in args.items() if k in labels and str(v).strip()}

        async with SessionLocal() as s:
            order = Order(tenant_id=self.tenant.id, conversation_id=self.conversation.id,
                          product_name=product, details=details)
            s.add(order)
            await s.commit()
            lines = [f"🛍️ YENİ SİPARİŞ #{order.id} — {self.tenant.name}",
                     f"Müşteri: {self.who}", self._lang_line(), f"Ürün: {product}"]
            lines += [f"{labels[k]}: {v}" for k, v in details.items()]
            if summary:
                lines.append(f"Not: {summary}")
            lines.append("Müşteriye Instagram'dan dönüş yapın.")
            order.notified = await meta.whatsapp_notify(self.tenant.notify_whatsapp, "\n".join(lines))
            await s.commit()
            self.orders.append(order.id)
        result = f"Sipariş #{order.id} oluşturuldu ve işletmeye iletildi."
        if self.tenant.customer_whatsapp:
            parts = [f"{L.order_word(self.language)} #{order.id}", product, *details.values()]
            link = wa_link(self.tenant.customer_whatsapp, "\n".join(parts))
            result += (f" Müşteri siparişini WhatsApp'tan da iletebilir, bu bağlantıyı aynen paylaş: {link}")
        return result

    async def whatsappa_yonlendir(self, konu: str, on_mesaj: str) -> str:
        text = on_mesaj.strip() or konu.strip()
        if self.conversation.customer_username:
            text += f"\n(Instagram: @{self.conversation.customer_username})"
        link = wa_link(self.tenant.customer_whatsapp, text)
        if self.tenant.notify_whatsapp:
            await meta.whatsapp_notify(
                self.tenant.notify_whatsapp,
                f"↪️ WHATSAPP'A YÖNLENDİRİLDİ — {self.tenant.name}\nMüşteri: {self.who}\n{self._lang_line()}\n"
                f"Konu: {konu}\nMüşteri birazdan {self.tenant.customer_whatsapp} hattına yazabilir.")
        return f"Bağlantı hazır. Müşteriye satıcının WhatsApp'tan yardımcı olacağını söyle ve bunu aynen ver: {link}"

    async def insana_aktar(self, sebep: str) -> str:
        async with SessionLocal() as s:
            s.add(Handoff(tenant_id=self.tenant.id, conversation_id=self.conversation.id, reason=sebep))
            conv = await s.get(Conversation, self.conversation.id)
            conv.bot_paused = True
            conv.paused_reason = "insana_aktar"
            await s.commit()
        await meta.whatsapp_notify(
            self.tenant.notify_whatsapp,
            f"🚨 MÜDAHALE GEREKİYOR — {self.tenant.name}\nMüşteri: {self.who}\n{self._lang_line()}\nSebep: {sebep}\n"
            f"Asistan bu sohbette durdu. Instagram'dan müşteriye yazabilirsiniz.",
        )
        self.handed_off = True
        return "Sohbet işletme sahibine aktarıldı. Müşteriye bir yetkilinin birazdan yazacağını söyle."


def build_llm(tenant: Tenant):
    s = get_settings()
    return ChatOpenAI(model=s.openai_model, temperature=s.openai_temperature,
                      api_key=s.openai_api_key).bind_tools(build_tools(tenant))


def to_lc(history, with_images: bool = True) -> list[BaseMessage]:
    """Geçmişi LangChain mesajlarına çevirir. Instagram görsel URL'leri bir süre sonra geçersizleştiği için
    görseller yalnızca son cevaptan sonra gelen müşteri mesajlarında modele gönderilir."""
    last_reply = max((i for i, m in enumerate(history) if m.role != "user"), default=-1)
    out: list[BaseMessage] = []
    for i, m in enumerate(history):
        if m.role == "user":
            imgs = (m.images or []) if with_images and i > last_reply else []
            if imgs:
                out.append(HumanMessage(content=[{"type": "text", "text": m.content},
                                                 *[{"type": "image_url", "image_url": {"url": u}} for u in imgs]]))
            else:
                note = " [görsel gönderilmişti]" if m.images and "[Müşteri görsel" not in m.content else ""
                out.append(HumanMessage(m.content + note))
        elif m.role == "assistant":
            out.append(AIMessage(m.content))
        else:  # staff — esnafın elle yazdığı mesaj
            out.append(AIMessage(f"[İşletme yetkilisi yazdı] {m.content}"))
    return out


async def _log_usage(tenant: Tenant, runner: ToolRunner, ai: AIMessage) -> None:
    usage = getattr(ai, "usage_metadata", None) or {}
    if not usage:
        return
    try:
        async with SessionLocal() as s:
            s.add(UsageLog(tenant_id=tenant.id, conversation_id=runner.conversation.id,
                           model=get_settings().openai_model,
                           input_tokens=usage.get("input_tokens", 0), output_tokens=usage.get("output_tokens", 0)))
            await s.commit()
    except Exception:
        log.exception("Kullanım kaydı yazılamadı")


async def _run(llm, tenant, runner, messages: list[BaseMessage]) -> str:
    for _ in range(MAX_TOOL_ROUNDS + 1):
        ai: AIMessage = await llm.ainvoke(messages)
        await _log_usage(tenant, runner, ai)
        messages.append(ai)
        if not ai.tool_calls:
            return (ai.content or "").strip()
        for call in ai.tool_calls:
            log.info("[%s] Araç: %s %s", tenant.name, call["name"], call["args"])
            result = await runner.run(call["name"], dict(call["args"]))
            messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
    langs = tenant.languages or L.DEFAULT_LANGUAGES
    return L.fallback_reply(runner.language, "en" if "en" in langs else langs[0])


async def generate_reply(tenant: Tenant, products: list[Product], history, runner: ToolRunner, llm=None) -> str:
    llm = llm or build_llm(tenant)
    system = SystemMessage(system_prompt(tenant, products))
    has_images = any(m.role == "user" and m.images for m in history)
    try:
        return await _run(llm, tenant, runner, [system, *to_lc(history)])
    except Exception:
        if not has_images or runner.orders or runner.handed_off:
            raise
        # Görsel indirilemediyse (süresi dolmuş URL vb.) görselsiz tekrar dene
        log.warning("Görselli istek başarısız, görselsiz tekrar deneniyor (tenant=%s)", tenant.id, exc_info=True)
        return await _run(llm, tenant, runner, [system, *to_lc(history, with_images=False)])
