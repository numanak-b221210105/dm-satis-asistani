"""Platform yöneticisi API'si (X-Admin-Token). Esnaf paneli ve 'Instagram ile bağlan' Adım 4'te eklenecek;
o zamana kadar esnaflar bu uç noktalarla kurulur."""
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select

from app import languages as L
from app.config import get_settings
from app.crypto import encrypt
from app.db import DEFAULT_ORDER_FIELDS, Conversation, Order, Product, SessionLocal, Tenant, UsageLog


def require_admin(x_admin_token: str | None = Header(None)) -> None:
    expected = get_settings().admin_token
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Yetkisiz")


router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)], tags=["admin"])


# ---------- Şemalar ----------

class OrderField(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]{1,40}$")
    label: str
    required: bool = False


class TenantIn(BaseModel):
    name: str
    sector: str = ""
    description: str = ""
    policies: str = ""
    tone: str = "samimi ve kibar"
    notify_whatsapp: str = Field("", pattern=r"^(\d{10,15})?$")
    order_fields: list[OrderField] | None = None
    humanizer_enabled: bool = True
    active: bool = True
    languages: list[str] | None = None        # Ör. ["tr", "en", "sr", "ro"]
    owner_language: str | None = None         # Bildirim özetlerinin dili (varsayılan tr)

    @field_validator("languages")
    @classmethod
    def _langs(cls, v):
        if v is None:
            return v
        bad = [c for c in v if not L.is_valid(c)]
        if bad or not v:
            raise ValueError(f"Geçersiz dil kodu: {bad}. Desteklenenler: {', '.join(L.LANGUAGES)}")
        return list(dict.fromkeys(v))

    @field_validator("owner_language")
    @classmethod
    def _owner(cls, v):
        if v is not None and not L.is_valid(v):
            raise ValueError(f"Geçersiz dil kodu: {v}")
        return v


class TenantPatch(BaseModel):
    name: str | None = None
    sector: str | None = None
    description: str | None = None
    policies: str | None = None
    tone: str | None = None
    notify_whatsapp: str | None = Field(None, pattern=r"^(\d{10,15})?$")
    order_fields: list[OrderField] | None = None
    humanizer_enabled: bool | None = None
    active: bool | None = None
    languages: list[str] | None = None
    owner_language: str | None = None

    @field_validator("languages")
    @classmethod
    def _langs(cls, v):
        if v is None:
            return v
        bad = [c for c in v if not L.is_valid(c)]
        if bad or not v:
            raise ValueError(f"Geçersiz dil kodu: {bad}. Desteklenenler: {', '.join(L.LANGUAGES)}")
        return list(dict.fromkeys(v))

    @field_validator("owner_language")
    @classmethod
    def _owner(cls, v):
        if v is not None and not L.is_valid(v):
            raise ValueError(f"Geçersiz dil kodu: {v}")
        return v


class InstagramConnect(BaseModel):
    ig_account_id: str
    access_token: str
    ig_username: str | None = None
    expires_at: datetime | None = None


class ProductIn(BaseModel):
    name: str
    price: str = ""
    category: str = ""
    variants: str = ""
    description: str = ""
    in_stock: bool = True


def tenant_out(t: Tenant) -> dict:
    return {"id": t.id, "name": t.name, "sector": t.sector, "description": t.description,
            "policies": t.policies, "tone": t.tone, "notify_whatsapp": t.notify_whatsapp,
            "order_fields": t.order_fields, "humanizer_enabled": t.humanizer_enabled, "active": t.active,
            "languages": t.languages or L.DEFAULT_LANGUAGES, "owner_language": t.owner_language or "tr",
            "instagram": {"bagli": bool(t.ig_token_enc), "hesap_id": t.ig_account_id,
                          "kullanici_adi": t.ig_username,
                          "token_bitis": t.ig_token_expires_at.isoformat() if t.ig_token_expires_at else None}}


async def _tenant(s, tenant_id: int) -> Tenant:
    t = await s.get(Tenant, tenant_id)
    if t is None:
        raise HTTPException(404, "Esnaf bulunamadı")
    return t


# ---------- Esnaflar ----------

@router.post("/tenants")
async def create_tenant(body: TenantIn):
    async with SessionLocal() as s:
        data = body.model_dump(exclude={"order_fields"})
        fields = [f.model_dump() for f in body.order_fields] if body.order_fields else list(DEFAULT_ORDER_FIELDS)
        t = Tenant(**data, order_fields=fields)
        s.add(t)
        await s.commit()
        return tenant_out(t)


@router.get("/tenants")
async def list_tenants():
    async with SessionLocal() as s:
        return [tenant_out(t) for t in await s.scalars(select(Tenant).order_by(Tenant.id))]


