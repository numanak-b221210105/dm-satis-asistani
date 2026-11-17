import asyncio, hashlib, hmac, json, itertools
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app import agent, humanizer, meta
from app.main import app, parse_events

H = {"X-Admin-Token": "adm"}
_mid = itertools.count()


class FakeLLM:
    def __init__(self, script, seen=None): self.script, self.seen = list(script), seen
    async def ainvoke(self, messages):
        if self.seen is not None: self.seen.append(list(messages))
        return self.script.pop(0)


@pytest.fixture
def io(monkeypatch):
    log = {"ig": [], "wa": [], "tokens": []}
    async def ig_send(token, uid, text):
        log["ig"].append((uid, text)); log["tokens"].append(token); return f"bot-{next(_mid)}"
    async def ig_action(token, uid, a): pass
    async def wa(to, text): log["wa"].append((to, text)); return True
    async def uname(token, uid): return f"user_{uid}"
    monkeypatch.setattr(meta, "ig_send_text", ig_send)
    monkeypatch.setattr(meta, "ig_sender_action", ig_action)
    monkeypatch.setattr(meta, "whatsapp_notify", wa)
    monkeypatch.setattr(meta, "ig_get_username", uname)
    return log


def sign(body): return "sha256=" + hmac.new(b"testsecret", body, hashlib.sha256).hexdigest()


def post(c, account, sender, text, echo=False, mid=None):
    mid = mid or f"m-{next(_mid)}"
    m = {"mid": mid, "text": text}
    if echo: m["is_echo"] = True
    ev = {"sender": {"id": account if echo else sender}, "recipient": {"id": sender if echo else account},
          "timestamp": 1, "message": m}
    body = json.dumps({"object": "instagram", "entry": [{"id": account, "time": 1, "messaging": [ev]}]}).encode()
    return c.post("/webhook", content=body, headers={"X-Hub-Signature-256": sign(body)})


def make_tenant(c, name, ig_id, token, wa, fields=None, products=()):
    body = {"name": name, "sector": "test", "notify_whatsapp": wa}
    if fields: body["order_fields"] = fields
    t = c.post("/admin/tenants", json=body, headers=H).json()
    r = c.post(f"/admin/tenants/{t['id']}/instagram", json={"ig_account_id": ig_id, "access_token": token}, headers=H)
    assert r.status_code == 200, r.text
    if products:
        c.post(f"/admin/tenants/{t['id']}/products", json=list(products), headers=H)
    return t["id"]


def test_webhook_verify_and_signature():
    with TestClient(app) as c:
        assert c.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "9"}).text == "9"
        assert c.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "9"}).status_code == 403
        assert c.post("/webhook", content=b"{}", headers={"X-Hub-Signature-256": "sha256=00"}).status_code == 401
        assert c.get("/admin/tenants").status_code == 401


def test_parse_events_echo_direction():
    p = {"object": "instagram", "entry": [{"id": "ACC", "messaging": [
        {"sender": {"id": "CUS"}, "recipient": {"id": "ACC"}, "message": {"mid": "1", "text": "a"}},
        {"sender": {"id": "ACC"}, "recipient": {"id": "CUS"}, "message": {"mid": "2", "text": "b", "is_echo": True}}]}]}
    evs = parse_events(p)
    assert [(e.account_id, e.customer_id, e.is_echo) for e in evs] == [("ACC", "CUS", False), ("ACC", "CUS", True)]


def test_token_encrypted_at_rest():
    from app.db import SessionLocal, Tenant
    with TestClient(app) as c:
        tid = make_tenant(c, "Sifre Test", "IG-ENC", "gizli-token-123", "905000000000")
        async def get():
            async with SessionLocal() as s: return (await s.get(Tenant, tid)).ig_token_enc
        enc = asyncio.run(get())
        assert "gizli-token-123" not in enc
        assert c.get("/admin/tenants", headers=H).json()[-1]["instagram"]["bagli"] is True
        # aynı IG hesabı ikinci esnafa bağlanamaz
        t2 = c.post("/admin/tenants", json={"name": "x"}, headers=H).json()
        assert c.post(f"/admin/tenants/{t2['id']}/instagram", json={"ig_account_id": "IG-ENC", "access_token": "t"}, headers=H).status_code == 409


