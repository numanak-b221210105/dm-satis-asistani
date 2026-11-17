"""Müşteriye verilecek wa.me bağlantıları (müşteri işletmeye kendisi yazar → 24 saat/şablon kısıtı yok)."""
from urllib.parse import quote


def wa_link(number: str, text: str) -> str:
    digits = "".join(ch for ch in number if ch.isdigit())
    return f"https://wa.me/{digits}?text={quote(text[:1500])}"
