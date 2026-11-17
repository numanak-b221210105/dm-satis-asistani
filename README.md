<p align="center">
  <img src="docs/banner.svg" alt="DM Satış Asistanı" width="100%">
</p>

<p align="center">
  <a href="https://github.com/numanak-b221210105/dm-satis-asistani/actions/workflows/tests.yml"><img src="https://github.com/numanak-b221210105/dm-satis-asistani/actions/workflows/tests.yml/badge.svg" alt="tests"></a>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/GPT--4o-vision%20%2B%20tools-412991?logo=openai&logoColor=white" alt="GPT-4o">
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/lisans-tüm%20hakları%20saklı-lightgrey" alt="Lisans">
</p>

<p align="center">
  <b>Instagram'dan satış yapan işletmeler için yapay zeka destekli DM satış asistanı.</b><br>
  Müşteriye işletmenin kendi kataloğuyla cevap verir, sipariş bilgilerini toplar ve siparişi WhatsApp'tan işletme sahibine iletir.
</p>

<p align="center">
  <a href="#nasil">Nasıl çalışır?</a> •
  <a href="#ozellikler">Özellikler</a> •
  <a href="#sektorler">Sektörler</a> •
  <a href="#mimari">Mimari</a> •
  <a href="#kurulum">Kurulum</a> •
  <a href="#yol-haritasi">Yol haritası</a>
</p>

---

## 🎯 Problem

Instagram'dan satış yapan bir işletmenin DM kutusu her gün aynı sorularla doluyor:

> *"Fiyatı ne kadar?"* · *"Bedeni var mı?"* · *"Kargo kaç gün?"* · *"Bu ürün sizde var mı?"* 📷

Cevap birkaç saat gecikirse müşteri başka bir hesaptan alışverişini yapıyor. İşletme sahibi ise gününün büyük kısmını
satış yapmak yerine mesaj yazarak geçiriyor.

## 💡 Çözüm

**DM Satış Asistanı** işletmenin Instagram hesabına bağlanıyor ve bir satış danışmanı gibi çalışıyor:

<p align="center">
  <img src="docs/demo.svg" alt="Örnek sohbet: müşteri yazar, asistan cevaplar, sipariş WhatsApp'a düşer" width="100%">
</p>

<a id="nasil"></a>

## ⚙️ Nasıl çalışır?

| | Adım | Ne oluyor? |
|:-:|---|---|
| **1** | 💬 **Müşteri yazar** | Instagram DM'den bir soru, ürün fotoğrafı ya da sesli mesaj gelir. |
| **2** | 🧠 **Asistan anlar** | Mesajı okur, fotoğraftaki ürünü tanır, işletmenin kataloğundan en uygun ürünü bulur. |
| **3** | 📝 **Bilgileri toplar** | İşletmenin belirlediği bilgileri (beden, adres, tarih...) doğal bir sohbet içinde sorar. |
| **4** | 📲 **Siparişi iletir** | Sipariş tamamlanınca işletme sahibine WhatsApp'tan hazır bir sipariş özeti gönderir. |
| **5** | 🙋 **Gerekirse insana devreder** | Şikayet, iade ya da bilmediği bir soru gelirse sohbeti işletme sahibine aktarır ve kendisi susar. |

<a id="ozellikler"></a>

## ✨ Özellikler

<table>
<tr>
<td width="50%" valign="top">

### 📸 Görsel anlama
Müşteri ürünün ekran görüntüsünü attığında GPT-4o görseli inceliyor ve katalogdaki en yakın ürünü buluyor.

</td>
<td width="50%" valign="top">

### 🛡️ Uydurmuyor
Yalnızca katalogdaki ürünleri ve işletmenin yazdığı kuralları kullanıyor. Bilmediği bir şeyi tahmin etmiyor, işletme sahibine soruyor.

</td>
</tr>
<tr>
<td valign="top">

### 🤝 İşletme sahibi devreye girince susar
İşletme sahibi Instagram'dan müşteriye kendisi yazdığında asistan bunu fark edip o sohbetten çekiliyor.

</td>
<td valign="top">

### 💬 Art arda mesajlara tek cevap
*"selam"* · *"ceket var mı"* · *"siyah"* gibi peş peşe gelen mesajları bekleyip hepsine tek, toplu bir cevap veriyor.

</td>
</tr>
<tr>
<td valign="top">

### ⌨️ Doğal sohbet akışı
Mesajı görüldü olarak işaretliyor, cevap gönderilene kadar *"yazıyor..."* gösteriyor, uzun cevapları cümle sonlarından ikiye bölüyor.

</td>
<td valign="top">

