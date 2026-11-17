"""Desteklenen diller, bayraklar ve koddaki sabit (yedek) mesajların çevirileri."""

LANGUAGES: dict[str, tuple[str, str]] = {
    # kod: (yerel ad, bayrak)
    "tr": ("Türkçe", "🇹🇷"),
    "en": ("English", "🇬🇧"),
    "sr": ("Srpski / Српски", "🇷🇸"),
    "ro": ("Română", "🇷🇴"),
    "bs": ("Bosanski", "🇧🇦"),
    "hr": ("Hrvatski", "🇭🇷"),
    "mk": ("Македонски", "🇲🇰"),
    "bg": ("Български", "🇧🇬"),
    "sq": ("Shqip", "🇦🇱"),
    "el": ("Ελληνικά", "🇬🇷"),
    "de": ("Deutsch", "🇩🇪"),
    "fr": ("Français", "🇫🇷"),
    "ru": ("Русский", "🇷🇺"),
    "uk": ("Українська", "🇺🇦"),
    "ar": ("العربية", "🇸🇦"),
    "az": ("Azərbaycanca", "🇦🇿"),
}

DEFAULT_LANGUAGES = ["tr", "en"]

FALLBACK_REPLY = {
    "tr": "Talebinizi ekibimize ilettim, en kısa sürede dönüş yapacağız 🙏",
    "en": "I've passed your request to our team, we'll get back to you shortly 🙏",
    "sr": "Prosledio sam vaš zahtev našem timu, javićemo vam se uskoro 🙏",
    "ro": "Am transmis solicitarea dvs. echipei noastre, vă vom răspunde în curând 🙏",
    "bs": "Proslijedio sam vaš zahtjev našem timu, javit ćemo vam se uskoro 🙏",
    "hr": "Proslijedio sam vaš zahtjev našem timu, javit ćemo vam se uskoro 🙏",
    "bg": "Предадох запитването ви на екипа ни, ще се свържем с вас скоро 🙏",
    "de": "Ich habe Ihre Anfrage an unser Team weitergeleitet, wir melden uns in Kürze 🙏",
    "ru": "Я передал ваш запрос нашей команде, мы скоро свяжемся с вами 🙏",
}


def is_valid(code: str) -> bool:
    return code in LANGUAGES


def label(code: str | None) -> str:
    if not code:
        return "bilinmiyor"
    name, flag = LANGUAGES.get(code, (code, "🌐"))
    return f"{flag} {name}"


def fallback_reply(code: str | None, default: str = "tr") -> str:
    return FALLBACK_REPLY.get(code or "", FALLBACK_REPLY.get(default, FALLBACK_REPLY["en"]))
