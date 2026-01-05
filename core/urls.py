from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("cookie-test/", views.cookie_test, name="cookie_test"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/widgets/", views.dashboard_widgets_settings, name="dashboard_widgets_settings"),
    path("landing/", views.role_landing, name="role_landing"),
    path("portal/", views.portal_home, name="portal_home"),
    path("customers/", views.customers_list, name="customers_list"),
    path("customers/new/", views.customers_create, name="customers_create"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/edit/", views.customers_edit, name="customers_edit"),
    path("customers/<int:pk>/delete/", views.customers_delete, name="customers_delete"),
    # Customer actions (from customer detail page)
    path("customers/<int:customer_id>/create-ticket/", views.customer_create_ticket, name="customer_create_ticket"),
    path("customers/<int:customer_id>/create-order/", views.customer_create_order, name="customer_create_order"),
    path("customers/<int:customer_id>/add-product/", views.customer_add_product, name="customer_add_product"),
    # Order templates
    path("customers/<int:customer_id>/order-templates/", views.customer_order_templates_list, name="customer_order_templates_list"),
    path("customers/<int:customer_id>/order-templates/save/", views.customer_save_order_template, name="customer_save_order_template"),
    path("customers/<int:customer_id>/order-templates/<int:template_id>/", views.customer_order_template_detail, name="customer_order_template_detail"),
    path("customers/<int:customer_id>/order-templates/<int:template_id>/delete/", views.customer_order_template_delete, name="customer_order_template_delete"),
    path("suppliers/", views.suppliers_list, name="suppliers_list"),
    path("suppliers/new/", views.suppliers_create, name="suppliers_create"),
    path("suppliers/<int:pk>/", views.supplier_detail, name="supplier_detail"),
    path("suppliers/<int:pk>/edit/", views.suppliers_edit, name="suppliers_edit"),
    path("suppliers/<int:pk>/delete/", views.suppliers_delete, name="suppliers_delete"),
    path("suppliers/check-email/", views.check_supplier_email, name="check_supplier_email"),
    path("check-username/", views.check_username, name="check_username"),
    path("tickets/", views.tickets_list, name="tickets_list"),
    path("tickets/new/", views.tickets_new, name="tickets_new"),
    path("tickets/<int:pk>/", views.ticket_detail_owner, name="ticket_detail_owner"),
    path("offers/", views.offers_list, name="offers_list"),
    path("products/", views.owner_products_list, name="owner_products_list"),
    path("products/new/", views.owner_products_new, name="owner_products_new"),
    path("products/<int:pk>/edit/", views.owner_products_edit, name="owner_products_edit"),
    path("products/<int:pk>/delete/", views.owner_products_delete, name="owner_products_delete"),
    path("orders/", views.orders_list, name="orders_list"),
    path("orders/new/", views.orders_create, name="orders_create"),
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
    # Customer feedback survey (no-auth via unique token)
    path("feedback/<uuid:token>/", views.customer_feedback_survey, name="customer_feedback_survey"),
    # Owner review submission
    path("review/add/", views.add_owner_review, name="add_owner_review"),
    # Email webhook for incoming replies
    path("webhook/email/", views.email_webhook, name="email_webhook"),
]

# Healthcheck & Monitoring URLs
from core.healthcheck_views import healthcheck, healthcheck_detailed, system_metrics

urlpatterns += [
    path('health/', healthcheck, name='healthcheck'),
    path('health/detailed/', healthcheck_detailed, name='healthcheck_detailed'),
    path('metrics/', system_metrics, name='system_metrics'),
]