### 🏪 Birden fazla işletme
Tek kurulum birçok işletmeye hizmet veriyor. Her işletmenin kataloğu, üslubu, kuralları ve bildirim numarası ayrı.

</td>
</tr>
<tr>
<td valign="top">

### 🌍 Çok dilli
Müşteriye kendi dilinde cevap veriyor (Türkçe, İngilizce, Sırpça, Romence ve 12 dil daha). Sırpçada müşterinin kullandığı alfabeyi (Latin/Kiril) koruyor. İşletme sahibine bildirimler ise kendi dilinde, müşterinin dili belirtilerek gidiyor.

</td>
<td valign="top">

### 🔐 Güvenlik
Instagram token'ları şifreli saklanıyor, webhook imzası doğrulanıyor, aynı mesaj iki kez gelirse bir kez işleniyor.

</td>
</tr>
<tr>
<td valign="top">

### 🔄 Kendi bakımını yapar
Instagram bağlantısını 60 günde bir otomatik yeniliyor. Her işletmenin yapay zeka kullanımını ve maliyetini kaydediyor.

</td>
<td valign="top">

### 🧾 Hazır sipariş özeti
Sipariş tamamlanınca işletme sahibine ürün, müşteri bilgileri, müşterinin dili ve kısa bir not içeren düzenli bir özet gidiyor.

</td>
</tr>
</table>

<a id="sektorler"></a>

## 🧩 Her sektöre uyar

Siparişte hangi bilgilerin sorulacağına işletme karar veriyor; asistan sohbeti buna göre yürütüyor.

| İşletme | Asistanın topladığı bilgiler |
|---|---|
| 🧥 **Giyim butiği** | Boy · kilo · göğüs ölçüsü · renk · adres |
| 🎂 **Pastane** | Teslim tarihi · kişi sayısı · pasta üzerine yazı · adres |
| 💇 **Kuaför / güzellik salonu** | Hizmet · tarih ve saat · ad soyad · telefon |
| 🕯️ **El yapımı ürünler** | Renk · kişiselleştirme notu · adet · adres |
| 🏠 **Ev tekstili** | Ölçüler (en × boy) · desen · adet · adres |

<a id="mimari"></a>

## 🏗️ Mimari

```mermaid
flowchart LR
    A["📱 Instagram DM"] -->|webhook| B["⚡ FastAPI"]
    B -->|"imza doğrula<br/>işletmeyi bul"| C[("🐘 PostgreSQL")]
    B -->|"mesajları topla"| D["🧠 GPT-4o<br/>işletmeye özel talimat"]
    D -->|"siparis_olustur"| E["📲 WhatsApp"]
    D -->|"insana_aktar"| E
    D -->|"cevap"| F["⌨️ Doğal gönderim"]
    F --> A
    E --> G["👤 İşletme sahibi"]
    G -. "elle yazarsa asistan susar" .-> A
```

<details>
<summary><b>📨 Bir mesajın yolculuğu (sequence diagram)</b></summary>

```mermaid
sequenceDiagram
    autonumber
    participant M as 👤 Müşteri
    participant IG as 📱 Instagram
    participant API as ⚡ Sunucu
    participant AI as 🧠 GPT-4o
    participant WA as 📲 WhatsApp
    participant S as 🏪 İşletme sahibi

    M->>IG: "Bu ceketten var mı?" + 📷
    IG->>API: Webhook (imzalı)
    API->>API: İmza kontrolü · işletmeyi bul · kaydet
    Note over API: Birkaç saniye bekle,<br/>art arda mesajları topla
    API->>AI: Katalog + kurallar + geçmiş + görsel
    AI-->>API: "Var! Boyunuz ve kilonuz?"
    API->>IG: görüldü → yazıyor... → mesaj
    IG->>M: Cevap
    M->>IG: Ölçüler + adres
    IG->>API: Webhook
    API->>AI: Geçmiş + yeni mesaj
    AI-->>API: siparis_olustur(...)
    API->>WA: 🛍️ Yeni sipariş özeti
    WA->>S: Bildirim
    API->>IG: "Siparişiniz alındı 🙏"
```

</details>

<details>
<summary><b>📁 Proje yapısı</b></summary>

```
app/
├── main.py          Webhook, işletme yönlendirmesi, mesaj toplama, echo algılama
├── agent.py         Asistan döngüsü, dinamik araç şemaları, görsel desteği, kullanım kaydı
├── prompts.py       İşletmeye özel talimat (katalog + kurallar + sipariş alanları)
├── humanizer.py     Yazıyor göstergesi, bekleme, mesaj bölme
├── meta.py          Instagram API · WhatsApp Cloud API · imza doğrulama
├── admin.py         Yönetim API'si: işletmeler, ürünler, siparişler, sohbetler, kullanım
├── maintenance.py   Periyodik token yenileme
├── crypto.py        Token şifreleme (Fernet)
└── db.py            SQLAlchemy 2 (async) modelleri
migrations/          Alembic şema geçişleri
tests/               Uçtan uca testler (Meta ve OpenAI taklit edilerek)
docs/                README görselleri
```

