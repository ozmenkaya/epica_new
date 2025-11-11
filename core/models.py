from django.db import models
from decimal import Decimal
from django.contrib.auth import get_user_model
from accounts.models import Organization
from django.core.exceptions import ValidationError
import uuid

User = get_user_model()

class Customer(models.Model):
	organization = models.ForeignKey(
		Organization, on_delete=models.CASCADE, related_name="customers"
	)
	user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_profile")
	name = models.CharField(max_length=200)
	email = models.EmailField(blank=True, null=True)
	phone = models.CharField(max_length=50, blank=True)
	notes = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["name"]
		indexes = [
			models.Index(fields=["organization", "name"]),
		]
		constraints = [
			models.UniqueConstraint(
				fields=["organization", "email"],
				condition=models.Q(email__isnull=False),
				name="unique_customer_email_per_org"
			),
		]

	def __str__(self) -> str:
		return f"{self.name}"


class Supplier(models.Model):
	organizations = models.ManyToManyField(
		Organization, related_name="suppliers", verbose_name="Organizasyonlar"
	)
	user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_profile")
	name = models.CharField(max_length=200)
	email = models.EmailField(blank=True, null=True, unique=True)
	phone = models.CharField(max_length=50, blank=True)
	notes = models.TextField(blank=True)
	is_simplified = models.BooleanField(default=False, verbose_name="Basit Usul")
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["name"]

	def __str__(self) -> str:
		return f"{self.name}"


class SupplierProduct(models.Model):
	"""Products managed by suppliers, scoped to organization and category owned by org."""
	organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="supplier_products")
	supplier = models.ForeignKey('Supplier', on_delete=models.CASCADE, related_name='products')
	category = models.ForeignKey('Category', on_delete=models.PROTECT, related_name='products')
	name = models.CharField(max_length=200)
	description = models.TextField(blank=True)
	base_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["name"]
		unique_together = (("supplier", "name"),)

	def clean(self):
		# Validate supplier is in this organization
		if self.organization_id and self.supplier_id:
			if not self.supplier.organizations.filter(pk=self.organization_id).exists():
				raise ValidationError("Tedarikçi bu organizasyonda bulunmuyor.")
		# Validate category is in same organization
		if self.organization_id and self.category_id and self.organization_id != self.category.organization_id:
			raise ValidationError("Ürün ve kategori aynı organizasyonda olmalıdır.")

	def __str__(self) -> str:
		return f"{self.name}"