def test_multi_tenant_custom_fields_order(io, monkeypatch):
    """Giyim mağazası (ölçü alanları) ve kafe (farklı alanlar) aynı anda; her biri kendi token/numarası/kataloğuyla."""
    seen = []
    scripts = {
        "Butik": [AIMessage("", tool_calls=[{"name": "siparis_olustur", "id": "1", "args": {
                      "urun_adi": "Deri Ceket", "boy": "180", "kilo": "82", "gogus": "104", "adres": "Sakarya"}}]),
                  AIMessage("Siparişiniz alındı!")],
        "Kafe": [AIMessage("Pastamız 500 TL, kaç kişilik olsun?")],
    }
    monkeypatch.setattr(agent, "build_llm", lambda t: FakeLLM(scripts[t.name], seen))
    with TestClient(app) as c:
        b = make_tenant(c, "Butik", "IG-B", "tok-b", "905111111111",
                        fields=[{"key": "boy", "label": "Boy (cm)", "required": True},
                                {"key": "kilo", "label": "Kilo (kg)", "required": True},
                                {"key": "gogus", "label": "Göğüs (cm)", "required": True},
                                {"key": "adres", "label": "Adres", "required": True}],
                        products=[{"name": "Deri Ceket", "price": "4500 TL", "variants": "S-XL"}])
        k = make_tenant(c, "Kafe", "IG-K", "tok-k", "905222222222",
                        products=[{"name": "Doğum Günü Pastası", "price": "500 TL"}])
        post(c, "IG-B", "c1", "ceket istiyorum")
        post(c, "IG-K", "c2", "pasta fiyatı?")
        orders_b = c.get(f"/admin/tenants/{b}/orders", headers=H).json()
        orders_k = c.get(f"/admin/tenants/{k}/orders", headers=H).json()
    assert orders_b[0]["detaylar"] == {"boy": "180", "kilo": "82", "gogus": "104", "adres": "Sakarya"}
    assert orders_k == []
    assert io["wa"][0][0] == "905111111111" and "Göğüs (cm): 104" in io["wa"][0][1]
    assert ("c2", "Pastamız 500 TL, kaç kişilik olsun?") in io["ig"] and set(io["tokens"]) == {"tok-b", "tok-k"}
    prompts = [m[0].content for m in seen]
    assert any("Deri Ceket" in p and "Pasta" not in p for p in prompts)
    assert any("Pasta" in p and "Deri Ceket" not in p for p in prompts)


def test_missing_required_fields_blocks_order(io):
    from app.db import Tenant, Conversation
    t = Tenant(id=99, name="X", order_fields=[{"key": "adres", "label": "Adres", "required": True}], notify_whatsapp="1")
    r = agent.ToolRunner(t, Conversation(id=1, tenant_id=99, customer_id="c"))
    out = asyncio.run(r.run("siparis_olustur", {"urun_adi": "Ürün"}))
    assert "Adres" in out and io["wa"] == []


