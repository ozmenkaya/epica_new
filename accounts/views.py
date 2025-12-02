from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from .permissions import backoffice_only
from .models import Organization, Membership
import logging

logger = logging.getLogger(__name__)


@sensitive_post_parameters('password')
@csrf_protect
@never_cache
def login_view(request):
	"""
	Secure login view with comprehensive user routing.
	
	Routing priority:
	1. ?next parameter (if safe)
	2. Staff/Superuser -> Django Admin
	3. Customer profile -> Customer Portal
	4. Supplier profile -> Supplier Portal
	5. Organization member -> Role-based landing
	6. No organization -> Organization creation
	"""
	# Redirect if already authenticated
	if request.user.is_authenticated:
		return _redirect_authenticated_user(request.user, request)
	
	if request.method == "POST":
		form = AuthenticationForm(request, data=request.POST)
		if form.is_valid():
			user = form.get_user()
			
			# Check if user account is active
			if not user.is_active:
				messages.error(request, "Bu hesap devre dışı bırakılmış.")
				logger.warning(f"Inactive user login attempt: {user.username}")
				return render(request, "accounts/login.html", {"form": form})
			
			# Perform login
			login(request, user)
			logger.info(f"User logged in successfully: {user.username}")
			
			# Handle "Remember Me" functionality
			remember_me = request.POST.get('remember_me')
			if not remember_me:
				# If not checked, expire session when browser closes
				request.session.set_expiry(0)
			else:
				# If checked, use the default SESSION_COOKIE_AGE (2 weeks)
				request.session.set_expiry(None)
			
			# Determine redirect destination
			return _redirect_authenticated_user(user, request)
		else:
			# Log failed login attempts
			username = request.POST.get('username', '')
			logger.warning(f"Failed login attempt for username: {username}")
			messages.error(request, "Kullanıcı adı veya şifre hatalı. Lütfen tekrar deneyin.")
	else:
		form = AuthenticationForm(request)
	
	return render(request, "accounts/login.html", {"form": form})


def _redirect_authenticated_user(user, request):
	"""
	Determine where to redirect an authenticated user based on their profile.
	
	Args:
		user: The authenticated User object
		request: The HTTP request object
	
	Returns:
		HttpResponseRedirect to the appropriate destination
	"""
	# 1. Check for safe next parameter
	next_url = request.GET.get("next") or request.POST.get("next")
	if next_url and _is_safe_url(next_url, request):
		return redirect(next_url)
	
	# 2. Staff/Superuser -> Django Admin
	if user.is_staff or user.is_superuser:
		logger.info(f"Redirecting staff user {user.username} to admin")
		return redirect("/admin/")
	
	# 3. Customer profile -> Customer Portal
	customer_profile = getattr(user, 'customer_profile', None)
	if customer_profile is not None:
		logger.info(f"Redirecting customer {user.username} to customer portal")
		# Set organization in session
		request.session["current_org"] = customer_profile.organization.slug
		return redirect("customer_portal")
	
	# 4. Supplier profile -> Supplier Portal
	supplier_profile = getattr(user, 'supplier_profile', None)
	if supplier_profile is not None:
		logger.info(f"Redirecting supplier {user.username} to supplier portal")
		# Set first organization in session if available
		first_org = supplier_profile.organizations.first()
		if first_org:
			request.session["current_org"] = first_org.slug
		return redirect("supplier_portal")
	
	# 5. Organization member -> Check organizations
	user_memberships = Membership.objects.using('default').filter(
		user=user
	).select_related("organization")
	
	if user_memberships.exists():
		# User has organization access - use role landing
		logger.info(f"Redirecting organization member {user.username} to role landing")
		return redirect("role_landing")
	
	# 6. No organization -> Guide to create one
	logger.info(f"New user {user.username} with no organization - redirecting to org creation")
	messages.info(request, "Hoş geldiniz! Devam etmek için bir organizasyon oluşturun.")
	return redirect("org_create")


def _is_safe_url(url, request):
	"""
	Check if a redirect URL is safe to prevent open redirect vulnerabilities.
	
	Args:
		url: The URL to check
		request: The HTTP request object
	
	Returns:
		bool: True if URL is safe, False otherwise
	"""
	from django.utils.http import url_has_allowed_host_and_scheme
	
	# Get allowed hosts from settings
	from django.conf import settings
	allowed_hosts = settings.ALLOWED_HOSTS
	
	# Check if URL is safe
	return url_has_allowed_host_and_scheme(
		url=url,
		allowed_hosts=allowed_hosts,
		require_https=request.is_secure()
	)
