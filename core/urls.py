from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("landing/", views.role_landing, name="role_landing"),
    path("portal/", views.portal_home, name="portal_home"),
    path("customers/", views.customers_list, name="customers_list"),
    path("customers/new/", views.customers_create, name="customers_create"),
    path("customers/<int:pk>/edit/", views.customers_edit, name="customers_edit"),
    path("customers/<int:pk>/delete/", views.customers_delete, name="customers_delete"),
    path("suppliers/", views.suppliers_list, name="suppliers_list"),
    path("suppliers/new/", views.suppliers_create, name="suppliers_create"),
    path("suppliers/<int:pk>/edit/", views.suppliers_edit, name="suppliers_edit"),
    path("suppliers/<int:pk>/delete/", views.suppliers_delete, name="suppliers_delete"),
    path("suppliers/check-email/", views.check_supplier_email, name="check_supplier_email"),
    path("tickets/", views.tickets_list, name="tickets_list"),
    path("tickets/new/", views.tickets_new, name="tickets_new"),
    path("tickets/<int:pk>/", views.ticket_detail_owner, name="ticket_detail_owner"),
    path("offers/", views.offers_list, name="offers_list"),
    path("products/", views.owner_products_list, name="owner_products_list"),
    path("products/new/", views.owner_products_new, name="owner_products_new"),
    path("orders/", views.orders_list, name="orders_list"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    # Categories (Owner only)
    path("categories/", views.categories_list, name="categories_list"),
    path("categories/new/", views.categories_create, name="categories_create"),
    path("categories/<int:pk>/edit/", views.categories_edit, name="categories_edit"),
    path("categories/<int:pk>/delete/", views.categories_delete, name="categories_delete"),
    # Owner: Category dynamic form fields
    path("categories/<int:category_id>/fields/", views.category_form_fields_list, name="category_form_fields_list"),
    path("categories/<int:category_id>/fields/new/", views.category_form_fields_new, name="category_form_fields_new"),
    path("categories/<int:category_id>/fields/<int:pk>/edit/", views.category_form_fields_edit, name="category_form_fields_edit"),
    path("categories/<int:category_id>/fields/<int:pk>/delete/", views.category_form_fields_delete, name="category_form_fields_delete"),
    # Owner: Category routing rules
    path("categories/<int:category_id>/rules/", views.category_rules_list, name="category_rules_list"),
    path("categories/<int:category_id>/rules/new/", views.category_rules_new, name="category_rules_new"),
    path("categories/<int:category_id>/rules/<int:pk>/edit/", views.category_rules_edit, name="category_rules_edit"),
    path("categories/<int:category_id>/rules/<int:pk>/delete/", views.category_rules_delete, name="category_rules_delete"),
    # Portals
    path("portal/customer/", views.customer_portal, name="customer_portal"),
    path("portal/supplier/", views.supplier_portal, name="supplier_portal"),
    # Customer portal requests
    path("portal/customer/requests/", views.customer_requests_list, name="customer_requests_list"),
    path("portal/customer/requests/new/", views.customer_requests_new, name="customer_requests_new"),
    path("portal/customer/requests/<int:pk>/edit/", views.customer_requests_edit, name="customer_requests_edit"),
    path("portal/customer/requests/<int:pk>/delete/", views.customer_requests_delete, name="customer_requests_delete"),
    path("portal/customer/requests/<int:pk>/", views.customer_requests_detail, name="customer_requests_detail"),
    path("portal/customer/offers/", views.customer_offers_list, name="customer_offers_list"),
    path("portal/customer/offers/<int:pk>/", views.customer_offers_detail, name="customer_offers_detail"),
    path("portal/customer/offers/<int:pk>/pdf/", views.customer_offers_pdf, name="customer_offers_pdf"),
    path("portal/customer/orders/", views.customer_orders_list, name="customer_orders_list"),
    path("portal/customer/products/", views.customer_products_list, name="customer_products_list"),
    path("portal/supplier/requests/", views.supplier_requests_list, name="supplier_requests_list"),
    path("portal/supplier/requests/<int:pk>/", views.supplier_requests_detail, name="supplier_requests_detail"),
    path("portal/supplier/offers/", views.supplier_quotes_list, name="supplier_quotes_list"),
    path("portal/supplier/orders/", views.supplier_orders_list, name="supplier_orders_list"),
    path("portal/supplier/orders/<int:pk>/", views.supplier_order_detail, name="supplier_order_detail"),
    # Supplier products
    path("portal/supplier/products/", views.supplier_products_list, name="supplier_products_list"),
    path("portal/supplier/products/new/", views.supplier_products_new, name="supplier_products_new"),
    path("portal/supplier/products/<int:pk>/edit/", views.supplier_products_edit, name="supplier_products_edit"),
    path("portal/supplier/products/<int:pk>/delete/", views.supplier_products_delete, name="supplier_products_delete"),
    # No-auth supplier access via token
    path("supplier-access/<uuid:token>/", views.supplier_access_token, name="supplier_access_token"),
    # Email webhook for incoming replies
    path("webhook/email/", views.email_webhook, name="email_webhook"),
]