def test_staff_reply_pauses_bot_but_bot_echo_does_not(io, monkeypatch):
    calls = []
    def build(t):
        calls.append(1); return FakeLLM([AIMessage("Merhaba, nasıl yardımcı olabilirim?")])
    monkeypatch.setattr(agent, "build_llm", build)
    with TestClient(app) as c:
        tid = make_tenant(c, "Echo Test", "IG-E", "tok-e", "905333333333")
        post(c, "IG-E", "c9", "selam")
        assert len(calls) == 1
        # botun kendi mesajının echo'su gelir → bot durmamalı
        from app.db import SessionLocal, SentMessage
        from sqlalchemy import select
        async def mids():
            async with SessionLocal() as s: return list(await s.scalars(select(SentMessage.mid)))
        post(c, "IG-E", "c9", "Merhaba, nasıl yardımcı olabilirim?", echo=True, mid=asyncio.run(mids())[-1])
        assert c.get(f"/admin/tenants/{tid}/paused", headers=H).json() == []
        # esnaf elle yazar → bot durur
        post(c, "IG-E", "c9", "Ben Ahmet, buradayım", echo=True, mid="staff-1")
        paused = c.get(f"/admin/tenants/{tid}/paused", headers=H).json()
        assert paused[0]["sebep"] == "esnaf_yazdi"
        post(c, "IG-E", "c9", "tamam")
        assert len(calls) == 1  # bot cevap vermedi
        c.post(f"/admin/conversations/{paused[0]['conversation_id']}/resume", headers=H)
        monkeypatch.setattr(agent, "build_llm", lambda t: (calls.append(1), FakeLLM([AIMessage("Buyrun")]))[1])
        post(c, "IG-E", "c9", "fiyat?")
        assert len(calls) == 2


def test_handoff_notifies_and_pauses(io, monkeypatch):
    monkeypatch.setattr(agent, "build_llm", lambda t: FakeLLM([
        AIMessage("", tool_calls=[{"name": "insana_aktar", "id": "1", "args": {"sebep": "İade talebi"}}]),
        AIMessage("Sizi yetkiliye aktardım.")]))
    with TestClient(app) as c:
        tid = make_tenant(c, "Handoff", "IG-H", "tok-h", "905444444444")
        post(c, "IG-H", "c5", "iade istiyorum")
        assert c.get(f"/admin/tenants/{tid}/paused", headers=H).json()[0]["sebep"] == "insana_aktar"
    assert io["wa"][0][0] == "905444444444" and "İade talebi" in io["wa"][0][1]


def test_unknown_account_and_duplicates_ignored(io, monkeypatch):
    calls = []
    monkeypatch.setattr(agent, "build_llm", lambda t: (calls.append(1), FakeLLM([AIMessage("ok")]))[1])
    with TestClient(app) as c:
        make_tenant(c, "Dup", "IG-D", "tok-d", "905555555555")
        post(c, "IG-YOK", "c", "merhaba")
        post(c, "IG-D", "c", "merhaba", mid="same")
        post(c, "IG-D", "c", "merhaba", mid="same")
    assert len(calls) == 1


def test_debounce_answers_once_for_burst(io, monkeypatch):
    """Müşteri art arda 3 mesaj atarsa tek cevap verilir ve LLM son mesajı görür."""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "debounce_seconds", 0.3)
    seen = []
    monkeypatch.setattr(agent, "build_llm", lambda t: FakeLLM([AIMessage("Tek cevap")], seen))
    from app.main import IncomingEvent, handle_event
    with TestClient(app) as c:
        make_tenant(c, "Burst", "IG-X", "tok-x", "905666666666")
    async def burst():
        async def send(i, t):
            await asyncio.sleep(i * 0.05)  # gerçekçi: mesajlar arasında kısa aralık
            await handle_event(IncomingEvent("IG-X", "cb", f"b{i}", t, False))
        await asyncio.gather(*[send(i, t) for i, t in enumerate(["selam", "ceket var mı", "siyah"])])
    asyncio.run(burst())
    assert [t for u, t in io["ig"] if u == "cb"] == ["Tek cevap"]
    assert seen[0][-1].content == "siyah"


def test_humanizer():
    assert humanizer.typing_delay("a" * 30) == 2.0
    long = "Bu ürün hakiki deridir ve astarı pamukludur. " * 4 + "Size L beden uygun olur. Kargo ekibimizce teyit edilecek. " * 2
    parts = humanizer.split_message(long)
    assert len(parts) == 2 and parts[0].endswith(".")


