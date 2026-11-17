"""Kurulum sihirbazı — yeni bir işletmeyi sorular sorarak platforma ekler.
Kullanım:  python scripts/kurulum_sihirbazi.py http://localhost:8000 <ADMIN_TOKEN>"""
import json
import sys

import httpx

base, token = sys.argv[1].rstrip("/"), sys.argv[2]
H = {"X-Admin-Token": token}


def ask(q: dict):
    print()
    print(f"❓ {q['soru']}")
    options = q.get("secenekler")
    default = q.get("varsayilan")
    if options and q["tip"] in ("secim", "coklu_secim"):
        for k, v in options.items():
            print(f"   {k:<10} {v}")
    while True:
        hint = f" [{','.join(default) if isinstance(default, list) else default}]" if default else ""
        raw = input(f"→{hint} ").strip()
        if not raw:
            if default is not None:
                return default
            if q.get("zorunlu"):
                print("   Bu soru zorunlu.")
                continue
            return ""
        if q["tip"] == "secim" and options and raw not in options:
            print(f"   Lütfen şunlardan birini yazın: {', '.join(options)}")
            continue
        if q["tip"] == "coklu_secim" and options:
            picked = [x.strip().lower() for x in raw.split(",") if x.strip()]
            bad = [x for x in picked if x not in options]
            if bad:
                print(f"   Tanınmayan: {', '.join(bad)}")
                continue
            return picked
        return raw


def main():
    data = httpx.get(f"{base}/admin/onboarding", headers=H).raise_for_status().json()
    print("=" * 60)
    print("  Kurulum sihirbazı — birkaç soruyla asistanınızı hazırlayalım")
    print("=" * 60)
    answers = {q["key"]: ask(q) for q in data["sorular"]}
    print("\nÖzet:")
    print(json.dumps(answers, ensure_ascii=False, indent=2))
    if input("\nKaydedilsin mi? (e/h) ").strip().lower() not in ("e", "evet", "y", "yes"):
        print("İptal edildi.")
        return
    t = httpx.post(f"{base}/admin/onboarding", headers=H, json=answers).raise_for_status().json()
    print(f"\n✅ '{t['name']}' oluşturuldu (id={t['id']}).")
    print("   Sipariş alanları:", ", ".join(f["label"] for f in t["order_fields"]))
    print("   Sonraki adım: ürünleri ekleyin ve Instagram hesabını bağlayın.")


if __name__ == "__main__":
    main()
