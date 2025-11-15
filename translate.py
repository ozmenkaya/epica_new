#!/usr/bin/env python3
"""
Translation helper script for Epica
Automatically translates common Turkish->English strings in .po files
"""

TRANSLATIONS = {
    # UI Common
    "Türkçe": "Turkish",
    "English": "English",
    "Giriş": "Login",
    "Giriş Yap": "Login",
    "Çıkış": "Logout",
    "Kaydet": "Save",
    "İptal": "Cancel",
    "Sil": "Delete",
    "Düzenle": "Edit",
    "Ekle": "Add",
    "Yeni": "New",
    "Liste": "List",
    "Detay": "Detail",
    "Ara": "Search",
    "Filtrele": "Filter",
    "Temizle": "Clear",
    "Geri": "Back",
    "İleri": "Next",
    "Önceki": "Previous",
    "Sonraki": "Next",
    "İşlem": "Action",
    "Durum": "Status",
    "Tarih": "Date",
    "Saat": "Time",
    "Açıklama": "Description",
    "Not": "Note",
    "Yorum": "Comment",
    "Oluştur": "Create",
    "Güncelle": "Update",
    "Aktif": "Active",
    "Pasif": "Inactive",
    "Evet": "Yes",
    "Hayır": "No",
    
    # Navigation & Pages
    "Dashboard": "Dashboard",
    "Anasayfa": "Home",
    "Ayarlar": "Settings",
    "Profil": "Profile",
    "Hesap": "Account",
    "Organizasyonlar": "Organizations",
    "Organizasyonlarım": "My Organizations",
    "Yeni Organizasyon": "New Organization",
    "Yeni organizasyon": "New organization",
    "Geç": "Switch",
    
    # Business Entities
    "Müşteri": "Customer",
    "Müşteriler": "Customers",
    "Müşteri Portalım": "My Customer Portal",
    "Tedarikçi": "Supplier",
    "Tedarikçiler": "Suppliers",
    "Tedarikçi Portalım": "My Supplier Portal",
    "Kategori": "Category",
    "Kategoriler": "Categories",
    "Ürün": "Product",
    "Ürünler": "Products",
    "Ürünlerim": "My Products",
    "Talep": "Request",
    "Talepler": "Requests",
    "Taleplerim": "My Requests",
    "Teklif": "Quote",
    "Teklifler": "Quotes",
    "Tekliflerim": "My Quotes",
    "Sipariş": "Order",
    "Siparişler": "Orders",
    "Siparişlerim": "My Orders",
    
    # Forms & Fields
    "İsim": "Name",
    "Ad": "Name",
    "Soyad": "Surname",
    "E-posta": "Email",
    "Email": "Email",
    "Telefon": "Phone",
    "Adres": "Address",
    "Şehir": "City",
    "Ülke": "Country",
    "Şifre": "Password",
    "Yeni Şifre": "New Password",
    "Şifre Tekrar": "Password Confirmation",
    "Kullanıcı Adı": "Username",
    "Başlık": "Title",
    "İçerik": "Content",
    "Miktar": "Quantity",
    "Fiyat": "Price",
    "Toplam": "Total",
    "Birim": "Unit",
    "Para Birimi": "Currency",
    "KDV": "VAT",
    "İndirim": "Discount",
    "Kargo": "Shipping",
    "Ödeme": "Payment",
    "Ödeme Yöntemi": "Payment Method",
    "Teslimat": "Delivery",
    "Teslimat Adresi": "Delivery Address",
    "Fatura Adresi": "Billing Address",
    
    # Form Field Types
    "Etiket": "Label",
    "Alan Adı": "Field Name",
    "Alan Tipi": "Field Type",
    "Metin": "Text",
    "Seçim (Dropdown)": "Select (Dropdown)",
    "Seçenekler": "Options",
    "Zorunlu": "Required",
    "Sıra": "Order",
    "Yardım Metni": "Help Text",
    "Alan Tanımı": "Field Definition",
    "Veri anahtarı (otomatik üretilebilir)": "Data key (can be auto-generated)",
    "Select için seçenekleri satır satır yazın": "Write options line by line for Select",
    "- Alan seçin -": "- Select field -",
    "Miktar (form-0-quantity)": "Quantity (form-0-quantity)",
    "- Değer seçin -": "- Select value -",
    
    # Category Rules
    "Kategori Kuralları": "Category Rules",
    "Kural": "Rule",
    "Kurallar": "Rules",
    "Yeni Kural": "New Rule",
    "En Az Adet": "Minimum Quantity",
    "En Çok Adet": "Maximum Quantity",
    "Operatör": "Operator",
    "Değer": "Value",
    "Alan Koşulu": "Field Condition",
    "Adet Aralığı": "Quantity Range",
    "içerir": "contains",
    "şunlardan biri (virgülle ayırın)": "one of (comma-separated)",
    "Kategori form alan anahtarı": "Category form field key",
    "Alan filtresi için alan adı gereklidir.": "Field name is required for field filter.",
    "En az adet, en çok adetten büyük olamaz.": "Minimum quantity cannot be greater than maximum quantity.",
    "Alan anahtarları": "Field keys",
    "Alanı Sil": "Delete Field",
    "Evet, Sil": "Yes, Delete",
    '"{{ label }}" alanını silmek istediğinize emin misiniz?': 'Are you sure you want to delete the "{{ label }}" field?',
    "Konu": "Subject",
    
    # AI Assistant
    "AI Asistan": "AI Assistant",
    "Sohbetler": "Conversations",
    "Henüz sohbet yok": "No conversations yet",
    "AI Asistan Neler Yapabilir?": "What Can AI Assistant Do?",
    "Talep ve tekliflerinizi sorgula": "Query your requests and quotes",
    "İstatistik ve analiz yap": "Perform statistics and analysis",
    "Talep durumu güncelle": "Update request status",
    "Tedarikçi bilgisi ara": "Search supplier information",
    "Merhaba! Size nasıl yardımcı olabilirim?": "Hello! How can I help you?",
    "Talepler, teklifler, tedarikçiler hakkında soru sorabilir veya işlem yapabilirsiniz.": "You can ask questions or perform actions about requests, quotes, and suppliers.",
    "Mesajınızı yazın...": "Type your message...",
    "Gönder": "Send",
    "AI asistan beta aşamasındadır. Önemli kararlar için doğrulamayı unutmayın.": "AI assistant is in beta. Please verify important decisions.",
    "Henüz kural yok.": "No rules yet.",
    "ve": "and",
    
    # Supplier Form
    "Mevcut Tedarikçi Bulundu": "Existing Supplier Found",
    "isimli tedarikçi sistemde zaten kayıtlı.": "supplier already exists in the system.",
    "Bu tedarikçiyi organizasyonunuza eklemek istiyor musunuz?": "Would you like to add this supplier to your organization?",
    
    # Portal & Common
    "Organizasyon": "Organization",
    "Form Yanıtları": "Form Responses",
    "Genel toplam": "Grand total",
    "Teklife Yorum Yaz": "Write Comment on Quote",
    "Yorumu Gönder": "Send Comment",
    "Dosya boyutu {max_size / (1024*1024):.0f}MB'dan büyük olamaz.": "File size cannot exceed {max_size / (1024*1024):.0f}MB.",
    "İzin verilen dosya formatları: {', '.join(allowed_extensions)}": "Allowed file formats: {', '.join(allowed_extensions)}",
    
    # Status & Messages
    "Bekliyor": "Pending",
    "Onaylandı": "Approved",
    "Onaylandı": "Confirmed",
    "Reddedildi": "Rejected",
    "İptal Edildi": "Cancelled",
    "İptal": "Cancelled",
    "Tamamlandı": "Completed",
    "Gönderildi": "Sent",
    "Alındı": "Received",
    "İşleniyor": "Processing",
    "Başarılı": "Success",
    "Başarısız": "Failed",
    "Hata": "Error",
    "Uyarı": "Warning",
    "Bilgi": "Info",
    
    # Email Settings
    "E-posta Ayarları": "Email Settings",
    "SMTP Sunucu": "SMTP Server",
    "SMTP Sunucusu": "SMTP Server",
    "Port": "Port",
    "TLS Kullan": "Use TLS",
    "SSL Kullan": "Use SSL",
    "Kullanıcı Adı": "Username",
    "Parola": "Password",
    "Gönderici E-posta": "Sender Email",
    "Gönderici Adı": "Sender Name",
    
    # Time & Date
    "Bugün": "Today",
    "Dün": "Yesterday",
    "Yarın": "Tomorrow",
    "Hafta": "Week",
    "Ay": "Month",
    "Yıl": "Year",
    "Saat": "Hour",
    "Dakika": "Minute",
    "Saniye": "Second",
    "Oluşturulma Tarihi": "Created Date",
    "Güncellenme Tarihi": "Updated Date",
    "Kayıt Tarihi": "Registration Date",
    
    # Actions & Operations
    "Yükle": "Upload",
    "İndir": "Download",
    "Yazdır": "Print",
    "Dışa Aktar": "Export",
    "İçe Aktar": "Import",
    "Kopyala": "Copy",
    "Yapıştır": "Paste",
    "Kes": "Cut",
    "Seç": "Select",
    "Seç Tümünü": "Select All",
    "Temizle Seçimi": "Clear Selection",
    "Onayla": "Confirm",
    "Reddet": "Reject",
    "Gönder": "Send",
    "Al": "Receive",
    
    # Metrics & Performance
    "Değerlendirme Ekle": "Add Review",
    "Değerlendirmeler": "Reviews",
    "Yönetici Değerlendirmeleri": "Manager Reviews",
    "Puan": "Score",
    "Derecelendirme": "Rating",
    "Yıldız": "Star",
    "Performans": "Performance",
    "İstatistikler": "Statistics",
    "Rapor": "Report",
    "Analiz": "Analysis",
    "Grafik": "Chart",
    "Özet": "Summary",
    
    # Specific Business Terms
    "Toplam Talep": "Total Requests",
    "Siparişe Dönüşen": "Converted to Order",
    "Alınan Teklif": "Received Quotes",
    "Müşteri Skoru": "Customer Score",
    "Tedarikçi Skoru": "Supplier Score",
    "Müşteri Performansı": "Customer Performance",
    "Tedarikçi Performansı": "Supplier Performance",
    "Dönüşüm Oranı": "Conversion Rate",
    "İptal Oranı": "Cancellation Rate",
    "Yanıt Hızı": "Response Speed",
    "Toplam Harcama": "Total Spending",
    "Güvenilirlik": "Reliability",
    "İletişim": "Communication",
    "Kalite": "Quality",
    "Fiyatlandırma": "Pricing",
    
    # Common Phrases
    "Hiç organizasyon yok.": "No organizations available.",
    "Lütfen formu kontrol edin.": "Please check the form.",
    "İşlem başarılı.": "Operation successful.",
    "İşlem başarısız.": "Operation failed.",
    "Emin misiniz?": "Are you sure?",
    "Bu işlem geri alınamaz.": "This action cannot be undone.",
    "Değişiklikler kaydedildi.": "Changes saved.",
    "Kayıt bulunamadı.": "Record not found.",
    "Yetkiniz yok.": "You don't have permission.",
    "Oturum açmanız gerekiyor.": "You need to login.",
}

def update_po_file(po_path):
    """Update .po file with translations"""
    import re
    
    with open(po_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to find msgid/msgstr pairs
    pattern = r'msgid "([^"]+)"\nmsgstr ""'
    
    def replace_empty(match):
        msgid = match.group(1)
        if msgid in TRANSLATIONS:
            return f'msgid "{msgid}"\nmsgstr "{TRANSLATIONS[msgid]}"'
        return match.group(0)
    
    updated_content = re.sub(pattern, replace_empty, content)
    
    with open(po_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print(f"Updated: {po_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        update_po_file(sys.argv[1])
    else:
        # Update English translation by default
        update_po_file("locale/en/LC_MESSAGES/django.po")
