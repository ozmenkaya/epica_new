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
