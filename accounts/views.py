from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .permissions import backoffice_only
from .models import Organization, Membership


def login_view(request):
	if request.method == "POST":
		form = AuthenticationForm(request, data=request.POST)
		if form.is_valid():
			user = form.get_user()
			login(request, user)
			return redirect("portal_home")
		messages.error(request, "Giriş başarısız")
	else:
		form = AuthenticationForm(request)
	return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
	logout(request)
	return redirect("role_landing")


def signup_view(request):
	if request.method == "POST":
		form = UserCreationForm(request.POST)
		if form.is_valid():
			user = form.save()
			login(request, user)
			return redirect("portal_home")
		messages.error(request, "Kayıt başarısız")
	else:
		form = UserCreationForm()
	return render(request, "accounts/signup.html", {"form": form})


@backoffice_only
def org_list(request):
	orgs = Organization.objects.filter(memberships__user=request.user).distinct()
	current = getattr(request, "tenant", None)
	return render(request, "accounts/org_list.html", {"orgs": orgs, "current": current})


@backoffice_only
def org_create(request):
	if request.method == "POST":
		name = request.POST.get("name", "").strip()
		if name:
			org = Organization.objects.create(name=name, owner=request.user)
			Membership.objects.create(user=request.user, organization=org, role=Membership.Role.OWNER)
			request.session["current_org"] = org.slug
			return redirect("role_landing")
		messages.error(request, "İsim gerekli")
	return render(request, "accounts/org_create.html")


@backoffice_only
def org_switch(request, slug: str):
	org = Organization.objects.filter(slug=slug, memberships__user=request.user).first()
	if not org:
		messages.error(request, "Bu organizasyona erişiminiz yok")
		return redirect("org_list")
	request.session["current_org"] = org.slug
	return redirect("role_landing")


@backoffice_only
def org_settings(request, pk: int):
	org = get_object_or_404(Organization, pk=pk, memberships__user=request.user)
	
	# Check if user is owner or admin
	membership = Membership.objects.filter(user=request.user, organization=org).first()
	if not membership or membership.role not in [Membership.Role.OWNER, Membership.Role.ADMIN]:
		messages.error(request, "Bu ayarlara erişim yetkiniz yok")
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
		
		org.save()
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
	org = get_object_or_404(Organization, pk=pk, memberships__user=request.user)
	
	# Only owner can delete organization
	membership = Membership.objects.filter(user=request.user, organization=org).first()
	if not membership or membership.role != Membership.Role.OWNER:
		messages.error(request, "Sadece organizasyon sahibi silebilir")
		return redirect("org_list")
	
	if request.method == "POST":
		org_name = org.name
		org.delete()  # This will trigger the post_delete signal
		messages.success(request, f"{org_name} organizasyonu silindi")
		return redirect("org_list")
	
	return render(request, "accounts/org_delete.html", {"org": org})


@backoffice_only
def org_members(request, pk: int):
	org = get_object_or_404(Organization, pk=pk, memberships__user=request.user)
	
	# Check if user is owner or admin
	membership = Membership.objects.filter(user=request.user, organization=org).first()
	if not membership or membership.role not in [Membership.Role.OWNER, Membership.Role.ADMIN]:
		messages.error(request, "Bu sayfaya erişim yetkiniz yok")
		return redirect("org_list")
	
	members = Membership.objects.filter(organization=org).select_related('user').order_by('-created_at')
	
	return render(request, "accounts/org_members.html", {
		"org": org,
		"members": members,
		"is_owner": membership.role == Membership.Role.OWNER
	})