class Category(models.Model):
	"""Organization-scoped category that maps to one or more Suppliers."""
	organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="categories")
	parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name="Üst Kategori")
	name = models.CharField(max_length=200)
	suppliers = models.ManyToManyField('Supplier', related_name='categories', blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["name"]
		unique_together = (("organization", "name"),)

	def clean(self):
		# Validate that all selected suppliers are in this organization
		if self.organization_id and self.pk:
			for sup in self.suppliers.all():
				if not sup.organizations.filter(pk=self.organization_id).exists():
					raise ValidationError(f"Tedarikçi '{sup.name}' bu organizasyonda bulunmuyor.")
		# Validate parent category is in same organization
		if self.parent_id and self.organization_id:
			if self.parent.organization_id != self.organization_id:
				raise ValidationError("Üst kategori aynı organizasyonda olmalıdır.")
		# Prevent circular reference
		if self.parent_id and self.pk and self.parent_id == self.pk:
			raise ValidationError("Kategori kendi üst kategorisi olamaz.")

	def __str__(self) -> str:
		if self.parent:
			return f"{self.parent.name} > {self.name}"
		return f"{self.name}"
	
	def get_full_path(self):
		"""Return full category path from root to this category."""
		path = [self.name]
		parent = self.parent
		while parent:
			path.insert(0, parent.name)
			parent = parent.parent
		return " > ".join(path)


class CategorySupplierRule(models.Model):
	"""Rule to dynamically route tickets in a category to specific suppliers.
	A rule matches if both quantity and field conditions (when provided) evaluate true.
	If no rules match, fallback to category.suppliers.
	"""
	organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="category_supplier_rules")
	category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='supplier_rules')
	label = models.CharField(max_length=120)
	is_active = models.BooleanField(default=True)
	order = models.PositiveIntegerField(default=0)
	# Quantity condition
	min_quantity = models.PositiveIntegerField(null=True, blank=True)
	max_quantity = models.PositiveIntegerField(null=True, blank=True)
	# Dynamic field condition (matches Ticket.extra_data)
	field_name = models.CharField(max_length=100, blank=True, help_text="Category form field key (name)")
	field_operator = models.CharField(max_length=20, blank=True, choices=(
		("eq", "="), 
		("neq", "!="), 
		("gt", ">"), 
		("gte", ">="), 
		("lt", "<"), 
		("lte", "<="), 
		("contains", "içerir"), 
		("in", "şunlardan biri (virgülle ayırın)")
	))
	field_value = models.CharField(max_length=255, blank=True)
	suppliers = models.ManyToManyField('Supplier', related_name='category_rules', blank=True)

	class Meta:
		ordering = ["category", "order", "id"]

	def __str__(self) -> str:
		return f"{self.category.name} :: {self.label}"

	def matches(self, ticket: 'Ticket') -> bool:
		if not self.is_active:
			return False
		# org/category guard
		if self.organization_id and ticket.organization_id and self.organization_id != ticket.organization_id:
			return False
		if self.category_id and ticket.category_id and self.category_id != ticket.category_id:
			return False
		# Quantity check
		q_ok = True
		try:
			qty = ticket.desired_quantity or 0
		except Exception:
			qty = 0
		if self.min_quantity is not None and qty < self.min_quantity:
			q_ok = False
		if self.max_quantity is not None and qty > self.max_quantity:
			q_ok = False
		if not q_ok:
			return False
		# Field check (optional, supports comma-separated multi field names and values)
		if self.field_name:
			data = ticket.extra_data or {}
			# Parse field names and target values as lists
			field_names = [n.strip() for n in str(self.field_name).split(',') if n.strip()]
			op = (self.field_operator or "").strip()
			target_values = [v.strip() for v in str(self.field_value or "").split(',') if v.strip()]
			# If no names parsed, treat as non-restrictive
			if not field_names:
				return True
			# Evaluate OR across field names and OR across values for eq/contains; for neq require value not in targets
			matched = False
			for fname in field_names:
				val = data.get(fname)
				if op == "eq":
					if not target_values:
						if val not in (None, ""):
							matched = True
					else:
						if any(str(val) == tv for tv in target_values):
							matched = True
				elif op == "neq":
					if not target_values:
						# any non-empty passes
						if val in (None, ""):
							matched = False
						else:
							matched = True
					else:
						if all(str(val) != tv for tv in target_values):
							matched = True
				elif op == "gt":
					# Greater than: value > target (numeric comparison)
					if val is not None and target_values:
						try:
							val_num = float(val)
							if any(val_num > float(tv) for tv in target_values):
								matched = True
						except (ValueError, TypeError):
							pass
				elif op == "gte":
					# Greater than or equal: value >= target (numeric comparison)
					if val is not None and target_values:
						try:
							val_num = float(val)
							if any(val_num >= float(tv) for tv in target_values):
								matched = True
						except (ValueError, TypeError):
							pass
				elif op == "lt":
					# Less than: value < target (numeric comparison)
					if val is not None and target_values:
						try:
							val_num = float(val)
							if any(val_num < float(tv) for tv in target_values):
								matched = True
						except (ValueError, TypeError):
							pass
				elif op == "lte":
					# Less than or equal: value <= target (numeric comparison)
					if val is not None and target_values:
						try:
							val_num = float(val)
							if any(val_num <= float(tv) for tv in target_values):
								matched = True
						except (ValueError, TypeError):
							pass
				elif op == "contains":
					if val is None:
						continue
					if not target_values:
						# contains with empty target: treat as True if value non-empty
						if str(val):
							matched = True
					else:
						if any(tv in str(val) for tv in target_values):
							matched = True
				elif op == "in":
					# classic membership: value must be one of targets
					if any(str(val) == tv for tv in target_values):
						matched = True
				else:
					# unknown operator -> don't enforce
					matched = True
				if matched:
					break
			if not matched:
				return False
		return True


