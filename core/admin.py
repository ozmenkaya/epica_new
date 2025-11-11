from django.contrib import admin
from django import forms
from .models import Customer, Supplier, Category, Ticket, CategorySupplierRule, TicketEmailReply


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
