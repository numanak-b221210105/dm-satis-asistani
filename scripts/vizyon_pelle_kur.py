"""İlk müşteri: Vizyon Pelle Fur'u platforma ekler (giyime özel ölçü alanlarıyla).
Kullanım:  python scripts/vizyon_pelle_kur.py http://localhost:8000 <ADMIN_TOKEN>"""
import sys

import httpx

base, token = sys.argv[1].rstrip("/"), sys.argv[2]
H = {"X-Admin-Token": token}

tenant = httpx.post(f"{base}/admin/tenants", headers=H, json={
    "name": "Vizyon Pelle Fur",
    "sector": "Deri ve kürk giyim",
    "description": "Hakiki deri ve kürk ürünler satan butik marka.",   # ← detaylandırın
    "policies": "",   # ← kargo / iade / ödeme şartları; yurt dışı kargo ücreti ve fiyatların para birimini (EUR/TRY) mutlaka yazın
    "tone": "samimi, kibar, kısa cümleler",
    "languages": ["tr", "sr", "ro", "hr", "en"],   # Sırbistan, Romanya, Hırvatistan ağırlıklı müşteriler
    "owner_language": "tr",                  # Bildirim özetleri Türkçe gelir
    "currency": "EUR",                       # ← EUR veya USD
    "customer_whatsapp": None,               # ← müşterilerin yazacağı WhatsApp hattı, ör. "90XXXXXXXXXX"
    "notify_whatsapp": "90XXXXXXXXXX",                                # ← bildirim numarası
    "order_fields": [
        {"key": "boy", "label": "Boy (cm)", "required": True},
        {"key": "kilo", "label": "Kilo (kg)", "required": True},
        {"key": "gogus_olcusu", "label": "Göğüs ölçüsü (cm)", "required": True},
        {"key": "ad_soyad", "label": "Ad soyad", "required": True},
        {"key": "telefon", "label": "Telefon", "required": True},
        {"key": "adres", "label": "Teslimat adresi", "required": True},
        {"key": "renk", "label": "Renk tercihi", "required": False},
    ],
}).raise_for_status().json()
print("Esnaf oluşturuldu, id =", tenant["id"])

products = [  # ← gerçek ürünlerle değiştirin
    {"name": "ÖRNEK Klasik Deri Ceket", "price": "", "category": "Deri ceket", "variants": "S, M, L, XL, XXL; Siyah, Kahverengi"},
    {"name": "ÖRNEK Kürk Yaka Mont", "price": "", "category": "Kürk", "variants": "M, L, XL"},
]
httpx.post(f"{base}/admin/tenants/{tenant['id']}/products", headers=H, json=products,
           params={"replace": "true"}).raise_for_status()
print(f"{len(products)} ürün eklendi. Instagram bağlantısı Adım 3'te yapılacak.")