def test_image_parsing_and_vision(io, monkeypatch):
    p = {"object": "instagram", "entry": [{"id": "ACC", "messaging": [
        {"sender": {"id": "C"}, "recipient": {"id": "ACC"}, "message": {"mid": "i1",
         "attachments": [{"type": "image", "payload": {"url": "https://cdn/x.jpg"}}, {"type": "audio", "payload": {"url": "a"}}]}}]}]}
    ev = parse_events(p)[0]
    assert ev.images == ["https://cdn/x.jpg"] and "sesli mesaj" in ev.text

    from app.db import Message
    hist = [Message(role="user", content="eski", images=["https://cdn/old.jpg"]),
            Message(role="assistant", content="cevap"),
            Message(role="user", content="bu var mı", images=["https://cdn/new.jpg"])]
    lc = agent.to_lc(hist)
    assert isinstance(lc[0].content, str) and "görsel gönderilmişti" in lc[0].content   # eski görsel URL'si gönderilmez
    assert lc[2].content[1]["image_url"]["url"] == "https://cdn/new.jpg"
    assert isinstance(agent.to_lc(hist, with_images=False)[2].content, str)


def test_vision_failure_falls_back_to_text(io, monkeypatch):
    class Flaky:
        def __init__(self): self.calls = []
        async def ainvoke(self, messages):
            self.calls.append(messages)
            if any(isinstance(m.content, list) for m in messages):
                raise RuntimeError("image url expired")
            return AIMessage("Görseli açamadım, ürün adını yazar mısınız?")
    llm = Flaky()
    from app.db import Message, Tenant, Conversation, DEFAULT_ORDER_FIELDS
    t = Tenant(id=1, name="T", order_fields=DEFAULT_ORDER_FIELDS)
    r = agent.ToolRunner(t, Conversation(id=1, tenant_id=1, customer_id="c"))
    out = asyncio.run(agent.generate_reply(t, [], [Message(role="user", content="x", images=["u"])], r, llm=llm))
    assert "Görseli açamadım" in out and len(llm.calls) == 2


def test_usage_logged(io, monkeypatch):
    ai = AIMessage("Merhaba", usage_metadata={"input_tokens": 120, "output_tokens": 15, "total_tokens": 135})
    monkeypatch.setattr(agent, "build_llm", lambda t: FakeLLM([ai]))
    with TestClient(app) as c:
        tid = make_tenant(c, "Usage", "IG-U", "tok-u", "905777777777")
        post(c, "IG-U", "cu", "selam")
        u = c.get(f"/admin/tenants/{tid}/usage", headers=H).json()
    assert u["input_tokens"] == 120 and u["output_tokens"] == 15 and u["mesaj_sayisi"] == 1


