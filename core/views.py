from django.shortcuts import render, redirect, get_object_or_404
from accounts.permissions import tenant_member_required, tenant_role_required
from django.conf import settings
from accounts.models import Membership
from .models import Customer, Supplier, Category, Ticket
from .models import Customer, Supplier, Category, Ticket, TicketAttachment, Quote, SupplierProduct, QuoteItem, OwnerQuoteAdjustment, CategoryFormField, CategorySupplierRule
from django.db import models
from django import forms
from django.forms import formset_factory
from decimal import Decimal, ROUND_HALF_UP
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from billing.models import Order, OrderItem
from django.http import HttpResponse
from django.template.loader import render_to_string


def home(request):
	return render(request, "core/home.html")


@tenant_member_required
def dashboard(request):
	return render(request, "core/dashboard.html", {"org": getattr(request, "tenant", None)})


def role_landing(request):
	# Unified landing: decide destination based on user's profile and memberships
	if not request.user.is_authenticated:
		return redirect("home")

	# 1) Staff/admins -> Django admin
	if request.user.is_staff:
		return redirect("/admin/")

	# 2) Customer portal users
	cust = getattr(request.user, "customer_profile", None)
	if cust is not None:
		_set_tenant_session(request, cust.organization)
		return redirect("customer_portal")

	# 3) Supplier portal users
	sup = getattr(request.user, "supplier_profile", None)
	if sup is not None:
		_set_tenant_session(request, sup.organization)
		return redirect("supplier_portal")

	# 4) Organization members -> map using role to internal app pages
	# Ensure we have a current org in session; if missing and the user has exactly
	# one membership, pick it automatically; otherwise ask user to choose.
	org = getattr(request, "tenant", None)
	if org is None:
		user_orgs = (
			Membership.objects.filter(user=request.user)
			.select_related("organization")
			.values_list("organization__slug", flat=True)
		)
		user_orgs = list(user_orgs)
		if len(user_orgs) == 1:
			request.session["current_org"] = user_orgs[0]
			org = getattr(request, "tenant", None)  # middleware will set on next request
		else:
			return redirect("org_list")

	mem = Membership.objects.filter(user=request.user, organization__slug=request.session.get("current_org")).select_related("role_fk").first()
	if not mem:
		return redirect("org_list")

	# default fallback
	fallback = settings.ROLE_LANDING_MAP.get("member", "/")
	# custom role key has priority
	if mem.role_fk and mem.role_fk.key in settings.ROLE_LANDING_MAP:
		return redirect(settings.ROLE_LANDING_MAP[mem.role_fk.key])
	# fallback to enum role
	return redirect(settings.ROLE_LANDING_MAP.get(mem.role, fallback))


# Lightweight ModelForm to create customers; organization is set from request.tenant

class CustomerForm(forms.ModelForm):
	# Optional login management by owner/admin
	login_username = forms.CharField(label="Kullanıcı Adı", required=False)
	login_password1 = forms.CharField(label="Şifre", required=False, widget=forms.PasswordInput)
	login_password2 = forms.CharField(label="Şifre (tekrar)", required=False, widget=forms.PasswordInput)
	class Meta:
		model = Customer
		fields = ["name", "email", "phone", "notes"]

	def __init__(self, *args, **kwargs):
		instance = kwargs.get("instance")
		super().__init__(*args, **kwargs)
		if instance and getattr(instance, "user", None):
			self.fields["login_username"].initial = instance.user.username

	def clean(self):
		cleaned = super().clean()
		p1 = cleaned.get("login_password1")
		p2 = cleaned.get("login_password2")
		if (p1 or p2) and p1 != p2:
			raise forms.ValidationError("Şifreler eşleşmiyor.")
		# If username provided, ensure it's unique (if creating new or changing)
		uname = cleaned.get("login_username")
		if uname:
			U = get_user_model()
			qs = U.objects.filter(username=uname)
			if self.instance and getattr(self.instance, "user", None):
				qs = qs.exclude(pk=self.instance.user_id)
			if qs.exists():
				raise forms.ValidationError("Bu kullanıcı adı kullanımda.")
		return cleaned


@tenant_member_required
def customers_list(request):
	org = getattr(request, "tenant", None)
	qs = Customer.objects.filter(organization=org)
	q = request.GET.get("q", "").strip()
	if q:
		qs = qs.filter(models.Q(name__icontains=q) | models.Q(email__icontains=q) | models.Q(phone__icontains=q))
	has_email = request.GET.get("has_email")
	if has_email:
		qs = qs.filter(email__isnull=False).exclude(email="")
	qs = qs.order_by("name")
	return render(request, "core/customers_list.html", {"customers": qs, "org": org, "q": q, "has_email": has_email})


@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def customers_create(request):
	org = getattr(request, "tenant", None)
	if request.method == "POST":
		form = CustomerForm(request.POST)
		if form.is_valid():
			cust = form.save(commit=False)
			cust.organization = org
			cust.save()
			# Create login if missing; prefer owner-provided credentials
			if not cust.user:
				U = get_user_model()
				uname = form.cleaned_data.get("login_username") or ""
				p1 = form.cleaned_data.get("login_password1") or ""
				if not uname:
					base = f"cust_{getattr(org, 'slug', 'org')}_{cust.id}"
					uname = base
					while U.objects.filter(username=uname).exists():
						uname = f"{base}_{get_random_string(4)}"
				password = p1 or get_random_string(10)
				user = U.objects.create_user(username=uname, password=password, email=cust.email or "")
				cust.user = user
				cust.save(update_fields=["user"])
				if p1:
					messages.success(request, f"Müşteri '{cust.name}' eklendi. Giriş: {uname}")
				else:
					messages.success(request, f"Müşteri '{cust.name}' eklendi. Kullanıcı: {uname} | Şifre: {password}")
			else:
				messages.success(request, f"Müşteri '{cust.name}' başarıyla eklendi.")
			return redirect("customers_list")
		else:
			messages.error(request, "Lütfen formu kontrol edin.")
	else:
		form = CustomerForm()
	return render(request, "core/customers_form.html", {"form": form, "org": org})


class SupplierForm(forms.ModelForm):
	login_username = forms.CharField(label="Kullanıcı Adı", required=False)
	login_password1 = forms.CharField(label="Şifre", required=False, widget=forms.PasswordInput)
	login_password2 = forms.CharField(label="Şifre (tekrar)", required=False, widget=forms.PasswordInput)
	class Meta:
		model = Supplier
		fields = ["name", "email", "phone", "notes"]

	def __init__(self, *args, **kwargs):
		self.is_existing = kwargs.pop("is_existing", False)
		instance = kwargs.get("instance")
		super().__init__(*args, **kwargs)
		if instance and getattr(instance, "user", None):
			self.fields["login_username"].initial = instance.user.username
		# Hide login fields if existing supplier
		if self.is_existing:
			self.fields["login_username"].widget = forms.HiddenInput()
			self.fields["login_password1"].widget = forms.HiddenInput()
			self.fields["login_password2"].widget = forms.HiddenInput()

	def _post_clean(self):
		"""Override to skip unique validation for email field when creating new supplier."""
		# Call parent but catch unique validation errors for email
		try:
			super()._post_clean()
		except forms.ValidationError:
			# If it's a new instance (not editing), skip email unique validation
			if not self.instance.pk and 'email' in self.errors:
				# Remove email errors - we'll handle duplicates in the view
				if '__all__' in self.errors:
					del self.errors['__all__']
				if 'email' in self.errors:
					del self.errors['email']
			else:
				raise

	def clean(self):
		cleaned = super().clean()
		# Skip password validation for existing suppliers
		if self.is_existing:
			return cleaned
		p1 = cleaned.get("login_password1")
		p2 = cleaned.get("login_password2")
		if (p1 or p2) and p1 != p2:
			raise forms.ValidationError("Şifreler eşleşmiyor.")
		uname = cleaned.get("login_username")
		if uname:
			U = get_user_model()
			qs = U.objects.filter(username=uname)
			if self.instance and getattr(self.instance, "user", None):
				qs = qs.exclude(pk=self.instance.user_id)
			if qs.exists():
				raise forms.ValidationError("Bu kullanıcı adı kullanımda.")
		return cleaned


class SupplierProductForm(forms.ModelForm):
	class Meta:
		model = SupplierProduct
		fields = ["category", "name", "description", "base_price", "is_active"]

	def __init__(self, *args, **kwargs):
		org = kwargs.pop("organization", None)
		supplier = kwargs.pop("supplier", None)
		super().__init__(*args, **kwargs)
		if org is not None:
			self.fields["category"].queryset = Category.objects.filter(organization=org).order_by("name")
		self._organization = org
		self._supplier = supplier

	def clean(self):
		if getattr(self, "_organization", None) is not None and not getattr(self.instance, "organization_id", None):
			self.instance.organization = self._organization
		if getattr(self, "_supplier", None) is not None and not getattr(self.instance, "supplier_id", None):
			self.instance.supplier = self._supplier
		return super().clean()


class OwnerSupplierProductForm(forms.ModelForm):
	supplier = forms.ModelChoiceField(queryset=Supplier.objects.none(), label="Tedarikçi")

	class Meta:
		model = SupplierProduct
		fields = ["supplier", "category", "name", "description", "base_price", "is_active"]

	def __init__(self, *args, **kwargs):
		org = kwargs.pop("organization", None)
		super().__init__(*args, **kwargs)
		if org is not None:
			self.fields["supplier"].queryset = Supplier.objects.filter(organizations=org).order_by("name")
			self.fields["category"].queryset = Category.objects.filter(organization=org).order_by("name")
		self._organization = org

	def clean(self):
		if getattr(self, "_organization", None) is not None and not getattr(self.instance, "organization_id", None):
			self.instance.organization = self._organization
		return super().clean()


# ---------- Category management (Owner only) ----------

