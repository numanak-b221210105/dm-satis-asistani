"""Kurulum sihirbazı: esnafa sorulacak sorular, sektör şablonları ve cevaplardan işletme ayarı üretme.
Aynı soru listesi hem komut satırı sihirbazında (scripts/kurulum_sihirbazi.py) hem ileride web panelinde kullanılır."""
import re

from app import currencies as C
from app import languages as L

# Sektöre göre önerilen sipariş alanları
SECTOR_PRESETS: dict[str, dict] = {
    "giyim": {
        "ad": "Giyim / butik / deri-kürk",
        "alanlar": [
            {"key": "beden", "label": "Beden (biliyorsa)", "required": False},
            {"key": "boy", "label": "Boy (cm)", "required": True},
            {"key": "kilo", "label": "Kilo (kg)", "required": True},
            {"key": "gogus_olcusu", "label": "Göğüs ölçüsü (cm)", "required": False},
            {"key": "renk", "label": "Renk", "required": False},
        ],
    },
    "yemek": {
        "ad": "Pastane / yemek / tatlı",
        "alanlar": [
            {"key": "teslim_tarihi", "label": "Teslim tarihi ve saati", "required": True},
            {"key": "kisi_sayisi", "label": "Kişi sayısı / adet", "required": True},
            {"key": "ozel_istek", "label": "Üzerine yazı, alerji vb. özel istek", "required": False},
        ],
    },
    "guzellik": {
        "ad": "Kuaför / güzellik salonu / randevulu hizmet",
        "alanlar": [
            {"key": "hizmet", "label": "İstenen hizmet", "required": True},
            {"key": "tarih_saat", "label": "Tercih edilen tarih ve saat", "required": True},
        ],
    },
    "el_yapimi": {
        "ad": "El yapımı / hediyelik / kişiye özel",
        "alanlar": [
            {"key": "adet", "label": "Adet", "required": True},
            {"key": "kisisellestirme", "label": "Kişiselleştirme (isim, yazı, renk)", "required": False},
        ],
    },
    "ev": {
        "ad": "Ev tekstili / mobilya / dekorasyon",
        "alanlar": [
            {"key": "olculer", "label": "Ölçüler (en × boy)", "required": True},
            {"key": "renk_desen", "label": "Renk / desen", "required": False},
            {"key": "adet", "label": "Adet", "required": True},
        ],
    },
    "diger": {"ad": "Diğer", "alanlar": [
        {"key": "adet", "label": "Adet", "required": False},
        {"key": "not", "label": "Ek not", "required": False},
    ]},
}

# Her sektörde sonda sorulan iletişim alanları
CONTACT_FIELDS = [
    {"key": "ad_soyad", "label": "Ad soyad", "required": True},
    {"key": "telefon", "label": "Telefon", "required": True},
    {"key": "adres", "label": "Teslimat adresi (şehir ve ülke dahil)", "required": True},
]

TONES = {
    "samimi": "samimi, sıcak ve kısa cümleler; ölçülü emoji",
    "resmi": "kibar ve resmi; emoji kullanma",
    "enerjik": "enerjik ve neşeli; emoji kullanabilirsin",
}

