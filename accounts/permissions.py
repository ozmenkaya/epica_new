from functools import wraps
from typing import Iterable, Callable, Any, Optional
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from .models import Membership, Organization


def _portal_guard(request: HttpRequest) -> Optional[HttpResponse]:
    """Return 403 if request.user is a portal-only user (customer or supplier)."""
    if getattr(request.user, "customer_profile", None) or getattr(request.user, "supplier_profile", None):
        return HttpResponseForbidden("Portal users cannot access this area")
    return None


def backoffice_only(view_func: Callable[..., HttpResponse]):
    """Decorator: allow only non-portal users into a view (still requires login)."""
    @login_required
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args: Any, **kwargs: Any):
        guard = _portal_guard(request)
        if guard is not None:
            return guard
        return view_func(request, *args, **kwargs)

    return _wrapped


def tenant_member_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        from django.shortcuts import render
        guard = _portal_guard(request)
        if guard is not None:
            return guard
        org = getattr(request, "tenant", None)
        if not org:
            return redirect("org_list")
        if not Membership.objects.using('default').filter(user=request.user, organization=org).exists():
            # Show a friendly error page instead of 403
            return render(request, "accounts/not_member.html", {
                "org": org,
                "user": request.user
            }, status=403)
        return view_func(request, *args, **kwargs)

    return _wrapped


def tenant_role_required(roles: Iterable[str]):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request: HttpRequest, *args, **kwargs):
            guard = _portal_guard(request)
            if guard is not None:
                return guard
            org = getattr(request, "tenant", None)
            if not org:
                return redirect("org_list")
            mem = Membership.objects.using('default').filter(user=request.user, organization=org).first()
            allowed = False
            if mem:
                if mem.role in roles:
                    allowed = True
                elif mem.role_fk and mem.role_fk.key in roles:
                    allowed = True
            if not allowed:
                return HttpResponseForbidden("Insufficient role")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def page_permission_required(permission_key: str):
    """
    Decorator: Check if user has specific page permission.
    Combines tenant membership check with page-level permission.
    """
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request: HttpRequest, *args, **kwargs):
            from django.shortcuts import render
            
            guard = _portal_guard(request)
            if guard is not None:
                return guard
            
            org = getattr(request, "tenant", None)
            if not org:
                return redirect("org_list")
            
            mem = Membership.objects.using('default').filter(user=request.user, organization=org).first()
            if not mem:
                return render(request, "accounts/not_member.html", {
                    "org": org,
                    "user": request.user
                }, status=403)
            
            # Check if user has the required permission
            if not mem.has_permission(permission_key):
                return render(request, "accounts/no_permission.html", {
                    "org": org,
                    "user": request.user,
                    "required_permission": permission_key
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped
    
    return decorator