class CategoryForm(forms.ModelForm):
	class Meta:
		model = Category
		fields = ["parent", "name", "suppliers"]
		widgets = {
			"parent": forms.Select(attrs={"class": "form-select"}),
			"name": forms.TextInput(attrs={"class": "form-control"}),
			"suppliers": forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
		}
		labels = {
			"parent": "Üst Kategori",
			"name": "Kategori Adı",
			"suppliers": "Tedarikçiler",
		}

	def __init__(self, *args, **kwargs):
		org = kwargs.pop("organization", None)
		super().__init__(*args, **kwargs)
		# Limit suppliers to current organization
		if org is not None:
			self.fields["suppliers"].queryset = Supplier.objects.filter(organizations=org).order_by("name")
			# Limit parent categories to current organization, excluding self and children
			parent_qs = Category.objects.filter(organization=org).order_by("name")
			if self.instance and self.instance.pk:
				parent_qs = parent_qs.exclude(pk=self.instance.pk)
				# Also exclude descendants to prevent circular references
				children_ids = list(self.instance.children.values_list('pk', flat=True))
				if children_ids:
					parent_qs = parent_qs.exclude(pk__in=children_ids)
			self.fields["parent"].queryset = parent_qs
			self.fields["parent"].required = False
			self.fields["parent"].empty_label = "--- Ana Kategori ---"


@tenant_role_required([Membership.Role.OWNER])
def categories_list(request):
	org = getattr(request, "tenant", None)
	# Get root categories (no parent) with all descendants
	root_categories = Category.objects.filter(
		organization=org, 
		parent__isnull=True
	).prefetch_related(
		"suppliers", 
		"children__suppliers",
		"children__children__suppliers",
		"children__children__children__suppliers"  # Support up to 3 levels deep
	).order_by("name")
	return render(request, "core/categories_list.html", {"root_categories": root_categories, "org": org})


@tenant_role_required([Membership.Role.OWNER])
def categories_create(request):
	org = getattr(request, "tenant", None)
	if request.method == "POST":
		form = CategoryForm(request.POST, organization=org)
		if form.is_valid():
			obj = form.save(commit=False)
			obj.organization = org
			obj.save()
			form.save_m2m()
			messages.success(request, f"Kategori '{obj.name}' oluşturuldu.")
			return redirect("categories_list")
		else:
			messages.error(request, "Lütfen formu kontrol edin.")
	else:
		form = CategoryForm(organization=org)
	return render(request, "core/categories_form.html", {"form": form, "org": org})


@tenant_role_required([Membership.Role.OWNER])
def categories_edit(request, pk: int):
	org = getattr(request, "tenant", None)
	obj = get_object_or_404(Category, pk=pk, organization=org)
	if request.method == "POST":
		form = CategoryForm(request.POST, instance=obj, organization=org)
		if form.is_valid():
			cat = form.save()
			messages.success(request, f"Kategori '{cat.name}' güncellendi.")
			return redirect("categories_list")
		else:
			messages.error(request, "Lütfen formu kontrol edin.")
	else:
		form = CategoryForm(instance=obj, organization=org)
	return render(request, "core/categories_form.html", {"form": form, "org": org})

@tenant_role_required([Membership.Role.OWNER])
def categories_delete(request, pk: int):
	org = getattr(request, "tenant", None)
	obj = get_object_or_404(Category, pk=pk, organization=org)
	if request.method == "POST":
		name = obj.name
		obj.delete()
		messages.success(request, f"Kategori '{name}' silindi.")
		return redirect("categories_list")
	return render(request, "core/categories_confirm_delete.html", {"obj": obj, "org": org})


# ---------- Tickets overview for owner ----------
@tenant_role_required([Membership.Role.OWNER])
def tickets_list(request):
	"""Owner view: show only requests that have no supplier quotes yet."""
	org = getattr(request, "tenant", None)
	qs = (
		Ticket.objects.filter(organization=org)
		.select_related("category", "customer")
	.annotate(qcount=models.Count("quotes"), quotes_count=models.Count("quotes"))
		.filter(qcount=0)
		.order_by("-created_at")
	)
	return render(request, "core/tickets_list.html", {"tickets": qs, "org": org})


@tenant_role_required([Membership.Role.OWNER])
def offers_list(request):
	"""Owner view: tickets moved here once any supplier has submitted a quote."""
	org = getattr(request, "tenant", None)
	qs = (
		Ticket.objects.filter(organization=org)
		.select_related("category", "customer")
		.annotate(qcount=models.Count("quotes"))
		.filter(qcount__gt=0)
		.order_by("-created_at")
	)
	return render(request, "core/offers_list.html", {"tickets": qs, "org": org})


@tenant_member_required
def suppliers_list(request):
	org = getattr(request, "tenant", None)
	qs = Supplier.objects.filter(organizations=org)
	q = request.GET.get("q", "").strip()
	if q:
		qs = qs.filter(models.Q(name__icontains=q) | models.Q(email__icontains=q) | models.Q(phone__icontains=q))
	has_email = request.GET.get("has_email")
	if has_email:
		qs = qs.filter(email__isnull=False).exclude(email="")
	qs = qs.order_by("name")
	return render(request, "core/suppliers_list.html", {"suppliers": qs, "org": org, "q": q, "has_email": has_email})


@tenant_role_required([Membership.Role.OWNER])
def owner_products_list(request):
	"""Owner view: list all supplier products and which customers have ordered them."""
	org = getattr(request, "tenant", None)
	q = (request.GET.get("q") or "").strip()
	# Base queryset of products in org
	base_qs = (
		SupplierProduct.objects
		.filter(organization=org)
		.select_related("supplier", "category")
		.order_by("supplier__name", "name")
	)
	if q:
		base_qs = base_qs.filter(models.Q(name__icontains=q) | models.Q(description__icontains=q) | models.Q(supplier__name__icontains=q))

	# Build buyers per product using OrderItem relation
	items = (
		OrderItem.objects
		.select_related("order__ticket__customer")
		.filter(order__organization=org, product__isnull=False)
		.values("product_id", "order__ticket__customer_id", "order__ticket__customer__name")
	)
	buyers_map = {}
	for row in items:
		pid = row["product_id"]
		cname = row["order__ticket__customer__name"]
		if not pid or not cname:
			continue
		buyers_map.setdefault(pid, set()).add(cname)

	# Build rows as (product, buyers_list)
	products = list(base_qs)
	rows = [(p, sorted(buyers_map.get(p.id, []))) for p in products]

	return render(
		request,
		"core/owner_products_list.html",
		{"rows": rows, "org": org, "q": q},
	)


@tenant_role_required([Membership.Role.OWNER])
def owner_products_new(request):
	org = getattr(request, "tenant", None)
	if request.method == "POST":
		form = OwnerSupplierProductForm(request.POST, organization=org)
		if form.is_valid():
			obj = form.save(commit=False)
			obj.organization = org
			obj.save()
			messages.success(request, "Ürün oluşturuldu.")
			return redirect("owner_products_list")
	else:
		form = OwnerSupplierProductForm(organization=org)
	return render(request, "core/owner_products_form.html", {"form": form, "org": org})


@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def suppliers_create(request):
	org = getattr(request, "tenant", None)
	existing_supplier = None
	confirm_add = request.POST.get("confirm_add_existing")
	
	if request.method == "POST":
		# Check if confirming to add existing supplier
		if confirm_add == "yes":
			supplier_id = request.POST.get("existing_supplier_id")
			if supplier_id:
				existing_supplier = Supplier.objects.filter(pk=supplier_id).first()
				if existing_supplier:
					if org in existing_supplier.organizations.all():
						messages.warning(request, f"Tedarikçi '{existing_supplier.name}' zaten bu organizasyonda mevcut.")
					else:
						existing_supplier.organizations.add(org)
						messages.success(request, f"Mevcut tedarikçi '{existing_supplier.name}' organizasyonunuza eklendi.")
					return redirect("suppliers_list")
		
		form = SupplierForm(request.POST)
		if form.is_valid():
			email = form.cleaned_data.get("email")
			# Check if supplier with this email already exists
			if email:
				existing_supplier = Supplier.objects.filter(email=email).first()
			
			if existing_supplier:
				# Show confirmation page
				form = SupplierForm(request.POST, is_existing=True)
				return render(request, "core/suppliers_form.html", {
					"form": form, 
					"org": org, 
					"existing_supplier": existing_supplier,
					"show_confirmation": True
				})
			
			# Create new supplier
			sup = form.save(commit=False)
			sup.save()
			sup.organizations.add(org)
			# Create login if missing; prefer owner-provided credentials
			if not sup.user:
				U = get_user_model()
				uname = form.cleaned_data.get("login_username") or ""
				p1 = form.cleaned_data.get("login_password1") or ""
				if not uname:
					base = f"supp_{getattr(org, 'slug', 'org')}_{sup.id}"
					uname = base
					while U.objects.filter(username=uname).exists():
						uname = f"{base}_{get_random_string(4)}"
				password = p1 or get_random_string(10)
				user = U.objects.create_user(username=uname, password=password, email=sup.email or "")
				sup.user = user
				sup.save(update_fields=["user"])
				if p1:
					messages.success(request, f"Tedarikçi '{sup.name}' eklendi. Giriş: {uname}")
				else:
					messages.success(request, f"Tedarikçi '{sup.name}' eklendi. Kullanıcı: {uname} | Şifre: {password}")
			else:
				messages.success(request, f"Tedarikçi '{sup.name}' başarıyla eklendi.")
			return redirect("suppliers_list")
		else:
			messages.error(request, "Lütfen formu kontrol edin.")
	else:
		form = SupplierForm()
	return render(request, "core/suppliers_form.html", {"form": form, "org": org})


@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def customers_edit(request, pk: int):
	org = getattr(request, "tenant", None)
	obj = get_object_or_404(Customer, pk=pk, organization=org)
	if request.method == "POST":
		form = CustomerForm(request.POST, instance=obj)
		if form.is_valid():
			cust = form.save()
			U = get_user_model()
			uname = form.cleaned_data.get("login_username") or ""
			p1 = form.cleaned_data.get("login_password1") or ""
			if uname or p1:
				user = cust.user
				if user is None:
					# create new user
					if not uname:
						base = f"cust_{getattr(org, 'slug', 'org')}_{cust.id}"
						uname = base
						while U.objects.filter(username=uname).exists():
							uname = f"{base}_{get_random_string(4)}"
					password = p1 or get_random_string(10)
					user = U.objects.create_user(username=uname, password=password, email=cust.email or "")
					cust.user = user
					cust.save(update_fields=["user"])
					messages.success(request, f"Müşteri girişi oluşturuldu: {uname}")
				else:
					changed = False
					if uname and user.username != uname:
						user.username = uname
						changed = True
					if p1:
						user.set_password(p1)
						changed = True
					if changed:
						user.save()
						messages.success(request, "Müşteri giriş bilgileri güncellendi.")
			else:
				messages.success(request, f"Müşteri '{cust.name}' güncellendi.")
			return redirect("customers_list")
		else:
			messages.error(request, "Lütfen formu kontrol edin.")
	else:
		form = CustomerForm(instance=obj)
	return render(request, "core/customers_form.html", {"form": form, "org": org})