@backoffice_only
def org_member_add(request, pk: int):
	from django.contrib.auth import get_user_model
	User = get_user_model()
	
	org = get_object_or_404(Organization, pk=pk, memberships__user=request.user)
	
	# Only owner or admin can add members
	membership = Membership.objects.filter(user=request.user, organization=org).first()
	if not membership or membership.role not in [Membership.Role.OWNER, Membership.Role.ADMIN]:
		messages.error(request, "Kullanıcı ekleme yetkiniz yok")
		return redirect("org_members", pk=pk)
	
	if request.method == "POST":
		username_or_email = request.POST.get("username_or_email", "").strip()
		role = request.POST.get("role", Membership.Role.MEMBER)
		create_if_not_exists = request.POST.get("create_if_not_exists") == "1"
		
		if not username_or_email:
			messages.error(request, "Kullanıcı adı veya e-posta gerekli")
			return render(request, "accounts/org_member_add.html", {"org": org})
		
		# Find user by username or email
		user = User.objects.filter(username=username_or_email).first() or \
		       User.objects.filter(email=username_or_email).first()
		
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
					while User.objects.filter(username=username).exists():
						username = f"{base_username}{counter}"
						counter += 1
				else:
					username = username_or_email
					email = ""
				
				# Generate random password
				password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
				
				# Create user
				user = User.objects.create_user(username=username, email=email, password=password)
				messages.success(request, f"Yeni kullanıcı oluşturuldu: {username} (Şifre: {password})")
			else:
				messages.error(request, f"'{username_or_email}' kullanıcısı bulunamadı")
				return render(request, "accounts/org_member_add.html", {
					"org": org,
					"username_or_email": username_or_email
				})
		
		# Check if already a member
		if Membership.objects.filter(user=user, organization=org).exists():
			messages.error(request, f"{user.username} zaten bu organizasyonun üyesi")
			return redirect("org_members", pk=pk)
		
		# Create membership
		Membership.objects.create(user=user, organization=org, role=role)
		messages.success(request, f"{user.username} organizasyona eklendi")
		return redirect("org_members", pk=pk)
	
	return render(request, "accounts/org_member_add.html", {
		"org": org,
		"roles": Membership.Role.choices
	})


@backoffice_only
def org_member_edit(request, pk: int, member_id: int):
	org = get_object_or_404(Organization, pk=pk, memberships__user=request.user)
	member = get_object_or_404(Membership, pk=member_id, organization=org)
	
	# Only owner or admin can edit members
	user_membership = Membership.objects.filter(user=request.user, organization=org).first()
	if not user_membership or user_membership.role not in [Membership.Role.OWNER, Membership.Role.ADMIN]:
		messages.error(request, "Kullanıcı düzenleme yetkiniz yok")
		return redirect("org_members", pk=pk)
	
	# Can't edit owner
	if member.role == Membership.Role.OWNER and user_membership.role != Membership.Role.OWNER:
		messages.error(request, "Sahip rolünü değiştiremezsiniz")
		return redirect("org_members", pk=pk)
	
	if request.method == "POST":
		new_role = request.POST.get("role")
		
		# Can't change owner role
		if member.role == Membership.Role.OWNER:
			messages.error(request, "Sahip rolü değiştirilemez")
			return redirect("org_members", pk=pk)
		
		member.role = new_role
		member.save()
		messages.success(request, f"{member.user.username} rolü güncellendi")
		return redirect("org_members", pk=pk)
	
	return render(request, "accounts/org_member_edit.html", {
		"org": org,
		"member": member,
		"roles": Membership.Role.choices
	})


@backoffice_only
def org_member_delete(request, pk: int, member_id: int):
	org = get_object_or_404(Organization, pk=pk, memberships__user=request.user)
	member = get_object_or_404(Membership, pk=member_id, organization=org)
	
	# Only owner or admin can delete members
	user_membership = Membership.objects.filter(user=request.user, organization=org).first()
	if not user_membership or user_membership.role not in [Membership.Role.OWNER, Membership.Role.ADMIN]:
		messages.error(request, "Kullanıcı silme yetkiniz yok")
		return redirect("org_members", pk=pk)
	
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
		member.delete()
		messages.success(request, f"{username} organizasyondan çıkarıldı")
		return redirect("org_members", pk=pk)
	
	return render(request, "accounts/org_member_delete.html", {
		"org": org,
		"member": member
	})