@router.patch("/tenants/{tenant_id}")
async def update_tenant(tenant_id: int, body: TenantPatch):
    async with SessionLocal() as s:
        t = await _tenant(s, tenant_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(t, k, [f for f in v] if k == "order_fields" else v)
        await s.commit()
        return tenant_out(t)


@router.post("/tenants/{tenant_id}/instagram")
async def connect_instagram(tenant_id: int, body: InstagramConnect):
    """Instagram hesabını elle bağlar (Adım 4'te OAuth ile otomatikleşecek)."""
    async with SessionLocal() as s:
        t = await _tenant(s, tenant_id)
        other = await s.scalar(select(Tenant).where(Tenant.ig_account_id == body.ig_account_id,
                                                    Tenant.id != tenant_id))
        if other:
            raise HTTPException(409, f"Bu Instagram hesabı başka bir esnafa bağlı (#{other.id})")
        t.ig_account_id = body.ig_account_id
        t.ig_token_enc = encrypt(body.access_token)
        t.ig_username = body.ig_username
        t.ig_token_expires_at = body.expires_at
        await s.commit()
        return tenant_out(t)


# ---------- Ürünler ----------

@router.get("/tenants/{tenant_id}/products")
async def list_products(tenant_id: int):
    async with SessionLocal() as s:
        rows = await s.scalars(select(Product).where(Product.tenant_id == tenant_id).order_by(Product.id))
        return [{"id": p.id, **ProductIn.model_validate(p, from_attributes=True).model_dump()} for p in rows]


@router.post("/tenants/{tenant_id}/products")
async def add_products(tenant_id: int, items: list[ProductIn], replace: bool = False):
    """Ürün ekler. replace=true ise mevcut kataloğu tamamen değiştirir."""
    async with SessionLocal() as s:
        await _tenant(s, tenant_id)
        if replace:
            await s.execute(delete(Product).where(Product.tenant_id == tenant_id))
        s.add_all([Product(tenant_id=tenant_id, **i.model_dump()) for i in items])
        await s.commit()
    return {"eklenen": len(items)}


@router.delete("/tenants/{tenant_id}/products/{product_id}")
async def delete_product(tenant_id: int, product_id: int):
    async with SessionLocal() as s:
        await s.execute(delete(Product).where(Product.tenant_id == tenant_id, Product.id == product_id))
        await s.commit()
    return {"silindi": product_id}


# ---------- Siparişler ve sohbetler ----------

@router.get("/tenants/{tenant_id}/orders")
async def list_orders(tenant_id: int, limit: int = 50):
    async with SessionLocal() as s:
        rows = await s.execute(select(Order, Conversation).join(Conversation, Order.conversation_id == Conversation.id)
                               .where(Order.tenant_id == tenant_id).order_by(Order.id.desc()).limit(limit))
        return [{"id": o.id, "musteri": c.customer_username or c.customer_id, "urun": o.product_name,
                 "detaylar": o.details, "durum": o.status, "whatsapp_iletildi": o.notified,
                 "tarih": o.created_at.isoformat()} for o, c in rows]


@router.get("/tenants/{tenant_id}/paused")
async def paused_conversations(tenant_id: int):
    async with SessionLocal() as s:
        rows = await s.scalars(select(Conversation).where(Conversation.tenant_id == tenant_id,
                                                          Conversation.bot_paused.is_(True)))
        return [{"conversation_id": c.id, "musteri": c.customer_username or c.customer_id,
                 "sebep": c.paused_reason} for c in rows]


@router.post("/conversations/{conversation_id}/resume")
async def resume(conversation_id: int):
    async with SessionLocal() as s:
        c = await s.get(Conversation, conversation_id)
        if c is None:
            raise HTTPException(404, "Sohbet bulunamadı")
        c.bot_paused, c.paused_reason = False, None
        await s.commit()
    return {"conversation_id": conversation_id, "bot_paused": False}


@router.get("/tenants/{tenant_id}/usage")
async def usage(tenant_id: int, days: int = 30):
    """Son N gündeki LLM kullanımı (maliyet hesabı ve paket limitleri için)."""
    from datetime import timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(days=days)
    async with SessionLocal() as s:
        row = (await s.execute(select(func.count(UsageLog.id), func.coalesce(func.sum(UsageLog.input_tokens), 0),
                                      func.coalesce(func.sum(UsageLog.output_tokens), 0))
                               .where(UsageLog.tenant_id == tenant_id, UsageLog.created_at >= since))).one()
    return {"gun": days, "mesaj_sayisi": row[0], "input_tokens": row[1], "output_tokens": row[2]}


@router.get("/languages", tags=["admin"])
async def supported_languages():
    return [{"kod": k, "ad": v[0], "bayrak": v[1]} for k, v in L.LANGUAGES.items()]
