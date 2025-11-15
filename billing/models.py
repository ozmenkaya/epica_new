from django.db import models
from decimal import Decimal
from accounts.models import Organization
from core.models import Ticket, Quote, QuoteItem, SupplierProduct, Supplier, CURRENCY_CHOICES


class Order(models.Model):
	class Status(models.TextChoices):
		NEW = "new", "New"
		PROCESSING = "processing", "Processing"
		COMPLETED = "completed", "Completed"
		CANCELLED = "cancelled", "Cancelled"

	organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="orders")
	ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="order")
	quote = models.ForeignKey(Quote, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
	supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
	currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="TRY")
	total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
	# Supplier-side acknowledgement and scheduling
	supplier_acknowledged = models.BooleanField(default=False)
	supplier_eta = models.DateField(null=True, blank=True)
	supplier_note = models.TextField(blank=True)
	# Delivery tracking for metrics
	estimated_delivery_date = models.DateField(null=True, blank=True, help_text="Owner tarafından belirlenen tahmini teslimat tarihi")
	actual_delivery_date = models.DateField(null=True, blank=True, help_text="Gerçek teslimat tarihi")
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]
		indexes = [
			models.Index(fields=["organization", "status"]),
			models.Index(fields=['organization', 'status', '-created_at'], name='order_org_status_created_idx'),
			models.Index(fields=['supplier', 'status'], name='order_supplier_status_idx'),
			models.Index(fields=['status', '-created_at'], name='order_status_created_idx'),
		]

	def __str__(self) -> str:
		return f"Order #{self.pk} / Ticket #{self.ticket_id}"


class OrderItem(models.Model):
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
	product = models.ForeignKey(SupplierProduct, on_delete=models.SET_NULL, null=True, blank=True)
	description = models.CharField(max_length=255)
	quantity = models.PositiveIntegerField(default=1)
	supplier_unit_price = models.DecimalField(max_digits=12, decimal_places=2)
	owner_markup_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
	sell_total = models.DecimalField(max_digits=12, decimal_places=2)

	class Meta:
		ordering = ["id"]

	def __str__(self) -> str:
		return f"{self.description} x{self.quantity}"