@login_required
@never_cache
def logout_view(request):
	"""
	Secure logout view that clears session and redirects to home.
	"""
	username = request.user.username if request.user.is_authenticated else "Unknown"
	logout(request)
	logger.info(f"User logged out: {username}")
	messages.success(request, "Başarıyla çıkış yaptınız.")
	return redirect("home")


@sensitive_post_parameters('password1', 'password2')
@csrf_protect
@never_cache
def signup_view(request):
	"""
	User registration view.
	After successful signup, user is logged in and redirected to create an organization.
	"""
	# Redirect if already authenticated
	if request.user.is_authenticated:
		messages.info(request, "Zaten giriş yapmışsınız.")
		return redirect("role_landing")
	
	if request.method == "POST":
		form = UserCreationForm(request.POST)
		if form.is_valid():
			# Create user account
			user = form.save()
			username = user.username
			
			# Log the user in automatically
			login(request, user)
			logger.info(f"New user registered and logged in: {username}")
			
			# Guide to create organization
			messages.success(request, f"Hoş geldiniz {username}! Devam etmek için bir organizasyon oluşturun.")
			return redirect("org_create")
		else:
			# Show specific validation errors
			for field, errors in form.errors.items():
				for error in errors:
					messages.error(request, f"{form.fields.get(field).label if field != '__all__' else 'Hata'}: {error}")
			logger.warning(f"Failed signup attempt with errors: {form.errors}")
	else:
		form = UserCreationForm()
	
	return render(request, "accounts/signup.html", {"form": form})


@backoffice_only
def org_list(request):
	orgs = Organization.objects.using('default').filter(memberships__user=request.user).distinct()
	
	# If user has no organizations, redirect to create one
	if not orgs.exists():
		messages.info(request, "Henüz bir organizasyonunuz yok. Lütfen bir organizasyon oluşturun.")
		return redirect("org_create")
	
	current = getattr(request, "tenant", None)
	return render(request, "accounts/org_list.html", {"orgs": orgs, "current": current})


@login_required
def org_create(request):
	# Allow portal users (customer/supplier) to access if they have no org
	# but prevent them if they already have portal access
	cust = getattr(request.user, 'customer_profile', None)
	sup = getattr(request.user, 'supplier_profile', None)
	if cust or sup:
		messages.error(request, "Portal kullanıcıları organizasyon oluşturamaz")
		return redirect("home")
	
	if request.method == "POST":
		name = request.POST.get("name", "").strip()
		if name:
			org = Organization.objects.db_manager('default').create(name=name, owner=request.user)
			Membership.objects.db_manager('default').create(user=request.user, organization=org, role=Membership.Role.OWNER)
			request.session["current_org"] = org.slug
			request.session.modified = True  # Force Django to save session
			messages.success(request, f"{name} organizasyonu oluşturuldu")
			return redirect("role_landing")
		messages.error(request, "İsim gerekli")
	return render(request, "accounts/org_create.html")


@backoffice_only
def org_switch(request, slug: str):
	org = Organization.objects.using('default').filter(slug=slug, memberships__user=request.user).first()
	if not org:
		messages.error(request, "Bu organizasyona erişiminiz yok")
		return redirect("org_list")
	
	# Update session to set the new organization
	request.session["current_org"] = org.slug
	request.session.modified = True  # Force Django to save session
	messages.success(request, f"{org.name} organizasyonuna geçildi")
	return redirect("dashboard")


@backoffice_only
def org_settings(request, pk: int):
	org = get_object_or_404(Organization.objects.using('default'), pk=pk, memberships__user=request.user)
	
	# Only owner can access
	if org.owner != request.user:
		messages.error(request, "Bu ayarlara erişim yetkiniz yok - Sadece organizasyon sahibi erişebilir")
		return redirect("org_list")
	
	if request.method == "POST":
		# Get form data
		org.email_host = request.POST.get("email_host", "").strip()
		org.email_port = request.POST.get("email_port", "").strip()
		org.email_use_tls = "email_use_tls" in request.POST
		org.email_use_ssl = "email_use_ssl" in request.POST
		org.email_host_user = request.POST.get("email_host_user", "").strip()
		org.email_host_password = request.POST.get("email_host_password", "").strip()
		org.email_from_address = request.POST.get("email_from_address", "").strip()
		
		# Convert port to int if provided
		if org.email_port:
			try:
				org.email_port = int(org.email_port)
			except ValueError:
				messages.error(request, "Port numarası geçersiz")
				return render(request, "accounts/org_settings.html", {"org": org, "form": request.POST})
		else:
			org.email_port = None
		
		# Validate: if any field is filled, all required fields must be filled
		has_any = any([org.email_host, org.email_port, org.email_host_user, org.email_host_password])
		if has_any:
			if not all([org.email_host, org.email_port, org.email_host_user, org.email_host_password]):
				messages.error(request, "E-posta ayarlarını kullanmak için SMTP sunucu, port, kullanıcı adı ve şifre alanları gereklidir")
				return render(request, "accounts/org_settings.html", {"org": org, "form": request.POST})
		
		org.save(using='default')
		messages.success(request, "E-posta ayarları kaydedildi")
		return redirect("org_list")
	
	# Prepare form data for GET request
	form = {
		"email_host": {"value": org.email_host or ""},
		"email_port": {"value": org.email_port or ""},
		"email_use_tls": {"value": org.email_use_tls},
		"email_use_ssl": {"value": org.email_use_ssl},
		"email_host_user": {"value": org.email_host_user or ""},
		"email_host_password": {"value": org.email_host_password or ""},
		"email_from_address": {"value": org.email_from_address or ""},
	}
	
	return render(request, "accounts/org_settings.html", {"org": org, "form": form})