class CategoryFormField(models.Model):
	"""Owner-defined dynamic form field for a Category (customer request creation)."""
	class FieldType(models.TextChoices):
		TEXT = "text", "Metin"
		SELECT = "select", "Seçim (Dropdown)"

	organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="category_form_fields")
	category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='form_fields')
	label = models.CharField(max_length=100)
	name = models.SlugField(max_length=100, help_text="Veri anahtarı (otomatik üretilebilir)")
	field_type = models.CharField(max_length=10, choices=FieldType.choices, default=FieldType.TEXT)
	options = models.TextField(blank=True, help_text="Select için seçenekleri satır satır yazın")
	required = models.BooleanField(default=False)
	order = models.PositiveIntegerField(default=0)
	help_text = models.CharField(max_length=200, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["category", "order", "id"]
		unique_together = (("category", "name"),)

	def clean(self):
		# Organization consistency
		if self.organization_id and self.category_id and self.organization_id != self.category.organization_id:
			raise ValidationError("Alan ve kategori aynı organizasyonda olmalıdır.")

	def __str__(self) -> str:
		return f"{self.category.name}::{self.label}"


class Ticket(models.Model):
	"""Customer request (talep) created in customer portal."""
	class Status(models.TextChoices):
		OPEN = "open", "Open"
		OFFERED = "offered", "Offered"
		ACCEPTED = "accepted", "Accepted"
		REJECTED = "rejected", "Rejected"
		CLOSED = "closed", "Closed"

	organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="tickets")
	customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='tickets')
	category = models.ForeignKey('Category', on_delete=models.PROTECT, related_name='tickets')
	title = models.CharField(max_length=200)
	description = models.TextField(blank=True)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
	created_at = models.DateTimeField(auto_now_add=True)
	desired_quantity = models.PositiveIntegerField(default=1)
	# Unique token for supplier-specific no-auth access
	supplier_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
	# Owner workflow: chosen supplier quote and pricing to customer
	selected_quote = models.ForeignKey('Quote', on_delete=models.SET_NULL, null=True, blank=True, related_name='selected_for_tickets')
	markup_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
	offered_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
	offered_note = models.TextField(blank=True)
	# Dynamic form answers per category (owner-defined)
	extra_data = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ["-created_at"]

	def clean(self):
		# Ensure all orgs match without dereferencing unset relations
		if self.organization_id and self.customer_id:
			# Compare via cached FK id to avoid fetching related when unset
			cust_org_id = None
			try:
				cust_org_id = self.customer.organization_id  # uses cache if available
			except Exception:
				# Fallback to query by id only if needed
				from .models import Customer as _Customer
				cust_org_id = _Customer.objects.only("organization_id").filter(id=self.customer_id).values_list("organization_id", flat=True).first()
			if cust_org_id and cust_org_id != self.organization_id:
				raise ValidationError("Talep organizasyonu müşteri organizasyonu ile eşleşmeli.")
		if self.organization_id and self.category_id:
			cat_org_id = None
			try:
				cat_org_id = self.category.organization_id
			except Exception:
				from .models import Category as _Category
				cat_org_id = _Category.objects.only("organization_id").filter(id=self.category_id).values_list("organization_id", flat=True).first()
			if cat_org_id and cat_org_id != self.organization_id:
				raise ValidationError("Talep organizasyonu kategori organizasyonu ile eşleşmeli.")

		# If a quote is selected, it must belong to this ticket and organization
		if self.selected_quote_id:
			# Ensure selected quote belongs to this ticket
			if self.selected_quote.ticket_id != self.id:
				raise ValidationError("Seçilen teklif bu talebe ait değil.")
			# Ensure org matches as well (defensive)
			if self.organization_id and self.selected_quote.ticket.organization_id != self.organization_id:
				raise ValidationError("Seçilen teklif organizasyonla uyuşmuyor.")

	@property
	def assigned_suppliers(self):
		"""Return suppliers assigned via matching rules; fallback to category.suppliers if none.
		The result is a QuerySet of Supplier within the same organization.
		"""
		if not self.category_id:
			return Supplier.objects.none()
		# Evaluate rules in order; collect suppliers from all matching rules
		try:
			rules = list(self.category.supplier_rules.filter(is_active=True, organization_id=self.organization_id).order_by("order", "id"))
		except Exception:
			rules = []
		matched_ids = set()
		for r in rules:
			try:
				if r.matches(self):
					matched_ids.update(r.suppliers.values_list("id", flat=True))
			except Exception:
				continue
		if matched_ids:
			return Supplier.objects.filter(id__in=list(matched_ids), organization_id=self.organization_id).order_by("name")
		# fallback
		return self.category.suppliers.all()