QUESTIONS: list[dict] = [
    {"key": "name", "soru": "İşletmenizin adı nedir?", "tip": "metin", "zorunlu": True},
    {"key": "sector", "soru": "Hangi sektördesiniz?", "tip": "secim",
     "secenekler": {k: v["ad"] for k, v in SECTOR_PRESETS.items()}, "varsayilan": "diger"},
    {"key": "description", "soru": "İşletmenizi birkaç cümleyle anlatın (ne satıyorsunuz, nereden gönderiyorsunuz, "
                                   "neyle öne çıkıyorsunuz?)", "tip": "metin"},
    {"key": "languages", "soru": "Müşterileriniz hangi dillerde yazıyor? (virgülle, ör: tr,en,sr,ro,hr)",
     "tip": "coklu_secim", "secenekler": {k: v[0] for k, v in L.LANGUAGES.items()}, "varsayilan": ["tr", "en"]},
    {"key": "owner_language", "soru": "Size gelecek bildirim özetleri hangi dilde olsun?", "tip": "secim",
     "secenekler": {k: v[0] for k, v in L.LANGUAGES.items()}, "varsayilan": "tr"},
    {"key": "currency", "soru": "Fiyatlarınız hangi para biriminde?", "tip": "secim",
     "secenekler": {k: k for k in C.CURRENCIES}, "varsayilan": "TRY"},
    {"key": "shipping", "soru": "Kargo: hangi ülkelere gönderiyorsunuz, ücreti ve süresi nedir?", "tip": "metin"},
    {"key": "returns", "soru": "İade / değişim şartlarınız nedir?", "tip": "metin"},
    {"key": "payment", "soru": "Hangi ödeme yöntemlerini kabul ediyorsunuz? (havale, kapıda ödeme, PayPal...)",
     "tip": "metin"},
    {"key": "tone", "soru": "Asistan nasıl bir üslupla konuşsun?", "tip": "secim",
     "secenekler": {k: v for k, v in TONES.items()}, "varsayilan": "samimi"},
    {"key": "notify_whatsapp", "soru": "Sipariş ve acil durum bildirimleri hangi WhatsApp numarasına gelsin? "
                                       "(ülke koduyla, ör: 905321234567)", "tip": "telefon", "zorunlu": True},
    {"key": "customer_whatsapp", "soru": "Müşterilerin size yazabileceği bir WhatsApp hattı var mı? Varsa numara "
                                         "(boş bırakırsanız müşteriler WhatsApp'a yönlendirilmez)", "tip": "telefon"},
    {"key": "extra_fields", "soru": "Siparişte ayrıca sorulmasını istediğiniz bilgi var mı? (virgülle, ör: "
                                    "hediye paketi, fatura adresi)", "tip": "metin"},
]


def normalize_phone(raw: str | None) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):   # 05xx... → 905xx...
        digits = "9" + digits
    return digits


def _slug(text: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return re.sub(r"[^a-z0-9]+", "_", text.translate(tr).lower()).strip("_")[:40] or "alan"


def build_tenant(answers: dict) -> dict:
    """Sihirbaz cevaplarından /admin/tenants gövdesi üretir."""
    sector = answers.get("sector") or "diger"
    preset = SECTOR_PRESETS.get(sector, SECTOR_PRESETS["diger"])
    fields = [dict(f) for f in preset["alanlar"]]
    for extra in [x.strip() for x in (answers.get("extra_fields") or "").split(",") if x.strip()]:
        fields.append({"key": _slug(extra), "label": extra, "required": False})
    fields += [dict(f) for f in CONTACT_FIELDS]
    seen, unique = set(), []
    for f in fields:
        if f["key"] not in seen:
            seen.add(f["key"])
            unique.append(f)

    langs = answers.get("languages") or ["tr", "en"]
    if isinstance(langs, str):
        langs = [x.strip().lower() for x in langs.split(",") if x.strip()]

    policies = []
    for key, title in [("shipping", "Kargo"), ("returns", "İade/değişim"), ("payment", "Ödeme")]:
        if (answers.get(key) or "").strip():
            policies.append(f"{title}: {answers[key].strip()}")

    return {
        "name": answers["name"].strip(),
        "sector": preset["ad"],
        "description": (answers.get("description") or "").strip(),
        "policies": "\n".join(policies),
        "tone": TONES.get(answers.get("tone") or "samimi", answers.get("tone") or TONES["samimi"]),
        "languages": langs,
        "owner_language": answers.get("owner_language") or "tr",
        "currency": (answers.get("currency") or "TRY").upper(),
        "notify_whatsapp": normalize_phone(answers.get("notify_whatsapp")),
        "customer_whatsapp": normalize_phone(answers.get("customer_whatsapp")) or None,
        "order_fields": unique,
    }
