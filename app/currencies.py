"""Para birimleri ve fiyat gösterimi."""
import re

CURRENCIES = {
    "EUR": "€", "USD": "$", "TRY": "₺", "GBP": "£", "RSD": "RSD", "RON": "lei",
    "BAM": "KM", "BGN": "лв", "MKD": "ден", "ALL": "L", "CHF": "CHF", "RUB": "₽", "AZN": "₼",
}


def is_valid(code: str) -> bool:
    return code in CURRENCIES


def format_price(price: str, currency: str) -> str:
    """'120' → '120 EUR'. Fiyatta zaten para birimi/sembol varsa dokunmaz; boşsa 'sorunuz' döner."""
    p = (price or "").strip()
    if not p:
        return "fiyat için sorunuz"
    if re.fullmatch(r"[\d.,\s]+", p):
        return f"{p} {currency}"
    return p