@backoffice_only
def org_delete(request, pk: int):
	org = get_object_or_404(Organization.objects.using('default'), pk=pk, memberships__user=request.user)
	
	# Only owner can delete organization
	membership = Membership.objects.using('default').filter(user=request.user, organization=org).first()
	if not membership or membership.role != Membership.Role.OWNER:
		messages.error(request, "Sadece organizasyon sahibi silebilir")
		return redirect("org_list")
	
	if request.method == "POST":
		org_name = org.name
		org.delete(using='default')  # This will trigger the post_delete signal
		messages.success(request, f"{org_name} organizasyonu silindi")
		return redirect("org_list")
	
	return render(request, "accounts/org_delete.html", {"org": org})


@backoffice_only
def org_members(request, pk: int):
	org = get_object_or_404(Organization.objects.using('default'), pk=pk, memberships__user=request.user)
	
	# Only owner can access
	if org.owner != request.user:
		messages.error(request, "Bu sayfaya erişim yetkiniz yok - Sadece organizasyon sahibi erişebilir")
		return redirect("org_list")
	
	membership = Membership.objects.using('default').filter(user=request.user, organization=org).first()
	if not membership:
		messages.error(request, "Bu organizasyonun üyesi değilsiniz")
		return redirect("org_list")
	
	members = Membership.objects.using('default').filter(organization=org).select_related('user').order_by('-created_at')
	
	return render(request, "accounts/org_members.html", {
		"org": org,
		"members": members,
		"is_owner": membership.role == Membership.Role.OWNER
	})


@backoffice_only
def org_member_add(request, pk: int):
	from django.contrib.auth import get_user_model
	User = get_user_model()
	
	org = get_object_or_404(Organization.objects.using('default'), pk=pk, memberships__user=request.user)
	
	# Only owner can add members
	if org.owner != request.user:
		messages.error(request, "Kullanıcı ekleme yetkiniz yok - Sadece organizasyon sahibi ekleyebilir")
		return redirect("org_list")
	
	if request.method == "POST":
		username_or_email = request.POST.get("username_or_email", "").strip()
		email_input = request.POST.get("email", "").strip()
		password_input = request.POST.get("password", "").strip()
		role = request.POST.get("role", Membership.Role.MEMBER)
		create_if_not_exists = request.POST.get("create_if_not_exists") == "1"
		
		if not username_or_email:
			messages.error(request, "Kullanıcı adı veya e-posta gerekli")
			return render(request, "accounts/org_member_add.html", {"org": org})
		
		# Find user by username or email (always use default database for auth)
		user = User.objects.using('default').filter(username=username_or_email).first() or \
		       User.objects.using('default').filter(email=username_or_email).first()
		
		if not user:
			if create_if_not_exists:
				# Create new user
				import secrets
				import string
				
				# Check if input is email
				if "@" in username_or_email:
					email = username_or_email
					# Generate username from email
					username = email.split("@")[0]
					# Ensure unique username
					base_username = username
					counter = 1
					while User.objects.using('default').filter(username=username).exists():
						username = f"{base_username}{counter}"
						counter += 1
				else:
					username = username_or_email
					email = ""
				
				# Use provided password or generate random one
				if password_input:
					password = password_input
				else:
					password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
				
				# Create user (always in default database)
				user = User.objects.db_manager('default').create_user(username=username, email=email, password=password)
				messages.success(request, f"Yeni kullanıcı oluşturuldu: {username} (Şifre: {password})")
			else:
				messages.error(request, f"'{username_or_email}' kullanıcısı bulunamadı")
				return render(request, "accounts/org_member_add.html", {
					"org": org,
					"username_or_email": username_or_email,
					"email": email_input,
					"password": password_input,
					"roles": Membership.Role.choices
				})
		
		# Update email if provided and different
		if email_input and user.email != email_input:
			user.email = email_input
			user.save(using='default')
			messages.info(request, f"{user.username} kullanıcısının e-posta adresi güncellendi")
		
		# Update password if provided
		if password_input:
			user.set_password(password_input)
			user.save(using='default')
			messages.info(request, f"{user.username} kullanıcısının şifresi güncellendi")
		
		# Check if already a member (always use default database for organization data)
		if Membership.objects.using('default').filter(user=user, organization=org).exists():
			messages.error(request, f"{user.username} zaten bu organizasyonun üyesi")
			return redirect("org_members", pk=pk)
		
		# Get selected permissions
		permissions_input = request.POST.getlist("permissions")
		
		# Create membership (always in default database)
		membership = Membership.objects.db_manager('default').create(user=user, organization=org, role=role)
		
		# Set custom permissions if provided
		if permissions_input:
			membership.custom_permissions = {"allowed": permissions_input}
			membership.save(using='default')
		
		messages.success(request, f"{user.username} organizasyona eklendi")
		return redirect("org_members", pk=pk)
	
	from .permissions_config import PAGE_PERMISSIONS, ROLE_DEFAULT_PERMISSIONS
	import json
	
	return render(request, "accounts/org_member_add.html", {
		"org": org,
		"roles": Membership.Role.choices,
		"page_permissions": PAGE_PERMISSIONS,
		"role_defaults": json.dumps(ROLE_DEFAULT_PERMISSIONS),
	})


