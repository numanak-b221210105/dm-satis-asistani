"""Instagram (Instagram Login ile Instagram API) ve WhatsApp Cloud API istemcileri.
Instagram çağrıları her esnafın kendi token'ıyla yapılır; WhatsApp bildirimleri platformun tek hattından gider."""
import hashlib
import hmac
import logging

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)
_client: httpx.AsyncClient | None = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=20)
    return _client


def ig_url(path: str) -> str:
    s = get_settings()
    return f"{s.instagram_graph_base}/{s.graph_api_version}/{path}"


def fb_url(path: str) -> str:
    s = get_settings()
    return f"{s.facebook_graph_base}/{s.graph_api_version}/{path}"


def verify_signature(body: bytes, header: str | None) -> bool:
    secret = get_settings().meta_app_secret
    if not secret:
        log.warning("META_APP_SECRET tanımlı değil — imza doğrulaması atlandı (canlıda tanımlayın!)")
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


# ---------- Instagram ----------

async def ig_send_text(token: str, recipient_id: str, text: str) -> str | None:
    """Mesaj gönderir, Meta'nın döndürdüğü message_id'yi verir."""
    r = await client().post(
        ig_url("me/messages"),
        headers={"Authorization": f"Bearer {token}"},
        json={"recipient": {"id": recipient_id}, "message": {"text": text}},
    )
    if r.is_error:
        log.error("Instagram mesajı gönderilemedi: %s %s", r.status_code, r.text)
    r.raise_for_status()
    return r.json().get("message_id")


async def ig_sender_action(token: str, recipient_id: str, action: str) -> None:
    """typing_on | typing_off | mark_seen — hata sohbeti durdurmaz."""
    try:
        r = await client().post(
            ig_url("me/messages"),
            headers={"Authorization": f"Bearer {token}"},
            json={"recipient": {"id": recipient_id}, "sender_action": action},
        )
        if r.is_error:
            log.warning("sender_action %s başarısız: %s %s", action, r.status_code, r.text)
    except httpx.HTTPError as e:
        log.warning("sender_action %s hatası: %s", action, e)


async def ig_get_username(token: str, user_id: str) -> str | None:
    try:
        r = await client().get(ig_url(user_id), params={"fields": "username,name"},
                               headers={"Authorization": f"Bearer {token}"})
        if r.is_success:
            d = r.json()
            return d.get("username") or d.get("name")
    except httpx.HTTPError as e:
        log.warning("Kullanıcı adı alınamadı: %s", e)
    return None


# ---------- WhatsApp ----------

async def whatsapp_notify(to_number: str, text: str) -> bool:
    """Esnafa WhatsApp bildirimi. 24 saat penceresi dışında yalnızca onaylı şablon iletilir;
    şablon tanımlıysa önce o, olmazsa serbest metin denenir."""
    s = get_settings()
    if not to_number or not s.whatsapp_phone_number_id:
        log.warning("WhatsApp bildirimi atlanıyor (numara veya hat tanımsız)")
        return False
    url = fb_url(f"{s.whatsapp_phone_number_id}/messages")
    headers = {"Authorization": f"Bearer {s.whatsapp_access_token}"}
    base = {"messaging_product": "whatsapp", "to": to_number}

    attempts = []
    if s.whatsapp_template_name:
        flat = " | ".join(line.strip() for line in text.splitlines() if line.strip())[:1000]
        attempts.append({**base, "type": "template", "template": {
            "name": s.whatsapp_template_name, "language": {"code": s.whatsapp_template_lang},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": flat}]}],
        }})
    attempts.append({**base, "type": "text", "text": {"body": text[:4096]}})

    for payload in attempts:
        try:
            r = await client().post(url, headers=headers, json=payload)
            if r.is_success:
                return True
            log.error("WhatsApp (%s) başarısız: %s %s", payload["type"], r.status_code, r.text)
        except httpx.HTTPError as e:
            log.error("WhatsApp (%s) hatası: %s", payload["type"], e)
    return False


async def ig_refresh_token(token: str) -> tuple[str, int]:
    """Uzun ömürlü Instagram token'ını yeniler (60 gün). (yeni_token, saniye_cinsinden_ömür) döner.
    Token en az 24 saatlik ve süresi dolmamış olmalıdır."""
    s = get_settings()
    r = await client().get(f"{s.instagram_graph_base}/refresh_access_token",
                           params={"grant_type": "ig_refresh_token", "access_token": token})
    r.raise_for_status()
    d = r.json()
    return d["access_token"], int(d.get("expires_in", 60 * 24 * 3600))
