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
