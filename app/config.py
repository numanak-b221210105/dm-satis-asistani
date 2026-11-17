"""Platform ayarları — .env dosyasından / ortam değişkenlerinden okunur.
Müşteriye (esnafa) özel ayarlar burada DEĞİL, veritabanındaki `tenants` tablosundadır."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Genel ---
    platform_name: str = "DM Satış Asistanı"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/dm_asistan"
    history_limit: int = 20
    admin_token: str = ""          # Platform yöneticisi (sen) için /admin uç noktaları
    encryption_key: str = ""       # Esnaf token'larını şifrelemek için (Fernet anahtarı)
    auto_create_tables: bool = True   # Geliştirme kolaylığı; canlıda false + `alembic upgrade head`
    run_maintenance: bool = True      # Token yenileme döngüsü (birden fazla sunucuda yalnızca birinde açık olsun)

    # --- Meta uygulaması (tek uygulama, tüm esnaflar bunun üzerinden bağlanır) ---
    meta_verify_token: str = "degistir-beni"
    meta_app_secret: str = ""
    graph_api_version: str = "v21.0"
    instagram_graph_base: str = "https://graph.instagram.com"
    facebook_graph_base: str = "https://graph.facebook.com"

    # --- WhatsApp (platformun bildirim hattı — tüm esnaflara bildirim bu hattan gider) ---
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_template_name: str = ""   # Onaylı şablon (tek {{1}} gövde parametresi)
    whatsapp_template_lang: str = "tr"

    # --- OpenAI ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.4

    # --- Mesaj işleme ---
    debounce_seconds: float = 4.0     # Müşteri art arda yazarsa son mesajdan sonra bu kadar bekleyip tek cevap ver

    # --- İnsansı gönderim (varsayılanlar; esnaf bazında kapatılabilir) ---
    humanizer_enabled: bool = True
    chars_per_second: float = 15.0
    min_delay: float = 1.5
    max_delay: float = 12.0
    split_threshold: int = 280
    split_gap_min: float = 2.0
    split_gap_max: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