</details>

<details>
<summary><b>🔧 Teknik kararlar</b></summary>

- **Debounce + sohbet başına kilit:** Peş peşe gelen mesajlar tek cevapta birleştiriliyor. Kilit sayesinde
  botun kendi gönderdiği mesajın echo'su, mesajın ID'si kaydedilmeden önce işlenmiyor; böylece bot kendi
  mesajını işletme sahibininki sanıp susmuyor.
- **Dinamik araç şeması:** `siparis_olustur` aracının parametreleri her işletmenin `order_fields` ayarından
  oluşturuluyor. Zorunlu bilgiler eksikse model bunu araçtan geri bildirim olarak alıyor.
- **Görseller yalnızca yeni mesajlarda gönderiliyor:** Instagram'ın görsel bağlantılarının süresi doluyor.
  Bu yüzden modele yalnızca son cevaptan sonra gelen görseller gidiyor. İstek yine de başarısız olursa
  görselsiz tekrar deneniyor.
- **Tek Meta uygulaması:** Tüm işletmeler aynı uygulamaya bağlanıyor. Hangi işletmeye ait olduğu webhook'taki
  `entry.id` ile belirleniyor.
- **WhatsApp'ın 24 saat kuralı:** Bildirimlerde önce onaylı şablon deneniyor, olmazsa düz metin gönderiliyor.

</details>

<a id="kurulum"></a>

## 🚀 Kurulum

```bash
git clone https://github.com/numanak-b221210105/dm-satis-asistani.git
cd dm-satis-asistani
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # anahtarları doldurun
docker compose up -d db                                # PostgreSQL
alembic upgrade head                                   # tabloları oluştur
uvicorn app.main:app --reload                          # → http://localhost:8000/docs
```

```bash
pytest -q        # 18 test · gerçek API'ye bağlanmaz
```

<details>
<summary><b>Örnek: yeni işletme ekleme</b></summary>

```bash
curl -X POST localhost:8000/admin/tenants \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "Örnek Butik",
    "sector": "Kadın giyim",
    "notify_whatsapp": "90XXXXXXXXXX",
    "policies": "Kargo ücretsiz, 2-3 iş günü. 14 gün içinde iade.",
    "order_fields": [
      {"key": "beden", "label": "Beden", "required": true},
      {"key": "adres", "label": "Teslimat adresi", "required": true}
    ]
  }'
```

</details>

## 🧰 Teknolojiler

| Katman | Teknoloji |
|---|---|
| Backend | Python 3.12 · FastAPI · asyncio |
| Yapay zeka | OpenAI GPT-4o (görsel + function calling) · LangChain |
| Veritabanı | PostgreSQL · SQLAlchemy 2 (async) · Alembic |
| Entegrasyonlar | Instagram Graph API · WhatsApp Cloud API |
| Güvenlik | HMAC-SHA256 webhook doğrulama · Fernet şifreleme |
| DevOps | Docker · Docker Compose · GitHub Actions |

<a id="yol-haritasi"></a>

## 🗺️ Yol haritası

- [x] Çok işletmeli çekirdek ve dinamik sipariş alanları
- [x] Görsel anlama, token yenileme, kullanım takibi, Alembic, CI
- [x] Çok dilli destek (müşteri dilinde cevap, esnafa kendi dilinde özet)
- [ ] Gerçek bir işletmeyle canlı pilot
- [ ] İşletme paneli ve "Instagram ile bağlan" ile kendi kendine kayıt
- [ ] Paketler ve ödeme altyapısı
- [ ] Kuyruk tabanlı işleme (Redis) ile yatay ölçekleme
- [ ] Meta App Review ve genel kullanıma açılış

> **Bilinen sınırlar:** Mesajlar şimdilik sunucunun kendi içinde işleniyor. Sunucu tam işlem sırasında yeniden
> başlarsa o mesaj cevapsız kalabiliyor; kuyruk altyapısı yol haritasında. Gerçek Meta ortamında uçtan uca test
> henüz yapılmadı.

## 📄 Lisans

Kaynak kod portföy ve inceleme amacıyla herkese açık; kullanım hakları saklıdır. Ayrıntılar için [LICENSE](LICENSE).

<p align="center"><sub>Numan AK tarafından geliştirildi · Sakarya Üniversitesi Bilgisayar Mühendisliği</sub></p>