@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def customers_delete(request, pk: int):
	org = getattr(request, "tenant", None)
	obj = get_object_or_404(Customer, pk=pk, organization=org)
	if request.method == "POST":
		name = obj.name
		obj.delete()
		messages.success(request, f"Müşteri '{name}' silindi.")
		return redirect("customers_list")
	return render(request, "core/customers_confirm_delete.html", {"obj": obj, "org": org})


@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def suppliers_edit(request, pk: int):
	org = getattr(request, "tenant", None)
	obj = get_object_or_404(Supplier, pk=pk, organizations=org)
	if request.method == "POST":
		form = SupplierForm(request.POST, instance=obj)
		if form.is_valid():
			sup = form.save()
			U = get_user_model()
			uname = form.cleaned_data.get("login_username") or ""
			p1 = form.cleaned_data.get("login_password1") or ""
			if uname or p1:
				user = sup.user
				if user is None:
					if not uname:
						base = f"supp_{getattr(org, 'slug', 'org')}_{sup.id}"
						uname = base
						while U.objects.filter(username=uname).exists():
							uname = f"{base}_{get_random_string(4)}"
					password = p1 or get_random_string(10)
					user = U.objects.create_user(username=uname, password=password, email=sup.email or "")
					sup.user = user
					sup.save(update_fields=["user"])
					messages.success(request, f"Tedarikçi girişi oluşturuldu: {uname}")
				else:
					changed = False
					if uname and user.username != uname:
						user.username = uname
						changed = True
					if p1:
						user.set_password(p1)
						changed = True
					if changed:
						user.save()
						messages.success(request, "Tedarikçi giriş bilgileri güncellendi.")
			else:
				messages.success(request, f"Tedarikçi '{sup.name}' güncellendi.")
			return redirect("suppliers_list")
		else:
			messages.error(request, "Lütfen formu kontrol edin.")
	else:
		form = SupplierForm(instance=obj)
	return render(request, "core/suppliers_form.html", {"form": form, "org": org})


@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def suppliers_delete(request, pk: int):
	org = getattr(request, "tenant", None)
	obj = get_object_or_404(Supplier, pk=pk, organizations=org)
	if request.method == "POST":
		name = obj.name
		# Remove organization from supplier (or delete if last org)
		obj.organizations.remove(org)
		if not obj.organizations.exists():
			obj.delete()
			messages.success(request, f"Tedarikçi '{name}' tamamen silindi.")
		else:
			messages.success(request, f"Tedarikçi '{name}' bu organizasyondan kaldırıldı.")
		return redirect("suppliers_list")
	return render(request, "core/suppliers_confirm_delete.html", {"obj": obj, "org": org})


@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def check_supplier_email(request):
	"""AJAX endpoint to check if supplier with email exists."""
	from django.http import JsonResponse
	email = request.GET.get("email", "").strip()
	if not email:
		return JsonResponse({"exists": False})
	
	supplier = Supplier.objects.filter(email=email).first()
	if supplier:
		return JsonResponse({
			"exists": True,
			"name": supplier.name,
			"id": supplier.id
		})
	return JsonResponse({"exists": False})


from django.contrib.auth.decorators import login_required


def _set_tenant_session(request, org):
	request.session["current_org"] = org.slug


@login_required
def portal_home(request):
	"""Unified portal home after login.
	- If user has a customer profile, go to customer portal (and set tenant)
	- Else if supplier profile, go to supplier portal (and set tenant)
	- Else fall back to role-based landing
	"""
	cust = getattr(request.user, "customer_profile", None)
	if cust is not None:
		_set_tenant_session(request, cust.organization)
		return redirect("customer_portal")
	sup = getattr(request.user, "supplier_profile", None)
	if sup is not None:
		_set_tenant_session(request, sup.organization)
		return redirect("supplier_portal")
	return redirect("role_landing")


@login_required
def customer_portal(request):
	cust = getattr(request.user, "customer_profile", None)
	if not cust:
		return redirect("home")
	_set_tenant_session(request, cust.organization)
	open_cnt = cust.tickets.filter(status=Ticket.Status.OPEN).count() if hasattr(cust, 'tickets') else 0
	return render(request, "core/portal_customer.html", {"customer": cust, "org": cust.organization, "open_count": open_cnt})


@login_required
def supplier_portal(request):
	sup = getattr(request.user, "supplier_profile", None)
	if not sup:
		return redirect("home")
	_set_tenant_session(request, sup.organization)
	# Count tickets assigned to this supplier via rules (fallback to category.suppliers)
	open_tickets = Ticket.objects.filter(organization=sup.organization, status=Ticket.Status.OPEN).select_related("category")
	assigned_cnt = 0
	for t in open_tickets:
		try:
			if t.assigned_suppliers.filter(id=sup.id).exists():
				assigned_cnt += 1
		except Exception:
			continue
	return render(request, "core/portal_supplier.html", {"supplier": sup, "org": sup.organization, "assigned_open_count": assigned_cnt})


@login_required
def supplier_requests_list(request):
	sup = getattr(request.user, "supplier_profile", None)
	if not sup:
		return redirect("home")
	_set_tenant_session(request, sup.organization)
	# Rule-based assignment: filter in Python since rules can't be expressed in ORM easily
	all_tickets = Ticket.objects.filter(organization=sup.organization).select_related("category", "customer")
	tickets = []
	for t in all_tickets:
		try:
			if t.assigned_suppliers.filter(id=sup.id).exists():
				tickets.append(t)
		except Exception:
			continue
	return render(request, "core/portal_supplier_requests_list.html", {"tickets": tickets, "supplier": sup, "org": sup.organization})


@login_required
def supplier_orders_list(request):
	sup = getattr(request.user, "supplier_profile", None)
	if not sup:
		return redirect("home")
	_set_tenant_session(request, sup.organization)
	qs = (
		Order.objects.filter(organization=sup.organization, supplier=sup)
		.filter(status__in=[Order.Status.PROCESSING, Order.Status.COMPLETED])
		.select_related("ticket")
		.order_by("-created_at")
	)
	# Compute remaining days until ETA for display
	orders = list(qs)
	try:
		from datetime import date
		today = date.today()
		for o in orders:
			if getattr(o, "supplier_eta", None):
				o.remaining_days = (o.supplier_eta - today).days
			else:
				o.remaining_days = None
	except Exception:
		for o in orders:
			o.remaining_days = None
	return render(request, "core/portal_supplier_orders_list.html", {"orders": orders, "supplier": sup, "org": sup.organization})


@login_required
def supplier_order_detail(request, pk: int):
	sup = getattr(request.user, "supplier_profile", None)
	if not sup:
		return redirect("home")
	_set_tenant_session(request, sup.organization)
	order = get_object_or_404(
		Order.objects.select_related("ticket").prefetch_related("items"),
		pk=pk,
		organization=sup.organization,
		supplier=sup,
	)
	if request.method == "POST":
		eta_str = (request.POST.get("supplier_eta") or "").strip()
		note = (request.POST.get("supplier_note") or "").strip()
		eta_val = None
		if eta_str:
			try:
				from datetime import datetime
				eta_val = datetime.strptime(eta_str, "%Y-%m-%d").date()
			except Exception:
				eta_val = None
		order.supplier_eta = eta_val
		order.supplier_note = note
		order.supplier_acknowledged = True
		order.save(update_fields=["supplier_eta", "supplier_note", "supplier_acknowledged"])
		messages.success(request, "Sipariş bilgileri güncellendi.")
		return redirect("supplier_order_detail", pk=order.pk)

	return render(
		request,
		"core/portal_supplier_order_detail.html",
		{"order": order, "supplier": sup, "org": sup.organization},
	)


@login_required
def supplier_quotes_list(request):
	sup = getattr(request.user, "supplier_profile", None)
	if not sup:
		return redirect("home")
	_set_tenant_session(request, sup.organization)
	qs = (
		Quote.objects
		.filter(supplier=sup)
		.select_related("ticket", "ticket__customer")
		.order_by("-created_at")
	)
	q = (request.GET.get("q") or "").strip()
	if q:
		qs = qs.filter(ticket__title__icontains=q)
	return render(
		request,
		"core/portal_supplier_quotes_list.html",
		{"quotes": qs, "supplier": sup, "org": sup.organization, "q": q},
	)


# ---------- Customer portal: Tickets (requests) ----------
from django.forms import ModelForm


class TicketForm(ModelForm):
	class Meta:
		model = Ticket
		fields = ["category", "desired_quantity", "title", "description"]

	def __init__(self, *args, **kwargs):
		org = kwargs.pop("organization", None)
		self._organization = org
		self._customer = kwargs.pop("customer", None)
		super().__init__(*args, **kwargs)
		if org is not None:
			self.fields["category"].queryset = Category.objects.filter(organization=org).prefetch_related("suppliers").order_by("name")

	def clean(self):
		# Ensure instance has organization/customer set before model full_clean
		if getattr(self, "_organization", None) is not None and not getattr(self.instance, "organization_id", None):
			self.instance.organization = self._organization
		if getattr(self, "_customer", None) is not None and not getattr(self.instance, "customer_id", None):
			self.instance.customer = self._customer
		return super().clean()