@backoffice_only
def org_member_edit(request, pk: int, member_id: int):
	org = get_object_or_404(Organization.objects.using('default'), pk=pk, memberships__user=request.user)
	member = get_object_or_404(Membership.objects.using('default'), pk=member_id, organization=org)
	
	# Only owner can edit members
	if org.owner != request.user:
		messages.error(request, "Kullanıcı düzenleme yetkiniz yok - Sadece organizasyon sahibi düzenleyebilir")
		return redirect("org_list")
	
	if request.method == "POST":
		new_role = request.POST.get("role")
		permissions_input = request.POST.getlist("permissions")
		new_password = request.POST.get("new_password", "").strip()
		
		# Can't change owner role
		if member.role == Membership.Role.OWNER:
			messages.error(request, "Sahip rolü değiştirilemez")
			return redirect("org_members", pk=pk)
		
		member.role = new_role
		
		# Update custom permissions
		if permissions_input:
			member.custom_permissions = {"allowed": permissions_input}
		else:
			member.custom_permissions = {}
		
		member.save(using='default')
		
		# Update password if provided
		if new_password:
			member.user.set_password(new_password)
			member.user.save(using='default')
			messages.success(request, f"{member.user.username} rolü, yetkileri ve şifresi güncellendi")
		else:
			messages.success(request, f"{member.user.username} rolü ve yetkileri güncellendi")
		
		return redirect("org_members", pk=pk)
	
	from .permissions_config import PAGE_PERMISSIONS, ROLE_DEFAULT_PERMISSIONS
	import json
	
	return render(request, "accounts/org_member_edit.html", {
		"org": org,
		"member": member,
		"roles": Membership.Role.choices,
		"page_permissions": PAGE_PERMISSIONS,
		"role_defaults": json.dumps(ROLE_DEFAULT_PERMISSIONS),
		"current_permissions": member.get_permissions(),
	})


@backoffice_only
def org_member_delete(request, pk: int, member_id: int):
	org = get_object_or_404(Organization.objects.using('default'), pk=pk, memberships__user=request.user)
	member = get_object_or_404(Membership.objects.using('default'), pk=member_id, organization=org)
	
	# Only owner can delete members
	if org.owner != request.user:
		messages.error(request, "Kullanıcı silme yetkiniz yok - Sadece organizasyon sahibi silebilir")
		return redirect("org_list")
	
	# Can't delete owner
	if member.role == Membership.Role.OWNER:
		messages.error(request, "Sahip silinemez")
		return redirect("org_members", pk=pk)
	
	# Can't delete yourself
	if member.user == request.user:
		messages.error(request, "Kendinizi çıkaramazsınız")
		return redirect("org_members", pk=pk)
	
	if request.method == "POST":
		username = member.user.username
		member.delete(using='default')
		messages.success(request, f"{username} organizasyondan çıkarıldı")
		return redirect("org_members", pk=pk)
	
	return render(request, "accounts/org_member_delete.html", {
		"org": org,
		"member": member
	})
