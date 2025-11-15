# AI Assistant - Setup & Usage Guide

## 🎉 Sistem Başarıyla Kuruldu!

AI Assistant sistemi Epica'ya entegre edildi. Self-learning (kendi kendine öğrenen) bir yapay zeka asistanı.

## 🔧 Kurulum

### 1. Dependencies (✅ Tamamlandı)
```bash
pip install openai numpy
```

### 2. Migrations (✅ Tamamlandı)
```bash
python manage.py makemigrations ai_assistant
python manage.py migrate
```

### 3. OpenAI API Key Ayarı (❗ GEREKLİ)

`.env` dosyanıza ekleyin:
```bash
OPENAI_API_KEY=sk-proj-your-api-key-here
OPENAI_MODEL=gpt-4o-mini  # Opsiyonel, default: gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small  # Opsiyonel
```

**API Key Almak İçin:**
1. https://platform.openai.com/ adresine gidin
2. API Keys bölümünden yeni key oluşturun
3. Key'i `.env` dosyasına ekleyin

## 🚀 Kullanım

### Web Interface
- URL: `/ai/chat/`
- Navbar'da "AI Asistan" linki (sadece owner'lar için)
- Chat interface ile soru sorabilir, komut verebilirsiniz

### Özellikler

#### 1. Soru-Cevap
- "Son 1 aydaki ticket'larımın durumu nedir?"
- "Hangi kategoride en çok talep var?"
- "X tedarikçisinin iletişim bilgileri nedir?"

#### 2. Analiz
- "Bu ay kaç ticket açıldı?"
- "Pending durumunda kaç talep var?"
- "En çok hangi kategoride işlem yapılıyor?"

#### 3. Komut Çalıştırma
- "Ticket #123'ün durumunu completed yap"
- "ABC tedarikçisini ara"
- "Son 5 talebi göster"

### Self-Learning (Otomatik Öğrenme)

Sistem otomatik olarak şunları öğrenir:
- ✅ **Ticket'lar**: Yeni ticket oluşturulduğunda veya güncellendiğinde
- ✅ **Quote'lar**: Yeni teklif geldiğinde
- ✅ **Supplier'lar**: Tedarikçi eklendiğinde/güncellendiğinde

**Nasıl Çalışır:**
1. Yeni bir ticket/quote/supplier oluşturulur
2. Django signals otomatik tetiklenir
3. İçerik OpenAI embeddings ile vektörleştirilir
4. `EmbeddedDocument` modelinde saklanır
5. AI sorulara cevap verirken bu bilgileri kullanır

## 📊 Database Modelleri

### Conversation
- Kullanıcıların AI ile yaptığı sohbetler
- Organization bazlı izolasyon

### Message
- Sohbet içindeki mesajlar
- User/Assistant/System rolleri
- Token kullanım takibi

### AIAction
- AI'ın yaptığı işlemler (log)
- Status tracking (success/failed)
- Input/output data

### EmbeddedDocument
- Vektörleştirilmiş dökümanlar
- Semantic search için kullanılır
- Organization bazlı izolasyon

## 🔍 Kod Yapısı

```
ai_assistant/
├── models.py              # Database modelleri
├── admin.py               # Django admin
├── views.py               # Chat API ve UI
├── urls.py                # URL routing
├── signals.py             # Auto-learning signals
├── apps.py                # App configuration
├── services/
│   ├── embedder.py        # Embedding oluşturma
│   ├── retriever.py       # Semantic search
│   ├── agent.py           # OpenAI agent
│   └── actions.py         # AI komutları
└── migrations/
    └── 0001_initial.py    # Initial migration
```

## 💰 Maliyet

OpenAI GPT-4o-mini kullanıyor (çok ucuz):
- Input: $0.15 / 1M tokens
- Output: $0.60 / 1M tokens
- Embeddings: $0.02 / 1M tokens

**Tahmini aylık maliyet:**
- 1000 soru: ~$2-5
- 10000 soru: ~$20-50

## 🧪 Test

```bash
# Development server başlat
python manage.py runserver

# Browser'da aç
http://localhost:8000/ai/chat/

# Test soruları:
1. "Bu ay kaç ticket açıldı?"
2. "Pending durumunda kaç talep var?"
3. "Son 5 talebi göster"
```

## 🔒 Güvenlik

- ✅ Her organizasyon sadece kendi verilerine erişebilir
- ✅ AI sadece kullanıcının yetkisi dahilinde işlem yapar
- ✅ Tüm AI eylemleri loglanır (`AIAction` modeli)
- ✅ OpenAI API key environment variable'da saklanır

## 📈 Sonraki Adımlar

### Kısa Vadede (Opsiyonel)
- [ ] Email gönderme özelliği ekle
- [ ] Daha fazla action type ekle
- [ ] Raporlama fonksiyonları
- [ ] Voice input desteği

### Uzun Vadede
- [ ] Python 3.10+ upgrade → LangChain ekle
- [ ] Daha gelişmiş RAG pipeline
- [ ] Fine-tuning (özel model)
- [ ] Multi-modal support (görsel analiz)

## 🆘 Troubleshooting

### "No module named 'openai'"
```bash
pip install openai numpy
```

### "OPENAI_API_KEY not set"
`.env` dosyasına API key ekleyin:
```bash
OPENAI_API_KEY=sk-proj-...
```

### "Organization not found"
URL'de organization seçin:
```
http://localhost:8000/ai/chat/?org=your-org-slug
```

### Embeddings çalışmıyor
Signals'ı kontrol edin:
```python
# ai_assistant/apps.py'de ready() çağrılıyor mu?
```

## 📝 Notlar

- Sistem şu anda **OpenAI only** (LangChain/ChromaDB yok - Python 3.9 uyumluluğu için)
- Embeddings PostgreSQL JSONField'de saklanıyor (pgvector gerekmez)
- Production'da OPENAI_API_KEY mutlaka set edilmeli
- Her organization'ın verisi izole (multi-tenant safe)

## 🎯 Sonuç

✅ Sistem hazır!
✅ Self-learning aktif!
✅ Chat interface çalışıyor!

Sadece `.env` dosyasına `OPENAI_API_KEY` ekleyin ve kullanmaya başlayın! 🚀
