from typing import Optional
from django.http import HttpRequest
from django.utils.deprecation import MiddlewareMixin
from accounts.models import Organization, Membership
import logging

logger = logging.getLogger(__name__)


class TenantMiddleware(MiddlewareMixin):
    """
    Resolve current tenant from query parameter or session.
    Also sets the appropriate database for multi-tenant database isolation.
    
    Priority:
    1. Query parameter (?org=helmex)
    2. Session (stored from previous request)
    """

    def process_request(self, request: HttpRequest):
        # Debug: log all requests for troubleshooting
        user = getattr(request, 'user', None)
        if user and getattr(user, 'is_authenticated', False):
            session_key = request.session.session_key
            current_org = request.session.get("current_org")
            logger.info(f"TenantMiddleware - User: {user.username}, Session: {session_key}, CurrentOrg: {current_org}, Path: {request.path}")
        
        # Priority: query param > session
        slug = request.GET.get("org") or request.session.get("current_org")
        
        tenant: Optional[Organization] = None
        if slug:
            # Use default database to fetch organization
            tenant = Organization.objects.using('default').filter(slug=slug).first()
            if tenant:
                request.session["current_org"] = tenant.slug
        
        request.tenant = tenant
        
        # Set database for this request (for multi-database routing)
        if tenant:
            from core.db_router import set_tenant_db_for_request
            set_tenant_db_for_request(request)


class ForceLocaleMiddleware(MiddlewareMixin):
    """
    Force all requests to use Turkish locale.
    Redirect /en/ to /tr/ to prevent language-based session loss.
    """
    
    def process_request(self, request: HttpRequest):
        from django.shortcuts import redirect
        from django.utils import translation
        
        # Force Turkish locale
        translation.activate('tr')
        request.LANGUAGE_CODE = 'tr'
        
        # Redirect /en/ paths to /tr/
        if request.path.startswith('/en/'):
            new_path = '/tr/' + request.path[4:]
            return redirect(new_path)
        
        # If path doesn't start with /tr/ or /i18n/, redirect to /tr/
        if not request.path.startswith(('/tr/', '/i18n/', '/static/', '/media/')):
            return redirect('/tr' + request.path)
