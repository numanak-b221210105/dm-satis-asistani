"""Veritabanı modelleri (çok müşterili / multi-tenant). Her kayıt bir esnafa (tenant) bağlıdır."""
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
                        select)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# Yeni esnaf için önerilen sipariş alanları (panelden değiştirilebilir)
DEFAULT_ORDER_FIELDS = [
    {"key": "ad_soyad", "label": "Ad soyad", "required": True},
    {"key": "telefon", "label": "Telefon numarası", "required": True},
    {"key": "adres", "label": "Teslimat adresi (il/ilçe dahil)", "required": True},
    {"key": "adet", "label": "Adet", "required": False},
    {"key": "not", "label": "Varsa ek not (renk, beden, tarih vb.)", "required": False},
]


class Tenant(Base):
    """Bir esnaf / işletme."""
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))                    # "Vizyon Pelle Fur"
    sector: Mapped[str] = mapped_column(String(100), default="")      # "Deri ve kürk giyim"
    description: Mapped[str] = mapped_column(Text, default="")        # Botun bilmesi gereken genel bilgiler
    policies: Mapped[str] = mapped_column(Text, default="")           # Kargo, iade, ödeme şartları (esnafın yazdığı)
    tone: Mapped[str] = mapped_column(String(200), default="samimi ve kibar")
    order_fields: Mapped[list] = mapped_column(JSON, default=lambda: list(DEFAULT_ORDER_FIELDS))

    ig_account_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    ig_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ig_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)       # Şifreli
    ig_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    notify_whatsapp: Mapped[str] = mapped_column(String(20), default="")       # 90XXXXXXXXXX
    humanizer_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Dil ayarları: müşterilere hangi dillerde hizmet verilir, esnafa bildirimler hangi dilde gider
    languages: Mapped[list | None] = mapped_column(JSON, nullable=True)            # ["tr","en","sr","ro"]
    owner_language: Mapped[str | None] = mapped_column(String(8), nullable=True)   # "tr"
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


def tenant_languages(t: "Tenant") -> list[str]:
    from app.languages import DEFAULT_LANGUAGES
    return list(t.languages or DEFAULT_LANGUAGES)


def tenant_owner_language(t: "Tenant") -> str:
    return t.owner_language or "tr"


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[str] = mapped_column(String(100), default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    variants: Mapped[str] = mapped_column(String(500), default="")   # "S, M, L" / "Kırmızı, Siyah"
    description: Mapped[str] = mapped_column(Text, default="")
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("tenant_id", "customer_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[str] = mapped_column(String(64))
    customer_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bot_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)   # Müşterinin son kullandığı dil
    paused_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))   # user | assistant | staff
    content: Mapped[str] = mapped_column(Text)
    mid: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    images: Mapped[list] = mapped_column(JSON, default=list)   # Müşterinin gönderdiği görsel URL'leri
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    product_name: Mapped[str] = mapped_column(String(255))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="yeni")   # yeni | onaylandi | kargoda | iptal
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Handoff(Base):
    __tablename__ = "handoffs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class UsageLog(Base):
    """Esnaf bazında LLM kullanımı — maliyet takibi ve paket limitleri için."""
    __tablename__ = "usage_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class SentMessage(Base):
    """Botun gönderdiği mesaj ID'leri — esnafın elle yazdığı mesajı (echo) bottan ayırt etmek için."""
    __tablename__ = "sent_messages"
    mid: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------- Yardımcılar ----------

async def tenant_by_ig(session: AsyncSession, ig_account_id: str) -> Tenant | None:
    return await session.scalar(select(Tenant).where(Tenant.ig_account_id == ig_account_id))


async def get_or_create_conversation(session: AsyncSession, tenant_id: int, customer_id: str) -> Conversation:
    conv = await session.scalar(select(Conversation).where(
        Conversation.tenant_id == tenant_id, Conversation.customer_id == customer_id))
    if conv is None:
        conv = Conversation(tenant_id=tenant_id, customer_id=customer_id)
        session.add(conv)
        try:
            await session.commit()
        except IntegrityError:  # Aynı anda gelen iki ilk mesaj — diğeri oluşturdu
            await session.rollback()
            conv = await session.scalar(select(Conversation).where(
                Conversation.tenant_id == tenant_id, Conversation.customer_id == customer_id))
    return conv


async def get_history(session: AsyncSession, conversation_id: int, limit: int) -> list[Message]:
    rows = await session.scalars(select(Message).where(Message.conversation_id == conversation_id)
                                 .order_by(Message.id.desc()).limit(limit))
    return list(reversed(rows.all()))


async def last_message(session: AsyncSession, conversation_id: int) -> Message | None:
    return await session.scalar(select(Message).where(Message.conversation_id == conversation_id)
                                .order_by(Message.id.desc()).limit(1))
