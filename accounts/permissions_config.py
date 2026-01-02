# Sayfa yetkileri tanımları
PAGE_PERMISSIONS = {
    'dashboard': {
        'name': 'Dashboard',
        'codename': 'view_dashboard',
        'description': 'Dashboard sayfasını görüntüleme'
    },
    'org_create': {
        'name': 'Organizasyon Oluşturma',
        'codename': 'add_organization',
        'description': 'Yeni organizasyon oluşturma'
    },
    'customers_list': {
        'name': 'Müşteriler Listesi',
        'codename': 'view_customers',
        'description': 'Müşteri listesini görüntüleme'
    },
    'customers_create': {
        'name': 'Müşteri Ekleme',
        'codename': 'add_customers',
        'description': 'Yeni müşteri ekleme'
    },
    'customers_edit': {
        'name': 'Müşteri Düzenleme',
        'codename': 'change_customers',
        'description': 'Müşteri bilgilerini düzenleme'
    },
    'customers_delete': {
        'name': 'Müşteri Silme',
        'codename': 'delete_customers',
        'description': 'Müşteri silme'
    },
    'suppliers_list': {
        'name': 'Tedarikçiler Listesi',
        'codename': 'view_suppliers',
        'description': 'Tedarikçi listesini görüntüleme'
    },
    'suppliers_create': {
        'name': 'Tedarikçi Ekleme',
        'codename': 'add_suppliers',
        'description': 'Yeni tedarikçi ekleme'
    },
    'suppliers_edit': {
        'name': 'Tedarikçi Düzenleme',
        'codename': 'change_suppliers',
        'description': 'Tedarikçi bilgilerini düzenleme'
    },
    'suppliers_delete': {
        'name': 'Tedarikçi Silme',
        'codename': 'delete_suppliers',
        'description': 'Tedarikçi silme'
    },
    'categories_list': {
        'name': 'Kategoriler',
        'codename': 'view_categories',
        'description': 'Kategori listesini görüntüleme'
    },
    'categories_manage': {
        'name': 'Kategori Yönetimi',
        'codename': 'manage_categories',
        'description': 'Kategori ekleme, düzenleme, silme'
    },
    'tickets_list': {
        'name': 'Talepler',
        'codename': 'view_tickets',
        'description': 'Talep listesini görüntüleme'
    },
    'tickets_create': {
        'name': 'Talep Oluşturma',
        'codename': 'add_tickets',
        'description': 'Yeni talep oluşturma'
    },
    'offers_list': {
        'name': 'Teklifler',
        'codename': 'view_offers',
        'description': 'Teklif listesini görüntüleme'
    },
    'orders_list': {
        'name': 'Siparişler',
        'codename': 'view_orders',
        'description': 'Sipariş listesini görüntüleme'
    },
    'orders_manage': {
        'name': 'Sipariş Yönetimi',
        'codename': 'manage_orders',
        'description': 'Sipariş onaylama, düzenleme'
    },
    'products_list': {
        'name': 'Ürünler',
        'codename': 'view_products',
        'description': 'Ürün listesini görüntüleme'
    },
    'products_manage': {
        'name': 'Ürün Yönetimi',
        'codename': 'manage_products',
        'description': 'Ürün ekleme, düzenleme, silme'
    },
    'reports': {
        'name': 'Raporlar',
        'codename': 'view_reports',
        'description': 'Raporları görüntüleme'
    },
    'settings': {
        'name': 'Ayarlar',
        'codename': 'change_settings',
        'description': 'Organizasyon ayarlarını değiştirme'
    },
}

# Rol bazlı varsayılan yetkiler
ROLE_DEFAULT_PERMISSIONS = {
    'owner': list(PAGE_PERMISSIONS.keys()),  # Tüm yetkiler
    'admin': [
        'dashboard',
        'customers_list', 'customers_create', 'customers_edit', 'customers_delete',
        'suppliers_list', 'suppliers_create', 'suppliers_edit', 'suppliers_delete',
        'tickets_list', 'tickets_create',
        'offers_list',
        'orders_list',
        'products_list', 'products_manage',
    ],
    'member': [
        'dashboard',
        'customers_list',
        'suppliers_list',
        'tickets_list',
    ],
}