def test_token_refresh(io, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app import maintenance
    from app.crypto import decrypt
    from app.db import SessionLocal, Tenant
    calls = []
    async def refresh(tok):
        calls.append(tok)
        if tok == "bozuk": raise RuntimeError("expired")
        return tok + "-yeni", 5184000
    monkeypatch.setattr(meta, "ig_refresh_token", refresh)
    now = datetime.now(timezone.utc)
    with TestClient(app) as c:
        a = make_tenant(c, "Yakin", "IG-R1", "eski", "905800000001")
        b = make_tenant(c, "Uzak", "IG-R2", "uzak", "905800000002")
        d = make_tenant(c, "Bozuk", "IG-R3", "bozuk", "905800000003")
        for tid, exp in [(a, now + timedelta(days=5)), (b, now + timedelta(days=50)), (d, now + timedelta(days=1))]:
            c.post(f"/admin/tenants/{tid}/instagram", headers=H, json={
                "ig_account_id": f"IG-R{[a, b, d].index(tid) + 1}", "access_token": ["eski", "uzak", "bozuk"][[a, b, d].index(tid)],
                "expires_at": exp.isoformat()})
    stats = asyncio.run(maintenance.refresh_expiring_tokens(now))
    async def tok(tid):
        async with SessionLocal() as s: return decrypt((await s.get(Tenant, tid)).ig_token_enc)
    assert "uzak" not in calls                       # süresi uzak olan yenilenmez
    assert asyncio.run(tok(a)) == "eski-yeni"
    assert stats["hata"] >= 1 and any(to == "905800000003" and "süresi dolmak" in t for to, t in io["wa"])


# ---------------- Çok dilli destek ----------------

def test_language_settings_validation():
    with TestClient(app) as c:
        bad = c.post("/admin/tenants", json={"name": "X", "languages": ["tr", "klingon"]}, headers=H)
        assert bad.status_code == 422
        t = c.post("/admin/tenants", json={"name": "Dilli", "languages": ["tr", "sr", "ro", "en", "sr"]}, headers=H).json()
        assert t["languages"] == ["tr", "sr", "ro", "en"] and t["owner_language"] == "tr"
        assert any(l["kod"] == "sr" for l in c.get("/admin/languages", headers=H).json())


def test_prompt_and_tools_include_language_rules():
    from app.db import Tenant, DEFAULT_ORDER_FIELDS
    from app.prompts import system_prompt
    t = Tenant(name="V", order_fields=DEFAULT_ORDER_FIELDS, languages=["tr", "sr", "ro", "en"], owner_language="tr")
    p = system_prompt(t, [])
    assert "Srpski" in p and "Română" in p and "Kiril" in p and "kur çevirisi yapma" in p
    tools = {x["function"]["name"]: x["function"]["parameters"] for x in agent.build_tools(t)}
    assert "musteri_dili" in tools["siparis_olustur"]["required"] and "musteri_dili" in tools["insana_aktar"]["required"]


def test_serbian_order_notifies_owner_in_turkish_with_language(io, monkeypatch):
    script = [
        AIMessage("", tool_calls=[{"name": "siparis_olustur", "id": "1", "args": {
            "urun_adi": "Klasik Deri Ceket", "musteri_dili": "sr", "ozet": "Siyah renk istiyor, hediye paketi rica etti",
            "ad_soyad": "Marko Petrović", "telefon": "+381641234567", "adres": "Bulevar oslobođenja 12, Novi Sad"}}]),
        AIMessage("Hvala, Marko! Vaša porudžbina je primljena 🙏"),
    ]
    monkeypatch.setattr(agent, "build_llm", lambda t: FakeLLM(script))
    with TestClient(app) as c:
        tid = make_tenant(c, "Vizyon Test", "IG-SR", "tok-sr", "905900000000")
        c.patch(f"/admin/tenants/{tid}", json={"languages": ["tr", "sr", "ro", "en"]}, headers=H)
        post(c, "IG-SR", "marko", "Zdravo, želim crnu kožnu jaknu")
        orders = c.get(f"/admin/tenants/{tid}/orders", headers=H).json()
    wa = io["wa"][-1][1]
    assert "🇷🇸" in wa and "müşteriye bu dilde yazın" in wa
    assert "Not: Siyah renk istiyor" in wa and "Bulevar oslobođenja 12, Novi Sad" in wa   # adres çevrilmeden
    assert "musteri_dili" not in orders[0]["detaylar"]
    assert io["ig"][-1] == ("marko", "Hvala, Marko! Vaša porudžbina je primljena 🙏")
    from app.db import SessionLocal, Conversation
    from sqlalchemy import select
    async def lang():
        async with SessionLocal() as s:
            return (await s.scalar(select(Conversation).where(Conversation.customer_id == "marko"))).language
    assert asyncio.run(lang()) == "sr"


def test_romanian_handoff_and_fallback_reply_language(io, monkeypatch):
    from app.db import Tenant, Conversation, DEFAULT_ORDER_FIELDS
    loop_call = AIMessage("", tool_calls=[{"name": "insana_aktar", "id": "x",
                                          "args": {"sebep": "Müşteri iade istiyor", "musteri_dili": "ro"}}])
    class Loop:
        async def ainvoke(self, m): return loop_call
    with TestClient(app) as c:
        tid = make_tenant(c, "Ro Test", "IG-RO", "tok-ro", "905910000000")
    async def go():
        from app.db import SessionLocal, get_or_create_conversation
        async with SessionLocal() as s:
            t = await s.get(Tenant, tid)
            conv = await get_or_create_conversation(s, tid, "ioana")
        r = agent.ToolRunner(t, conv)
        return await agent.generate_reply(t, [], [], r, llm=Loop())
    out = asyncio.run(go())
    assert out.startswith("Am transmis")                       # araç turu sınırı → Romence yedek mesaj
    assert "🇷🇴" in io["wa"][0][1] and "Müşteri iade istiyor" in io["wa"][0][1]


# ---------------- Para birimi ve WhatsApp yönlendirme ----------------

def test_currency_in_prompt_and_catalog():
    from app.db import Tenant, Product, DEFAULT_ORDER_FIELDS
    from app.prompts import system_prompt
    from app.currencies import format_price
    assert format_price("120", "EUR") == "120 EUR" and format_price("$99", "EUR") == "$99" and "sorunuz" in format_price("", "EUR")
    t = Tenant(name="V", order_fields=DEFAULT_ORDER_FIELDS, currency="EUR")
    p = system_prompt(t, [Product(name="Ceket", price="250", in_stock=True)])
    assert "Tüm fiyatlar EUR cinsindendir" in p and "Fiyat: 250 EUR" in p
    with TestClient(app) as c:
        assert c.post("/admin/tenants", json={"name": "X", "currency": "XYZ"}, headers=H).status_code == 422


def test_whatsapp_tool_only_when_customer_number_set():
    from app.db import Tenant, DEFAULT_ORDER_FIELDS
    names = lambda t: [x["function"]["name"] for x in agent.build_tools(t)]
    assert "whatsappa_yonlendir" not in names(Tenant(name="A", order_fields=DEFAULT_ORDER_FIELDS))
    assert "whatsappa_yonlendir" in names(Tenant(name="B", order_fields=DEFAULT_ORDER_FIELDS, customer_whatsapp="905001112233"))


def test_order_gives_customer_whatsapp_link(io, monkeypatch):
    from urllib.parse import unquote
    seen = []
    script = [
        AIMessage("", tool_calls=[{"name": "siparis_olustur", "id": "1", "args": {
            "urun_adi": "Kürk Mont", "musteri_dili": "hr", "ad_soyad": "Ana Horvat", "telefon": "+385911234567",
            "adres": "Ilica 5, Zagreb"}}]),
        AIMessage("Hvala! Narudžbu možete poslati i na WhatsApp: https://wa.me/..."),
    ]
    monkeypatch.setattr(agent, "build_llm", lambda t: FakeLLM(script, seen))
    with TestClient(app) as c:
        tid = make_tenant(c, "WA Link", "IG-WL", "tok-wl", "905920000000")
        c.patch(f"/admin/tenants/{tid}", json={"customer_whatsapp": "905301112233", "languages": ["tr", "hr"]}, headers=H)
        post(c, "IG-WL", "ana", "Želim kupiti kaput")
    tool_result = [m for m in seen[1] if m.type == "tool"][0].content
    assert "https://wa.me/905301112233?text=" in tool_result
    text = unquote(tool_result.split("text=")[1])
    assert text.startswith("Narudžba #") and "Kürk Mont" in text and "Ilica 5, Zagreb" in text


def test_redirect_to_whatsapp_keeps_bot_active_and_notifies(io, monkeypatch):
    from urllib.parse import unquote
    seen = []
    script = [
        AIMessage("", tool_calls=[{"name": "whatsappa_yonlendir", "id": "1", "args": {
            "konu": "Özel ölçü ceket istiyor (kol boyu uzun)", "musteri_dili": "sr",
            "on_mesaj": "Zdravo, zanima me jakna po meri sa dužim rukavima."}}]),
        AIMessage("Za to je najbolje da pišete prodavcu na WhatsApp: https://wa.me/..."),
        AIMessage("Naravno, izvolite!"),
    ]
    shared = FakeLLM(script, seen)
    monkeypatch.setattr(agent, "build_llm", lambda t: shared)
    with TestClient(app) as c:
        tid = make_tenant(c, "Yonlendir", "IG-YN", "tok-yn", "905930000000")
        c.patch(f"/admin/tenants/{tid}", json={"customer_whatsapp": "905301112244"}, headers=H)
        post(c, "IG-YN", "petar", "Može li jakna po meri?")
        assert c.get(f"/admin/tenants/{tid}/paused", headers=H).json() == []   # bot susmaz
        post(c, "IG-YN", "petar", "Hvala, a koliko košta crna?")
    tool_result = [m for m in seen[0] if m.type == "tool"] or [m for m in seen[1] if m.type == "tool"]
    link_text = unquote(tool_result[0].content.split("text=")[1])
    assert link_text.startswith("Zdravo, zanima me jakna") and "@user_petar" in link_text
    assert any("WHATSAPP'A YÖNLENDİRİLDİ" in t and "Özel ölçü" in t for _, t in io["wa"])
    assert [t for u, t in io["ig"] if u == "petar"][-1] == "Naravno, izvolite!"


# ---------------- Kurulum sihirbazı ----------------

def test_onboarding_build_tenant():
    from app.onboarding import build_tenant, normalize_phone
    assert normalize_phone("+90 532 123 45 67") == "905321234567" and normalize_phone("0532 123 45 67") == "905321234567"
    t = build_tenant({"name": " Vizyon ", "sector": "giyim", "languages": "tr, sr, ro, hr", "currency": "eur",
                      "shipping": "Sırbistan ve Romanya'ya 5-7 gün, 15 EUR", "returns": "14 gün",
                      "tone": "samimi", "notify_whatsapp": "0532 111 22 33", "customer_whatsapp": "",
                      "extra_fields": "hediye paketi, fatura adresi"})
    keys = [f["key"] for f in t["order_fields"]]
    assert t["name"] == "Vizyon" and t["currency"] == "EUR" and t["languages"] == ["tr", "sr", "ro", "hr"]
    assert keys[:2] == ["beden", "boy"] and "hediye_paketi" in keys and keys[-3:] == ["ad_soyad", "telefon", "adres"]
    assert "Kargo: Sırbistan" in t["policies"] and t["customer_whatsapp"] is None and t["notify_whatsapp"] == "905321112233"


def test_onboarding_cli_end_to_end(monkeypatch, capsys):
    """Komut satırı sihirbazını gerçek API'ye karşı baştan sona çalıştırır."""
    import importlib, sys as _sys
    answers = iter(["Balkan Butik", "giyim", "Deri ceketler", "tr,sr,hr", "", "EUR", "Balkanlara 7 gün",
                    "14 gün iade", "Havale", "", "0532 999 88 77", "0532 999 88 66", "", "e"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    with TestClient(app) as c:
        import httpx
        monkeypatch.setattr(httpx, "get", lambda url, headers=None: c.get(url.replace("http://x", ""), headers=headers))
        monkeypatch.setattr(httpx, "post", lambda url, headers=None, json=None: c.post(url.replace("http://x", ""), headers=headers, json=json))
        monkeypatch.setattr(_sys, "argv", ["sihirbaz", "http://x", "adm"])
        spec = importlib.util.spec_from_file_location("sihirbaz", "scripts/kurulum_sihirbazi.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        mod.main()
        t = [x for x in c.get("/admin/tenants", headers=H).json() if x["name"] == "Balkan Butik"][0]
    assert "oluşturuldu" in capsys.readouterr().out
    assert t["currency"] == "EUR" and t["languages"] == ["tr", "sr", "hr"] and t["owner_language"] == "tr"
    assert t["customer_whatsapp"] == "905329998866" and "Boy (cm)" in [f["label"] for f in t["order_fields"]]
