from django.contrib import admin
from django import forms
from .models import (
	Customer, Supplier, Category, Ticket, CategorySupplierRule, TicketEmailReply,
	CustomerFeedback, OwnerReview, SupplierMetrics, CustomerMetrics
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
	list_display = ("name", "email", "phone", "organization", "user", "created_at")
	list_filter = ("organization",)
	search_fields = ("name", "email", "phone")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
	list_display = ("name", "email", "phone", "user", "created_at")
	filter_horizontal = ("organizations",)
	search_fields = ("name", "email", "phone")


class CategoryAdminForm(forms.ModelForm):
	class Meta:
		model = Category
		fields = ["organization", "name", "suppliers"]

	def clean(self):
		cleaned = super().clean()
		org = cleaned.get("organization")
		sups = cleaned.get("suppliers") or []
		if org:
			for s in sups:
				if s.organization_id != org.id:
					raise forms.ValidationError("Tüm tedarikçiler seçilen organizasyonda olmalıdır.")
		return cleaned


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
	form = CategoryAdminForm
	list_display = ("name", "organization", "suppliers_list", "created_at")
	list_filter = ("organization",)
	search_fields = ("name",)
	filter_horizontal = ("suppliers",)

	def suppliers_list(self, obj: Category):
		names = list(obj.suppliers.values_list("name", flat=True))
		return ", ".join(names) if names else "-"
	suppliers_list.short_description = "Suppliers"


	@admin.register(CategorySupplierRule)
	class CategorySupplierRuleAdmin(admin.ModelAdmin):
		list_display = ("label", "category", "organization", "is_active", "order", "min_quantity", "max_quantity", "field_name", "field_operator")
		list_filter = ("organization", "category", "is_active")
		search_fields = ("label", "field_name", "field_value")
		filter_horizontal = ("suppliers",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
	list_display = ("id", "title", "organization", "customer", "category", "status", "created_at")
	list_filter = ("organization", "status", "category")
	search_fields = ("title", "description")


@admin.register(TicketEmailReply)
class TicketEmailReplyAdmin(admin.ModelAdmin):
	list_display = ("ticket", "from_email", "supplier", "subject", "received_at")
	list_filter = ("supplier", "received_at")
	search_fields = ("from_email", "subject", "body")
	readonly_fields = ("ticket", "supplier", "from_email", "subject", "body", "received_at", "raw_data")


@admin.register(CustomerFeedback)
class CustomerFeedbackAdmin(admin.ModelAdmin):
	list_display = ("order", "supplier", "customer", "overall_satisfaction", "average_rating", "created_at")
	list_filter = ("organization", "supplier", "overall_satisfaction", "created_at")
	search_fields = ("customer__name", "supplier__name", "comment")
	readonly_fields = ("order", "supplier", "customer", "organization", "created_at", "average_rating")
	fieldsets = (
		("Genel Bilgiler", {
			"fields": ("order", "supplier", "customer", "organization", "created_at")
		}),
		("Değerlendirme", {
			"fields": ("product_quality", "communication", "delivery_time", "overall_satisfaction", "average_rating", "comment")
		}),
	)


@admin.register(OwnerReview)
class OwnerReviewAdmin(admin.ModelAdmin):
	list_display = ("get_target", "rating", "category", "reviewer", "organization", "created_at")
	list_filter = ("organization", "rating", "category", "created_at")
	search_fields = ("supplier__name", "customer__name", "comment")
	readonly_fields = ("created_at",)
	
	def get_target(self, obj):
		return obj.supplier.name if obj.supplier else obj.customer.name
	get_target.short_description = "Hedef"


@admin.register(SupplierMetrics)
class SupplierMetricsAdmin(admin.ModelAdmin):
	list_display = ("supplier", "overall_score", "win_rate_percent", "on_time_delivery_percent", "total_orders", "last_calculated")
	list_filter = ("organization", "last_calculated")
	search_fields = ("supplier__name",)
	readonly_fields = ("last_calculated",)
	fieldsets = (
		("Tedarikçi", {
			"fields": ("supplier", "organization")
		}),
		("Teklif Metrikleri", {
			"fields": ("total_quotes_sent", "total_quotes_accepted", "win_rate_percent", "avg_quote_response_hours")
		}),
		("Sipariş Metrikleri", {
			"fields": ("total_orders", "completed_orders", "on_time_deliveries", "on_time_delivery_percent")
		}),
		("Müşteri Memnuniyeti", {
			"fields": ("avg_product_quality", "avg_communication", "avg_delivery_rating", "avg_overall_satisfaction", "total_feedback_count")
		}),
		("Owner Değerlendirmesi", {
			"fields": ("avg_owner_rating", "owner_review_count")
		}),
		("Genel Skor", {
			"fields": ("overall_score", "last_calculated")
		}),
	)
	actions = ['recalculate_scores']
	
	def recalculate_scores(self, request, queryset):
		for metrics in queryset:
			metrics.calculate_score()
			metrics.save()
		self.message_user(request, f"{queryset.count()} tedarikçi skoru yeniden hesaplandı.")
	recalculate_scores.short_description = "Seçili skorları yeniden hesapla"


@admin.register(CustomerMetrics)
class CustomerMetricsAdmin(admin.ModelAdmin):
	list_display = ("customer", "overall_score", "conversion_rate_percent", "total_orders_placed", "total_spent", "last_calculated")
	list_filter = ("organization", "last_calculated")
	search_fields = ("customer__name",)
	readonly_fields = ("last_calculated",)
	fieldsets = (
		("Müşteri", {
			"fields": ("customer", "organization")
		}),
		("Talep ve Sipariş Metrikleri", {
			"fields": ("total_tickets_created", "total_orders_placed", "conversion_rate_percent", "avg_response_time_hours")
		}),
		("İptal ve Harcama", {
			"fields": ("cancelled_orders", "cancellation_rate_percent", "total_spent", "avg_order_value")
		}),
		("Owner Değerlendirmesi", {
			"fields": ("avg_owner_rating", "owner_review_count")
		}),
		("Genel Skor", {
			"fields": ("overall_score", "last_calculated")
		}),
	)
	actions = ['recalculate_scores']
	
	def recalculate_scores(self, request, queryset):
		for metrics in queryset:
			metrics.calculate_score()
			metrics.save()
		self.message_user(request, f"{queryset.count()} müşteri skoru yeniden hesaplandı.")
	recalculate_scores.short_description = "Seçili skorları yeniden hesapla"