class SubRequestForm(forms.Form):
	"""One line of a multi-request: choose category and write a description."""
	category = forms.ModelChoiceField(queryset=Category.objects.none(), required=True, label="Kategori")
	quantity = forms.IntegerField(min_value=1, initial=1, label="Adet")
	description = forms.CharField(required=True, widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Açıklama"}), label="Açıklama")

	def __init__(self, *args, **kwargs):
		org = kwargs.pop("organization", None)
		super().__init__(*args, **kwargs)
		if org is not None:
			self.fields["category"].queryset = Category.objects.filter(organization=org).order_by("name")


class TicketHeaderForm(forms.Form):
	title = forms.CharField(max_length=200, required=True, label="Başlık")

class OwnerTicketHeaderForm(forms.Form):
	title = forms.CharField(max_length=200, required=True, label="Başlık")
	customer = forms.ModelChoiceField(queryset=Customer.objects.none(), required=True, label="Müşteri")

	def __init__(self, *args, **kwargs):
		org = kwargs.pop("organization", None)
		super().__init__(*args, **kwargs)
		if org is not None:
			self.fields["customer"].queryset = Customer.objects.filter(organization=org).order_by("name")

class TicketAttachmentForm(forms.ModelForm):
	class Meta:
		model = TicketAttachment
		fields = ["file"]

class QuoteNoteForm(forms.ModelForm):
	class Meta:
		model = Quote
		fields = ["currency", "note"]


class QuoteItemForm(forms.Form):
	product = forms.ModelChoiceField(queryset=SupplierProduct.objects.none(), required=False, label="Ürün")
	description = forms.CharField(max_length=255, required=True, label="Açıklama")
	quantity = forms.IntegerField(min_value=1, initial=1, label="Adet")
	unit_price = forms.DecimalField(min_value=0, decimal_places=2, max_digits=12, label="Birim Fiyat")

	def __init__(self, *args, **kwargs):
		supplier = kwargs.pop("supplier", None)
		category = kwargs.pop("category", None)
		super().__init__(*args, **kwargs)
		qs = SupplierProduct.objects.none()
		if supplier is not None and category is not None:
			qs = SupplierProduct.objects.filter(supplier=supplier, category=category, is_active=True).order_by("name")
		self.fields["product"].queryset = qs


class OwnerOfferForm(forms.Form):
	selected_quote = forms.ModelChoiceField(queryset=Quote.objects.none(), required=True, label="Seçilen Teklif")
	offered_note = forms.CharField(required=False, widget=forms.Textarea, label="Müşteriye Not")

	def __init__(self, *args, **kwargs):
		ticket = kwargs.pop("ticket", None)
		super().__init__(*args, **kwargs)
		if ticket is not None:
			self.fields["selected_quote"].queryset = ticket.quotes.select_related("supplier").all()


@login_required
def customer_requests_list(request):
	cust = getattr(request.user, "customer_profile", None)
	if not cust:
		return redirect("home")
	_set_tenant_session(request, cust.organization)
	# Show only tickets without any supplier quotes here
	qs = Ticket.objects.filter(organization=cust.organization, customer=cust).annotate(qcount=models.Count("quotes")).filter(qcount=0).select_related("category", "customer")
	return render(request, "core/portal_customer_requests_list.html", {"tickets": qs, "customer": cust, "org": cust.organization})


class QuoteCommentForm(forms.ModelForm):
	class Meta:
		from .models import QuoteComment
		model = QuoteComment
		fields = ["text"]
		widgets = {"text": forms.Textarea(attrs={"rows": 3, "placeholder": "Teklife yorumunuz..."})}


@login_required
def customer_offers_list(request):
	cust = getattr(request.user, "customer_profile", None)
	if not cust:
		return redirect("home")
	_set_tenant_session(request, cust.organization)
	# Tickets that received at least one quote
	qs = Ticket.objects.filter(organization=cust.organization, customer=cust).annotate(qcount=models.Count("quotes")).filter(qcount__gt=0).select_related("category")
	return render(request, "core/portal_customer_offers_list.html", {"tickets": qs, "customer": cust, "org": cust.organization})


@login_required
def customer_offers_detail(request, pk: int):
	cust = getattr(request.user, "customer_profile", None)
	if not cust:
		return redirect("home")
	_set_tenant_session(request, cust.organization)
	ticket = get_object_or_404(Ticket.objects.select_related("category").prefetch_related("quotes__supplier", "attachments"), pk=pk, organization=cust.organization, customer=cust)
	quotes = list(ticket.quotes.select_related("supplier").all())
	if request.method == "POST":
		action = request.POST.get("action")
		if action in {"accept", "reject"} and ticket.status == Ticket.Status.OFFERED:
			if action == "accept":
				# Reuse existing accept flow
				request.POST = request.POST.copy()
				request.POST["action"] = "accept"
				return customer_requests_detail(request, pk)
			else:
				request.POST = request.POST.copy()
				request.POST["action"] = "reject"
				return customer_requests_detail(request, pk)
		# Comment submission
		form = QuoteCommentForm(request.POST)
		if form.is_valid():
			comment = form.save(commit=False)
			comment.ticket = ticket
			comment.author_customer = cust
			qid = request.POST.get("quote_id")
			if qid:
				try:
					comment.quote = ticket.quotes.get(id=int(qid))
				except Exception:
					comment.quote = None
			comment.save()
			messages.success(request, "Yorumunuz kaydedildi.")
			return redirect("customer_offers_detail", pk=pk)
	else:
		form = QuoteCommentForm()
	comments = ticket.quote_comments.select_related("author_customer").all()
	# Build customer-visible breakdown including owner markups for the selected quote
	selected_items = None
	selected_global_markup = None
	items_subtotal = None
	grand_total = None
	extra_fields = []
	if ticket.selected_quote_id and ticket.selected_quote:
		items = list(ticket.selected_quote.items.all())
		if items:
			adjs = {a.quote_item_id: a.markup_amount for a in ticket.owner_adjustments.all()}
			selected_items = []
			for it in items:
				supplier_total = it.line_total
				markup = adjs.get(it.id) or Decimal("0.00")
				selected_items.append({
					"name": (getattr(getattr(it, "product", None), "name", None) or it.description),
					"description": it.description,
					"quantity": it.quantity,
					# unit price shown to customer should include markup prorated per unit
					"sell_unit_price": (supplier_total + markup) / (it.quantity or 1),
					"sell_total": supplier_total + markup,
				})
			selected_global_markup = ticket.markup_amount or Decimal("0.00")
			# totals for display
			items_subtotal = sum((row["sell_total"] for row in selected_items), Decimal("0.00"))
			grand_total = ticket.offered_price or (items_subtotal + (selected_global_markup or Decimal("0.00")))
		else:
			selected_global_markup = ticket.markup_amount or Decimal("0.00")
			grand_total = ticket.offered_price or selected_global_markup

	# Map dynamic extra fields to labels
	if ticket.extra_data:
		try:
			specs = (
				CategoryFormField.objects
				.filter(organization=ticket.organization, category=ticket.category)
				.order_by("order", "id")
			)
			for f in specs:
				if f.name in ticket.extra_data:
					val = ticket.extra_data.get(f.name)
					if isinstance(val, list):
						val = ", ".join([str(v) for v in val])
					extra_fields.append({"label": f.label, "value": val})
		except Exception:
			for k, v in (ticket.extra_data or {}).items():
				extra_fields.append({"label": k, "value": v})
	return render(
		request,
		"core/portal_customer_offers_detail.html",
		{
			"ticket": ticket,
			"quotes": quotes,
			"form": form,
			"comments": comments,
			"org": cust.organization,
			"selected_items": selected_items,
			"selected_global_markup": selected_global_markup,
			"items_subtotal": items_subtotal,
			"grand_total": grand_total,
			"extra_fields": extra_fields,
		},
	)


@login_required
def customer_offers_pdf(request, pk: int):
	cust = getattr(request.user, "customer_profile", None)
	if not cust:
		return redirect("home")
	_set_tenant_session(request, cust.organization)
	ticket = get_object_or_404(
		Ticket.objects.select_related("category").prefetch_related("quotes__supplier"),
		pk=pk,
		organization=cust.organization,
		customer=cust,
	)

	# Build items for PDF similar to detail view
	selected_items = []
	items_subtotal = Decimal("0.00")
	selected_global_markup = ticket.markup_amount or Decimal("0.00")
	currency = ""
	extra_fields = []
	if ticket.selected_quote_id and ticket.selected_quote:
		currency = ticket.selected_quote.currency or ""
		items = list(ticket.selected_quote.items.all())
		if items:
			adjs = {a.quote_item_id: a.markup_amount for a in ticket.owner_adjustments.all()}
			for it in items:
				supplier_total = it.line_total
				markup = adjs.get(it.id) or Decimal("0.00")
				sell_total = supplier_total + markup
				sell_unit_price = sell_total / (it.quantity or 1)
				selected_items.append({
					"description": it.description,
					"quantity": it.quantity,
					"sell_unit_price": sell_unit_price,
					"sell_total": sell_total,
				})
				items_subtotal += sell_total

	# Map dynamic extra fields to labels
	if ticket.extra_data:
		try:
			specs = (
				CategoryFormField.objects
				.filter(organization=ticket.organization, category=ticket.category)
				.order_by("order", "id")
			)
			for f in specs:
				if f.name in ticket.extra_data:
					val = ticket.extra_data.get(f.name)
					if isinstance(val, list):
						val = ", ".join([str(v) for v in val])
					extra_fields.append({"label": f.label, "value": val})
		except Exception:
			for k, v in (ticket.extra_data or {}).items():
				extra_fields.append({"label": k, "value": v})

	grand_total = ticket.offered_price or (items_subtotal + (selected_global_markup or Decimal("0.00")))

	html = render_to_string(
		"core/portal_customer_offer_pdf.html",
		{
			"ticket": ticket,
			"items": selected_items,
			"items_subtotal": items_subtotal,
			"grand_total": grand_total,
			"currency": currency,
			"org": cust.organization,
			"extra_fields": extra_fields,
		},
	)

	# Lazy import of xhtml2pdf
	from xhtml2pdf import pisa
	response = HttpResponse(content_type="application/pdf")
	response["Content-Disposition"] = f'attachment; filename="teklif_{ticket.id}.pdf"'
	pisa.CreatePDF(src=html, dest=response)
	return response


@login_required
def customer_requests_new(request):
	cust = getattr(request.user, "customer_profile", None)
	if not cust:
		return redirect("home")
	_set_tenant_session(request, cust.organization)
	# Build a dynamic formset for multiple sub-requests
	SubFormSet = formset_factory(SubRequestForm, extra=1, can_delete=True)
	if request.method == "POST":
		header_form = TicketHeaderForm(request.POST)
		formset = SubFormSet(request.POST, form_kwargs={"organization": cust.organization})
		if header_form.is_valid() and formset.is_valid():
			title = header_form.cleaned_data.get("title")
			# Collect validation errors and values for dynamic fields per row prefix
			dyn_errors_by_prefix = {}
			dyn_values_by_prefix = {}
			rows_buffer = []  # (cat, desc, qty, extra_dict, prefix)
			for f in formset:
				if f.cleaned_data and not f.cleaned_data.get("DELETE"):
					cat = f.cleaned_data.get("category")
					qty = f.cleaned_data.get("quantity") or 1
					desc = f.cleaned_data.get("description")
					row_prefix = (getattr(f, "prefix", "") or "").strip()
					extra = {}
					row_errs = {}
					row_vals = {}
					if cat:
						dyn_fields = CategoryFormField.objects.filter(organization=cust.organization, category=cat).order_by("order", "id")
						for df in dyn_fields:
							key = f"{row_prefix}-extra-{df.name}"
							val = (request.POST.get(key, "") or "").strip()
							row_vals[df.name] = val
							if df.field_type == CategoryFormField.FieldType.SELECT:
								opts = [o.strip() for o in (df.options or "").splitlines() if o.strip()]
								if val and val not in opts:
									row_errs[df.name] = "Geçersiz seçim."
									val = ""
							if df.required and not val:
								row_errs[df.name] = row_errs.get(df.name) or "Bu alan zorunlu."
							# Save non-empty or optional values
							if val or not df.required:
								extra[df.name] = val
					if row_vals:
						dyn_values_by_prefix[row_prefix] = row_vals
					if row_errs:
						dyn_errors_by_prefix[row_prefix] = row_errs
					rows_buffer.append((cat, desc, qty, extra, row_prefix))

			# If any dynamic field errors, re-render with errors and prefill
			if dyn_errors_by_prefix:
				messages.error(request, "Lütfen zorunlu alanları doldurun.")
			else:
				created = 0
				for cat, desc, qty, extra, _ in rows_buffer:
					if cat and desc:
						Ticket.objects.create(
							organization=cust.organization,
							customer=cust,
							category=cat,
							title=title,
							description=desc,
							desired_quantity=qty,
							extra_data=extra,
						)
						created += 1
				if created == 0:
					messages.error(request, "En az bir satır ekleyin.")
				else:
					messages.success(request, f"{created} talep oluşturuldu.")
					return redirect("customer_requests_list")
	else:
		header_form = TicketHeaderForm()
		formset = SubFormSet(form_kwargs={"organization": cust.organization})
	# Preload category dynamic field specs for client-side rendering
	cat_fields = {}
	for c in Category.objects.filter(organization=cust.organization).order_by("name"):
		fields = []
		for df in c.form_fields.order_by("order", "id").all():
			fields.append({
				"name": df.name,
				"label": df.label,
				"type": df.field_type,
				"required": df.required,
				"help": df.help_text or "",
				"options": [o.strip() for o in (df.options or "").splitlines() if o.strip()],
			})
		cat_fields[c.id] = fields
	return render(
		request,
		"core/portal_customer_requests_form.html",
		{
			"header_form": header_form,
			"formset": formset,
			"customer": cust,
			"org": cust.organization,
			"cat_fields": cat_fields,
			"dynamic_prefill": locals().get("dyn_values_by_prefix", {}),
			"dynamic_errors": locals().get("dyn_errors_by_prefix", {}),
		},
	)


@tenant_role_required([Membership.Role.OWNER])
def tickets_new(request):
	"""Owner creates a new request on behalf of a selected customer."""
	org = getattr(request, "tenant", None)
	SubFormSet = formset_factory(SubRequestForm, extra=1, can_delete=True)
	if request.method == "POST":
		header_form = OwnerTicketHeaderForm(request.POST, organization=org)
		formset = SubFormSet(request.POST, form_kwargs={"organization": org})
		if header_form.is_valid() and formset.is_valid():
			title = header_form.cleaned_data.get("title")
			customer = header_form.cleaned_data.get("customer")
			# Collect validation errors and values for dynamic fields per row prefix
			dyn_errors_by_prefix = {}
			dyn_values_by_prefix = {}
			rows_buffer = []  # (cat, desc, qty, extra, prefix)
			for f in formset:
				if f.cleaned_data and not f.cleaned_data.get("DELETE"):
					cat = f.cleaned_data.get("category")
					qty = f.cleaned_data.get("quantity") or 1
					desc = f.cleaned_data.get("description")
					row_prefix = (getattr(f, "prefix", "") or "").strip()
					extra = {}
					row_errs = {}
					row_vals = {}
					if cat:
						dyn_fields = CategoryFormField.objects.filter(organization=org, category=cat).order_by("order", "id")
						for df in dyn_fields:
							key = f"{row_prefix}-extra-{df.name}"
							val = (request.POST.get(key, "") or "").strip()
							row_vals[df.name] = val
							if df.field_type == CategoryFormField.FieldType.SELECT:
								opts = [o.strip() for o in (df.options or "").splitlines() if o.strip()]
								if val and val not in opts:
									row_errs[df.name] = "Geçersiz seçim."
									val = ""
							if df.required and not val:
								row_errs[df.name] = row_errs.get(df.name) or "Bu alan zorunlu."
							if val or not df.required:
								extra[df.name] = val
					if row_vals:
						dyn_values_by_prefix[row_prefix] = row_vals
					if row_errs:
						dyn_errors_by_prefix[row_prefix] = row_errs
					rows_buffer.append((cat, desc, qty, extra, row_prefix))

			if dyn_errors_by_prefix:
				messages.error(request, "Lütfen zorunlu alanları doldurun.")
			else:
				created = 0
				for cat, desc, qty, extra, _ in rows_buffer:
					if cat and desc:
						Ticket.objects.create(
							organization=org,
							customer=customer,
							category=cat,
							title=title,
							description=desc,
							desired_quantity=qty,
							extra_data=extra,
						)
						created += 1
				if created == 0:
					messages.error(request, "En az bir satır ekleyin.")
				else:
					messages.success(request, f"{created} talep oluşturuldu.")
					return redirect("tickets_list")
	else:
		header_form = OwnerTicketHeaderForm(organization=org)
		formset = SubFormSet(form_kwargs={"organization": org})

	# Preload category dynamic field specs for client-side rendering
	cat_fields = {}
	for c in Category.objects.filter(organization=org).order_by("name"):
		fields = []
		for df in c.form_fields.order_by("order", "id").all():
			fields.append({
				"name": df.name,
				"label": df.label,
				"type": df.field_type,
				"required": df.required,
				"help": df.help_text or "",
				"options": [o.strip() for o in (df.options or "").splitlines() if o.strip()],
			})
		cat_fields[c.id] = fields
	return render(
		request,
		"core/owner_ticket_form.html",
		{
			"header_form": header_form,
			"formset": formset,
			"org": org,
			"cat_fields": cat_fields,
			"dynamic_prefill": locals().get("dyn_values_by_prefix", {}),
			"dynamic_errors": locals().get("dyn_errors_by_prefix", {}),
		},
	)


# ---------- Owner: Category form fields CRUD ----------
@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def category_form_fields_list(request, category_id: int):
	org = getattr(request, "tenant", None)
	category = get_object_or_404(Category, pk=category_id, organization=org)
	fields = category.form_fields.order_by("order", "id").all()
	return render(request, "core/category_form_fields_list.html", {"category": category, "fields": fields, "org": org})


class CategoryFormFieldForm(forms.ModelForm):
	class Meta:
		model = CategoryFormField
		fields = ["label", "name", "field_type", "options", "required", "order", "help_text"]

	def __init__(self, *args, **kwargs):
		self._organization = kwargs.pop("organization", None)
		self._category = kwargs.pop("category", None)
		super().__init__(*args, **kwargs)

	def clean(self):
		if getattr(self, "_organization", None) and not getattr(self.instance, "organization_id", None):
			self.instance.organization = self._organization
		if getattr(self, "_category", None) and not getattr(self.instance, "category_id", None):
			self.instance.category = self._category
		return super().clean()


@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def category_form_fields_new(request, category_id: int):
	org = getattr(request, "tenant", None)
	category = get_object_or_404(Category, pk=category_id, organization=org)
	if request.method == "POST":
		form = CategoryFormFieldForm(request.POST, organization=org, category=category)
		if form.is_valid():
			form.save()
			return redirect("category_form_fields_list", category_id=category.id)
	else:
		form = CategoryFormFieldForm(organization=org, category=category)
	return render(request, "core/category_form_fields_form.html", {"form": form, "category": category, "org": org})


@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def category_form_fields_edit(request, category_id: int, pk: int):
	org = getattr(request, "tenant", None)
	category = get_object_or_404(Category, pk=category_id, organization=org)
	obj = get_object_or_404(CategoryFormField, pk=pk, category=category)
	if request.method == "POST":
		form = CategoryFormFieldForm(request.POST, instance=obj, organization=org, category=category)
		if form.is_valid():
			form.save()
			return redirect("category_form_fields_list", category_id=category.id)
	else:
		form = CategoryFormFieldForm(instance=obj, organization=org, category=category)
	return render(request, "core/category_form_fields_form.html", {"form": form, "category": category, "org": org})


@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def category_form_fields_delete(request, category_id: int, pk: int):
	org = getattr(request, "tenant", None)
	category = get_object_or_404(Category, pk=category_id, organization=org)
	obj = get_object_or_404(CategoryFormField, pk=pk, category=category)
	if request.method == "POST":
		obj.delete()
		return redirect("category_form_fields_list", category_id=category.id)
	return render(request, "core/category_form_fields_confirm_delete.html", {"obj": obj, "category": category, "org": org})


# ---------- Owner: Category routing rules CRUD ----------
@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def category_rules_list(request, category_id: int):
	org = getattr(request, "tenant", None)
	category = get_object_or_404(Category, pk=category_id, organization=org)
	rules = category.supplier_rules.order_by("order", "id").all()
	# Provide dynamic field names to help owners author rules
	field_specs = list(category.form_fields.order_by("order", "id").values("name", "label"))
	return render(request, "core/category_rules_list.html", {"category": category, "rules": rules, "org": org, "field_specs": field_specs})


class CategorySupplierRuleForm(forms.ModelForm):
	class Meta:
		model = CategorySupplierRule
		fields = [
			"label",
			"is_active",
			"order",
			"min_quantity",
			"max_quantity",
			"field_name",
			"field_operator",
			"field_value",
			"suppliers",
		]

	def __init__(self, *args, **kwargs):
		from django.http import QueryDict
		self._organization = kwargs.pop("organization", None)
		self._category = kwargs.pop("category", None)
		super().__init__(*args, **kwargs)
		# Scope suppliers to organization
		if self._organization is not None:
			self.fields["suppliers"].queryset = Supplier.objects.filter(organizations=self._organization).order_by("name")
		# Build choices for field_name as single select
		all_fields = []
		if self._category is not None:
			all_fields = list(self._category.form_fields.order_by("order", "id").all())
		name_choices = [("", "- Alan seçin -")] + [(f.name, f"{f.label} ({f.name})") for f in all_fields]
		# Replace field_name with ChoiceField
		self.fields["field_name"] = forms.ChoiceField(
			choices=name_choices, required=False, label=self.fields["field_name"].label,
		)
		# Auto-submit on change to refresh value choices
		self.fields["field_name"].widget.attrs["onchange"] = "var f=document.getElementById('autosubmit-flag'); if(f){f.value='1';} this.form.submit();"
		# Determine selected field name from POST or instance
		data_present = isinstance(self.data, (dict, QueryDict)) and bool(self.data)
		selected_name = (self.data.get("field_name") if data_present else None) or (
			self.instance.field_name if getattr(self, "instance", None) and getattr(self.instance, "field_name", None) else None
		)
		if selected_name and selected_name not in {c[0] for c in name_choices}:
			selected_name = None
		self.fields["field_name"].initial = selected_name or ""

		# Configure field_value based on selected field and operator
		selected_field = next((f for f in all_fields if f.name == selected_name), None)
		op = (self.data.get("field_operator") if data_present else None) or (
			(self.instance.field_operator if getattr(self, "instance", None) else None)
		)
		op = (op or "").strip()
		# Auto-submit on operator change (impacts multi/single value field)
		self.fields["field_operator"].widget.attrs["onchange"] = "var f=document.getElementById('autosubmit-flag'); if(f){f.value='1';} this.form.submit();"

		from .models import CategoryFormField as _CFF
		if selected_field and selected_field.field_type == _CFF.FieldType.SELECT:
			opts = [o.strip() for o in (selected_field.options or "").splitlines() if o.strip()]
			choices = [("", "- Değer seçin -")] + [(o, o) for o in opts]
			# If operator is 'in', allow multi-select; else single select
			if op == "in":
				self.fields["field_value"] = forms.MultipleChoiceField(choices=choices[1:], required=False, label=self.fields["field_value"].label)
				# Initial: split CSV to list or posted list
				init_vals = []
				if getattr(self, "instance", None) and getattr(self.instance, "field_value", None):
					init_vals = [v.strip() for v in str(self.instance.field_value).split(',') if v.strip()]
				if data_present and hasattr(self.data, "getlist"):
					posted_vals = self.data.getlist("field_value")
					if posted_vals:
						init_vals = posted_vals
				self.fields["field_value"].initial = init_vals
			else:
				self.fields["field_value"] = forms.ChoiceField(choices=choices, required=False, label=self.fields["field_value"].label)
				init_val = ""
				if getattr(self, "instance", None) and getattr(self.instance, "field_value", None):
					# pick first if CSV
					init_val = str(self.instance.field_value).split(',')[0].strip()
				if data_present:
					posted_val = self.data.get("field_value") or ""
					if posted_val:
						init_val = posted_val
				self.fields["field_value"].initial = init_val
		else:
			# For non-select fields, let value be free text
			self.fields["field_value"] = forms.CharField(required=False, label=self.fields["field_value"].label)
			init_val = ""
			if getattr(self, "instance", None) and getattr(self.instance, "field_value", None):
				init_val = str(self.instance.field_value)
			if data_present:
				posted_val = self.data.get("field_value")
				if posted_val is not None:
					init_val = posted_val
			self.fields["field_value"].initial = init_val

	def clean(self):
		cleaned = super().clean()
		# Ensure org/category are set on the instance
		if self._organization and not getattr(self.instance, "organization_id", None):
			self.instance.organization = self._organization
		if self._category and not getattr(self.instance, "category_id", None):
			self.instance.category = self._category
		# Validate quantity range coherence
		mn = cleaned.get("min_quantity")
		mx = cleaned.get("max_quantity")
		if mn is not None and mx is not None and mn > mx:
			raise forms.ValidationError("En az adet, en çok adetten büyük olamaz.")
		# Normalize to CSV for storage (support both single and multi-select cases)
		fn_val = cleaned.get("field_name")
		fv_val = cleaned.get("field_value")
		# If any of field_operator/value provided, require field_name
		op = (cleaned.get("field_operator") or "").strip()
		if (op or fv_val) and not fn_val:
			raise forms.ValidationError("Alan filtresi için alan adı gereklidir.")
		cleaned["field_name"] = ",".join([str(v) for v in fn_val]) if isinstance(fn_val, (list, tuple)) else (fn_val or "")
		cleaned["field_value"] = ",".join([str(v) for v in fv_val]) if isinstance(fv_val, (list, tuple)) else (fv_val or "")
		return cleaned


@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def category_rules_new(request, category_id: int):
	org = getattr(request, "tenant", None)
	category = get_object_or_404(Category, pk=category_id, organization=org)
	if request.method == "POST":
		form = CategorySupplierRuleForm(request.POST, organization=org, category=category)
		# If autosubmit (field changed), just re-render without saving
		if request.POST.get("autosubmit") == "1":
			return render(request, "core/category_rules_form.html", {"form": form, "category": category, "org": org})
		if form.is_valid():
			form.save()
			return redirect("category_rules_list", category_id=category.id)
	else:
		form = CategorySupplierRuleForm(organization=org, category=category)
	return render(request, "core/category_rules_form.html", {"form": form, "category": category, "org": org})


@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def category_rules_edit(request, category_id: int, pk: int):
	org = getattr(request, "tenant", None)
	category = get_object_or_404(Category, pk=category_id, organization=org)
	obj = get_object_or_404(CategorySupplierRule, pk=pk, category=category, organization=org)
	if request.method == "POST":
		form = CategorySupplierRuleForm(request.POST, instance=obj, organization=org, category=category)
		if request.POST.get("autosubmit") == "1":
			return render(request, "core/category_rules_form.html", {"form": form, "category": category, "org": org})
		if form.is_valid():
			form.save()
			return redirect("category_rules_list", category_id=category.id)
	else:
		form = CategorySupplierRuleForm(instance=obj, organization=org, category=category)
	return render(request, "core/category_rules_form.html", {"form": form, "category": category, "org": org})


@tenant_role_required([Membership.Role.ADMIN, Membership.Role.OWNER])
def category_rules_delete(request, category_id: int, pk: int):
	org = getattr(request, "tenant", None)
	category = get_object_or_404(Category, pk=category_id, organization=org)
	obj = get_object_or_404(CategorySupplierRule, pk=pk, category=category, organization=org)
	if request.method == "POST":
		obj.delete()
		return redirect("category_rules_list", category_id=category.id)
	return render(request, "core/category_rules_confirm_delete.html", {"obj": obj, "category": category, "org": org})


@login_required
def customer_requests_edit(request, pk: int):
	cust = getattr(request.user, "customer_profile", None)
	if not cust:
		return redirect("home")
	_set_tenant_session(request, cust.organization)
	obj = get_object_or_404(Ticket, pk=pk, organization=cust.organization, customer=cust)
	if request.method == "POST":
		form = TicketForm(request.POST, instance=obj, organization=cust.organization, customer=cust)
		if form.is_valid():
			# Build extra_data from dynamic fields for the selected category with validation
			cat = form.cleaned_data.get("category")
			extra: dict = {}
			edit_errors = {}
			prefill_vals = {}
			if cat:
				dyn_fields = CategoryFormField.objects.filter(organization=cust.organization, category=cat).order_by("order", "id")
				for df in dyn_fields:
					key = f"extra-{df.name}"
					val = (request.POST.get(key, "") or "").strip()
					prefill_vals[df.name] = val
					if df.field_type == CategoryFormField.FieldType.SELECT:
						opts = [o.strip() for o in (df.options or "").splitlines() if o.strip()]
						if val and val not in opts:
							edit_errors[df.name] = "Geçersiz seçim."
							val = ""
					if df.required and not val:
						edit_errors[df.name] = edit_errors.get(df.name) or "Bu alan zorunlu."
					# Save non-empty or optional values
					if val or not df.required:
						extra[df.name] = val
			if edit_errors:
				messages.error(request, "Lütfen zorunlu alanları doldurun.")
				# fall through to render with errors and prefill
			else:
				obj = form.save(commit=False)
				obj.extra_data = extra
				obj.save()
				return redirect("customer_requests_list")
	else:
		form = TicketForm(instance=obj, organization=cust.organization, customer=cust)

	# Preload category dynamic field specs for client-side rendering
	cat_fields = {}
	for c in Category.objects.filter(organization=cust.organization).order_by("name"):
		fields = []
		for df in c.form_fields.order_by("order", "id").all():
			fields.append({
				"name": df.name,
				"label": df.label,
				"type": df.field_type,
				"required": df.required,
				"help": df.help_text or "",
				"options": [o.strip() for o in (df.options or "").splitlines() if o.strip()],
			})
		cat_fields[c.id] = fields

	return render(
		request,
		"core/portal_customer_request_edit.html",
		{
			"form": form,
			"customer": cust,
			"org": cust.organization,
			"cat_fields": cat_fields,
			"extra_values": locals().get("prefill_vals", obj.extra_data or {}),
			"dynamic_edit_errors": locals().get("edit_errors", {}),
		},
	)


@login_required
def customer_requests_delete(request, pk: int):
	cust = getattr(request.user, "customer_profile", None)
	if not cust:
		return redirect("home")
	_set_tenant_session(request, cust.organization)
	obj = get_object_or_404(Ticket, pk=pk, organization=cust.organization, customer=cust)
	if request.method == "POST":
		obj.delete()
		return redirect("customer_requests_list")
	return render(request, "core/portal_customer_requests_confirm_delete.html", {"obj": obj, "customer": cust, "org": cust.organization})


@login_required
def customer_requests_detail(request, pk: int):
	cust = getattr(request.user, "customer_profile", None)
	if not cust:
		return redirect("home")
	_set_tenant_session(request, cust.organization)
	obj = get_object_or_404(Ticket, pk=pk, organization=cust.organization, customer=cust)
	if request.method == "POST":
		# Two possible POSTs: accept/reject or file upload
		action = request.POST.get("action")
		if action == "accept" and obj.status == Ticket.Status.OFFERED:
			obj.status = Ticket.Status.ACCEPTED
			obj.save(update_fields=["status"])
			# Create order once on acceptance
			if obj.selected_quote_id and not hasattr(obj, "order"):
				order = Order.objects.create(
					organization=obj.organization,
					ticket=obj,
					quote=obj.selected_quote,
					supplier=(obj.selected_quote.supplier if obj.selected_quote else None),
					currency=obj.selected_quote.currency,
					total=obj.offered_price or Decimal("0.00"),
				)
				items = list(obj.selected_quote.items.all())
				if items:
					adjustments = {a.quote_item_id: a.markup_amount for a in obj.owner_adjustments.all()}
					for it in items:
						m = adjustments.get(it.id) or Decimal("0.00")
						OrderItem.objects.create(
							order=order,
							product=it.product,
							description=it.description,
							quantity=it.quantity,
							supplier_unit_price=it.unit_price,
							owner_markup_total=m,
							sell_total=it.line_total + m,
						)
					# Add a separate line for global markup if any
					if obj.markup_amount and obj.markup_amount > 0:
						OrderItem.objects.create(
							order=order,
							product=None,
							description="İşletme genel kar marjı",
							quantity=1,
							supplier_unit_price=Decimal("0.00"),
							owner_markup_total=obj.markup_amount,
							sell_total=obj.markup_amount,
						)
				else:
					OrderItem.objects.create(
						order=order,
						product=None,
						description=f"Teklif #{obj.selected_quote_id}",
						quantity=1,
						supplier_unit_price=obj.selected_quote.amount or Decimal("0.00"),
						owner_markup_total=(obj.markup_amount or Decimal("0.00")),
						sell_total=obj.offered_price or Decimal("0.00"),
					)
			return redirect("customer_requests_detail", pk=obj.pk)
		elif action == "reject" and obj.status == Ticket.Status.OFFERED:
			obj.status = Ticket.Status.REJECTED
			obj.save(update_fields=["status"])
			return redirect("customer_requests_detail", pk=obj.pk)
		form = TicketAttachmentForm(request.POST, request.FILES)
		if form.is_valid():
			att = form.save(commit=False)
			att.ticket = obj
			att.uploaded_by = request.user
			att.save()
			return redirect("customer_requests_detail", pk=obj.pk)
	else:
		form = TicketAttachmentForm()

	# Map dynamic extra fields to labels for display
	extra_fields = []
	if obj.extra_data:
		try:
			specs = (
				CategoryFormField.objects
				.filter(organization=obj.organization, category=obj.category)
				.order_by("order", "id")
			)
			for f in specs:
				if f.name in obj.extra_data:
					val = obj.extra_data.get(f.name)
					if isinstance(val, list):
						val = ", ".join([str(v) for v in val])
					extra_fields.append({"label": f.label, "value": val})
		except Exception:
			# Fallback: raw key/value list
			for k, v in (obj.extra_data or {}).items():
				extra_fields.append({"label": k, "value": v})

	return render(
		request,
		"core/portal_customer_requests_detail.html",
		{"ticket": obj, "form": form, "org": cust.organization, "extra_fields": extra_fields},
	)


@login_required
def supplier_requests_detail(request, pk: int):
	sup = getattr(request.user, "supplier_profile", None)
	if not sup:
		return redirect("home")
	_set_tenant_session(request, sup.organization)
	obj = get_object_or_404(Ticket, pk=pk, organization=sup.organization)
	# Authorization: ensure this supplier is assigned via rules or category fallback
	if not obj.assigned_suppliers.filter(id=sup.id).exists():
		return redirect("supplier_requests_list")
	existing = Quote.objects.filter(ticket=obj, supplier=sup).first()
	# Use extra=0 and add rows dynamically on the client
	ItemFormSet = formset_factory(QuoteItemForm, extra=0, can_delete=True)
	if request.method == "POST":
		note_form = QuoteNoteForm(request.POST, instance=existing)
		formset = ItemFormSet(request.POST, form_kwargs={"supplier": sup, "category": obj.category})
		if note_form.is_valid() and formset.is_valid():
			quote = note_form.save(commit=False)
			quote.ticket = obj
			quote.supplier = sup
			quote.amount = Decimal("0.00")
			quote.save()
			# Replace items
			QuoteItem.objects.filter(quote=quote).delete()
			total = Decimal("0.00")
			for f in formset:
				if f.cleaned_data and not f.cleaned_data.get("DELETE"):
					desc = f.cleaned_data.get("description")
					qty = f.cleaned_data.get("quantity") or 1
					unit = f.cleaned_data.get("unit_price") or Decimal("0.00")
					prod = f.cleaned_data.get("product")
					if desc and qty and unit is not None:
						item = QuoteItem.objects.create(
							quote=quote,
							product=prod,
							description=desc,
							quantity=qty,
							unit_price=unit,
						)
						total += item.line_total
			quote.amount = total
			quote.full_clean()
			# Save amount, note and currency (in case supplier changed it)
			quote.save(update_fields=["amount", "note", "currency"])
			return redirect("supplier_requests_detail", pk=obj.pk)
	else:
		note_form = QuoteNoteForm(instance=existing)
		initial_items = []
		if existing:
			for it in existing.items.all():
				initial_items.append({
					"product": it.product_id,
					"description": it.description,
					"quantity": it.quantity,
					"unit_price": it.unit_price,
				})
		formset = ItemFormSet(initial=initial_items, form_kwargs={"supplier": sup, "category": obj.category})
	# Prepare labeled dynamic fields for display
	extra_fields = []
	if obj.extra_data:
		try:
			specs = (
				CategoryFormField.objects
				.filter(organization=obj.organization, category=obj.category)
				.order_by("order", "id")
			)
			for f in specs:
				if f.name in obj.extra_data:
					val = obj.extra_data.get(f.name)
					if isinstance(val, list):
						val = ", ".join([str(v) for v in val])
					extra_fields.append({"label": f.label, "value": val})
		except Exception:
			for k, v in (obj.extra_data or {}).items():
				extra_fields.append({"label": k, "value": v})
	return render(
		request,
		"core/portal_supplier_requests_detail.html",
		{
			"ticket": obj,
			"note_form": note_form,
			"items_formset": formset,
			"org": sup.organization,
			"existing": existing,
			"extra_fields": extra_fields,
		},
	)


# ---------- Owner: review quotes, select and set offer ----------
@tenant_role_required([Membership.Role.OWNER])
def ticket_detail_owner(request, pk: int):
	org = getattr(request, "tenant", None)
	obj = get_object_or_404(Ticket.objects.select_related("customer", "category"), pk=pk, organization=org)
	quotes = obj.quotes.select_related("supplier").prefetch_related("items").all()
	comments = obj.quote_comments.select_related("author_customer", "quote").all()

	if request.method == "POST":
		form = OwnerOfferForm(request.POST, ticket=obj)
		if form.is_valid():
			sel: Quote = form.cleaned_data["selected_quote"]
			note = form.cleaned_data.get("offered_note") or ""
			items = list(sel.items.all())
			# Monetary accumulator with 2-decimal rounding
			total = Decimal("0.00")
			# Percentage based per-item markup: inputs named markup_pct_<item.id>
			for item in items:
				pct_key = f"markup_pct_{item.id}"
				raw_pct = request.POST.get(pct_key)
				try:
					pct = Decimal(raw_pct) if raw_pct not in (None, "") else Decimal("0")
				except Exception:
					pct = Decimal("0")
				# Convert percentage to absolute markup amount
				abs_markup = (item.line_total * pct / Decimal("100")) if item.line_total else Decimal("0.00")
				# Quantize to 2 decimal places using half-up to satisfy DecimalField(2)
				abs_markup = abs_markup.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
				OwnerQuoteAdjustment.objects.update_or_create(
					ticket=obj,
					quote_item=item,
					defaults={"markup_amount": abs_markup},
				)
				# Sum and keep total at 2 decimals
				total = (total + item.line_total + abs_markup).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

			# Remove global markup usage; ensure it's zeroed
			obj.markup_amount = Decimal("0.00")
			if not items:
				# Fallback: no itemized quote items -> just supplier quote amount
				total = sel.amount or Decimal("0.00")
			obj.selected_quote = sel
			# Ensure offered_price respects 2 decimal places
			obj.offered_price = (total or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
			obj.offered_note = note
			obj.status = Ticket.Status.OFFERED
			obj.full_clean()
			obj.save()
			messages.success(request, "Teklif ve kalem yüzde karları güncellendi, müşteriye iletildi.")
			return redirect("ticket_detail_owner", pk=obj.pk)
	else:
		initial = {}
		if obj.selected_quote_id:
			initial["selected_quote"] = obj.selected_quote_id
			initial["offered_note"] = obj.offered_note
		form = OwnerOfferForm(initial=initial, ticket=obj)

	# Prepare adjustments dict for pre-filling per-item markup inputs
	# Prepare prefill for per-item markup inputs
	# Build adjustments mapping for all quote items
	adjs_map = {a.quote_item_id: a.markup_amount for a in obj.owner_adjustments.all()}
	quotes_data = []
	cheapest_quote = None
	highest_quote = None
	for q in quotes:
		if cheapest_quote is None or q.amount < cheapest_quote.amount:
			cheapest_quote = q
		if highest_quote is None or q.amount > highest_quote.amount:
			highest_quote = q
		items_payload = []
		for it in q.items.all():
			markup_amt = adjs_map.get(it.id)
			if markup_amt and it.line_total:
				try:
					pct = (markup_amt / it.line_total * Decimal("100")).quantize(Decimal("0.01"))
				except Exception:
					pct = None
			else:
				pct = None
			items_payload.append({
				"id": it.id,
				"description": it.description,
				"quantity": it.quantity,
				"unit_price": str(it.unit_price),
				"line_total": str(it.line_total),
				"prefill_pct": str(pct) if pct is not None else None,
			})
		quotes_data.append({
			"id": q.id,
			"supplier": q.supplier.name,
			"amount": str(q.amount),
			"currency": q.currency,
			"items": items_payload,
		})

	# Basic analysis strings (kept short)
	analysis_base = ""
	if cheapest_quote and highest_quote and cheapest_quote != highest_quote:
		diff = highest_quote.amount - cheapest_quote.amount
		try:
			pct_diff = (diff / cheapest_quote.amount * Decimal("100")).quantize(Decimal("0.01")) if cheapest_quote.amount else Decimal("0.00")
		except Exception:
			pct_diff = Decimal("0.00")
		analysis_base = f"En düşük teklif {cheapest_quote.supplier.name} ({cheapest_quote.amount} {cheapest_quote.currency}). En yüksek teklif {highest_quote.supplier.name} (fark %{pct_diff})."
	elif cheapest_quote:
		analysis_base = f"Tek teklif {cheapest_quote.supplier.name} ({cheapest_quote.amount} {cheapest_quote.currency})."

	# Prepare labeled dynamic fields for display
	extra_fields = []
	if obj.extra_data:
		try:
			specs = (
				CategoryFormField.objects
				.filter(organization=obj.organization, category=obj.category)
				.order_by("order", "id")
			)
			for f in specs:
				if f.name in obj.extra_data:
					val = obj.extra_data.get(f.name)
					if isinstance(val, list):
						val = ", ".join([str(v) for v in val])
					extra_fields.append({"label": f.label, "value": val})
		except Exception:
			for k, v in (obj.extra_data or {}).items():
				extra_fields.append({"label": k, "value": v})

	return render(
		request,
		"core/ticket_detail_owner.html",
		{
			"ticket": obj,
			"quotes": quotes,
			"form": form,
			"org": org,
			"comments": comments,
			"extra_fields": extra_fields,
			"quotes_data": quotes_data,
			"analysis_base": analysis_base,
		},
	)


# ---------- Supplier: products CRUD ----------
from django.views.decorators.http import require_http_methods


@login_required
def supplier_products_list(request):
	sup = getattr(request.user, "supplier_profile", None)
	if not sup:
		return redirect("home")
	_set_tenant_session(request, sup.organization)
	qs = SupplierProduct.objects.filter(supplier=sup, is_active=True).select_related("category")
	return render(request, "core/portal_supplier_products_list.html", {"products": qs, "supplier": sup, "org": sup.organization})


@login_required
def supplier_products_new(request):
	sup = getattr(request.user, "supplier_profile", None)
	if not sup:
		return redirect("home")
	_set_tenant_session(request, sup.organization)
	if request.method == "POST":
		form = SupplierProductForm(request.POST, organization=sup.organization, supplier=sup)
		if form.is_valid():
			obj = form.save(commit=False)
			obj.organization = sup.organization
			obj.supplier = sup
			obj.save()
			return redirect("supplier_products_list")
	else:
		form = SupplierProductForm(organization=sup.organization, supplier=sup)
	return render(request, "core/portal_supplier_products_form.html", {"form": form, "supplier": sup, "org": sup.organization})


@login_required
def supplier_products_edit(request, pk: int):
	sup = getattr(request.user, "supplier_profile", None)
	if not sup:
		return redirect("home")
	_set_tenant_session(request, sup.organization)
	obj = get_object_or_404(SupplierProduct, pk=pk, supplier=sup)
	if request.method == "POST":
		form = SupplierProductForm(request.POST, instance=obj, organization=sup.organization, supplier=sup)
		if form.is_valid():
			form.save()
			return redirect("supplier_products_list")
	else:
		form = SupplierProductForm(instance=obj, organization=sup.organization, supplier=sup)
	return render(request, "core/portal_supplier_products_form.html", {"form": form, "supplier": sup, "org": sup.organization})


@login_required
def supplier_products_delete(request, pk: int):
	sup = getattr(request.user, "supplier_profile", None)
	if not sup:
		return redirect("home")
	_set_tenant_session(request, sup.organization)
	obj = get_object_or_404(SupplierProduct, pk=pk, supplier=sup)
	if request.method == "POST":
		obj.delete()
		return redirect("supplier_products_list")
	return render(request, "core/portal_supplier_products_confirm_delete.html", {"obj": obj, "supplier": sup, "org": sup.organization})


# ---------- Owner: Orders list (runsayfası) ----------
@tenant_role_required([Membership.Role.OWNER])
def orders_list(request):
	org = getattr(request, "tenant", None)
	qs = (
		Order.objects.filter(organization=org)
		.select_related("ticket", "ticket__customer", "quote", "supplier")
		.order_by("-created_at")
	)
	q = (request.GET.get("q") or "").strip()
	if q:
		qs = qs.filter(
			models.Q(ticket__title__icontains=q)
			| models.Q(ticket__customer__name__icontains=q)
			| models.Q(quote__supplier__name__icontains=q)
		)
	return render(request, "core/orders_list.html", {"orders": qs, "org": org, "q": q})


@tenant_role_required([Membership.Role.OWNER])
def order_detail(request, pk: int):
	org = getattr(request, "tenant", None)
	order = get_object_or_404(
		Order.objects.select_related("ticket", "ticket__customer", "quote", "supplier"),
		pk=pk,
		organization=org,
	)
	# Suppliers available via rule-based assignment (fallback to category.suppliers)
	suppliers = order.ticket.assigned_suppliers if order.ticket else []
	if request.method == "POST":
		action = request.POST.get("action")
		if action == "approve" and order.status == Order.Status.NEW:
			sid = request.POST.get("supplier")
			if sid:
				try:
					sel = suppliers.get(pk=int(sid))
					order.supplier = sel
				except Exception:
					pass
			elif not order.supplier and order.quote:
				order.supplier = order.quote.supplier
			order.status = Order.Status.PROCESSING
			order.save(update_fields=["supplier", "status"])
			messages.success(request, "Sipariş onaylandı ve işleme alındı.")
			return redirect("orders_list")
		elif action == "complete" and order.status in [Order.Status.PROCESSING, Order.Status.NEW]:
			order.status = Order.Status.COMPLETED
			order.save(update_fields=["status"])
			messages.success(request, "Sipariş tamamlandı.")
			return redirect("orders_list")
		elif action == "cancel" and order.status in [Order.Status.NEW, Order.Status.PROCESSING]:
			order.status = Order.Status.CANCELLED
			order.save(update_fields=["status"])
			messages.warning(request, "Sipariş iptal edildi.")
			return redirect("orders_list")
	# Default selected supplier
	selected_supplier_id = order.supplier_id or (order.quote.supplier_id if order.quote_id else None)
	return render(
		request,
		"core/order_detail.html",
		{"order": order, "suppliers": suppliers, "selected_supplier_id": selected_supplier_id, "org": org},
	)


@login_required
def customer_offers_pdf(request, pk: int):
    cust = getattr(request.user, "customer_profile", None)
    if not cust:
        return redirect("home")
    _set_tenant_session(request, cust.organization)
    ticket = get_object_or_404(
        Ticket.objects.select_related("category").prefetch_related("quotes__supplier"),
        pk=pk,
        organization=cust.organization,
        customer=cust,
    )

    # Build items for PDF similar to detail view
    selected_items = []
    currency = None
    if ticket.selected_quote_id and ticket.selected_quote:
        currency = ticket.selected_quote.currency
        items = list(ticket.selected_quote.items.all())
        if items:
            adjs = {a.quote_item_id: a.markup_amount for a in ticket.owner_adjustments.all()}
            for it in items:
                supplier_total = it.line_total
                markup = adjs.get(it.id) or Decimal("0.00")
                selected_items.append({
                    "description": it.description,
                    "quantity": it.quantity,
                    "sell_unit_price": (supplier_total + markup) / (it.quantity or 1),
                    "sell_total": supplier_total + markup,
                })

    html = render_to_string(
        "core/portal_customer_offer_pdf.html",
        {
            "ticket": ticket,
            "items": selected_items,
            "currency": currency or (ticket.selected_quote.currency if ticket.selected_quote else ""),
            "org": cust.organization,
        },
    )

    # Lazy import of xhtml2pdf
    from xhtml2pdf import pisa
    from django.http import HttpResponse

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="teklif_{ticket.id}.pdf"'
    pisa.CreatePDF(src=html, dest=response)
    return response


@login_required
def customer_orders_list(request):
    cust = getattr(request.user, "customer_profile", None)
    if not cust:
        return redirect("home")
    _set_tenant_session(request, cust.organization)
    orders = (
        Order.objects.filter(organization=cust.organization, ticket__customer=cust)
        .select_related("ticket", "quote")
        .order_by("-created_at")
    )
    return render(
        request,
        "core/portal_customer_orders_list.html",
        {"orders": orders, "customer": cust, "org": cust.organization},
    )


@login_required
def customer_products_list(request):
    cust = getattr(request.user, "customer_profile", None)
    if not cust:
        return redirect("home")
    _set_tenant_session(request, cust.organization)

    # Gather previously ordered products for this customer
    from billing.models import OrderItem, Order
    items_qs = (
        OrderItem.objects
        .filter(order__organization=cust.organization, order__ticket__customer=cust, product__isnull=False)
        .select_related("product", "product__supplier", "product__category")
        .order_by("product__name")
    )
    # Unique by product id preserving order
    seen = set()
    products = []
    for it in items_qs:
        pid = getattr(it.product, "id", None)
        if pid and pid not in seen:
            seen.add(pid)
            products.append(it.product)

    if request.method == "POST":
        selected = []
        for p in products:
            key = f"prod_{p.id}"
            qty_key = f"qty_{p.id}"
            if request.POST.get(key) == "on":
                try:
                    qty = int(request.POST.get(qty_key) or "1")
                except Exception:
                    qty = 1
                qty = max(1, qty)
                selected.append((p, qty))
        if not selected:
            messages.warning(request, "Lütfen en az bir ürün seçin.")
        else:
            # Create tickets for each selected product under its category
            created = 0
            for p, qty in selected:
                Ticket.objects.create(
                    organization=cust.organization,
                    customer=cust,
                    category=p.category,
                    title=f"{p.name} yeniden sipariş",
                    description=p.description or "",
                    desired_quantity=qty,
                    extra_data={"product_id": p.id, "reorder": True},
                )
                created += 1
            messages.success(request, f"{created} talep oluşturuldu.")
            return redirect("customer_requests_list")

    return render(
        request,
        "core/portal_customer_products_list.html",
        {"products": products, "customer": cust, "org": cust.organization},
    )