class TicketEmailReply(models.Model):
	"""Email replies from suppliers to ticket requests."""
	ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="email_replies")
	supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True, related_name='email_replies')
	from_email = models.EmailField()
	subject = models.CharField(max_length=255, blank=True)
	body = models.TextField()
	received_at = models.DateTimeField(auto_now_add=True)
	# Store raw email data if needed
	raw_data = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ["-received_at"]

	def __str__(self) -> str:
		return f"Reply from {self.from_email} for Ticket #{self.ticket_id}"


class TicketAttachment(models.Model):
	ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="attachments")
	file = models.FileField(upload_to="ticket_attachments/%Y/%m/%d/")
	uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
	uploaded_at = models.DateTimeField(auto_now_add=True)

	def __str__(self) -> str:
		return self.file.name


# Simple currency choices for quotes and orders
CURRENCY_CHOICES = (
	("TRY", "TRY"),
	("USD", "USD"),
	("EUR", "EUR"),
	("GBP", "GBP"),
)


class Quote(models.Model):
	ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="quotes")
	supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="quotes")
	currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="TRY", verbose_name="Para Birimi")
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	note = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]
		indexes = [
			models.Index(fields=["ticket", "supplier"]),
		]
		unique_together = (("ticket", "supplier"),)

	def clean(self):
		# supplier must be in the same organization as the ticket
		if self.ticket_id and self.supplier_id:
			ticket_org_id = self.ticket.organization_id
			if ticket_org_id and not self.supplier.organizations.filter(pk=ticket_org_id).exists():
				raise ValidationError(f"Tedarikçi '{self.supplier.name}' bu organizasyonda bulunmuyor.")

	def __str__(self) -> str:
		return f"{self.supplier.name} -> {self.ticket_id}: {self.amount} {self.currency}"


class QuoteItem(models.Model):
	"""Line items for a supplier quote."""
	quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="items")
	product = models.ForeignKey(SupplierProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name="quote_items")
	description = models.CharField(max_length=255)
	quantity = models.PositiveIntegerField(default=1)
	unit_price = models.DecimalField(max_digits=12, decimal_places=2)

	class Meta:
		ordering = ["id"]

	def clean(self):
		# Ensure product matches supplier/org and category fits ticket category
		if self.product_id:
			if self.product.supplier_id != self.quote.supplier_id:
				raise ValidationError("Ürün bu tedarikçiye ait değil.")
			# Category must match ticket category
			if self.product.category_id != self.quote.ticket.category_id:
				raise ValidationError("Ürün kategorisi taleple eşleşmiyor.")

	@property
	def line_total(self):
		try:
			return (self.unit_price or Decimal('0')) * (self.quantity or 0)
		except Exception:
			return Decimal('0')


class OwnerQuoteAdjustment(models.Model):
	"""Owner-defined per-item markup for a specific ticket and quote item."""
	ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="owner_adjustments")
	quote_item = models.ForeignKey(QuoteItem, on_delete=models.CASCADE, related_name="owner_adjustments")
	markup_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
	is_selected = models.BooleanField(default=True, verbose_name="Müşteriye Gönder")

	class Meta:
		unique_together = (("ticket", "quote_item"),)
		indexes = [models.Index(fields=["ticket", "quote_item"])]

	def __str__(self) -> str:
		return f"Adj ticket#{self.ticket_id} item#{self.quote_item_id}: {self.markup_amount}"


class QuoteComment(models.Model):
	"""Customer comment on an offered quote/ticket."""
	ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="quote_comments")
	quote = models.ForeignKey(Quote, on_delete=models.SET_NULL, null=True, blank=True, related_name="comments")
	author_customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="quote_comments")
	text = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]
		indexes = [models.Index(fields=["ticket", "created_at"])]

	def __str__(self) -> str:
		return f"Comment by {self.author_customer_id or 'anon'} on ticket {self.ticket_id}"
