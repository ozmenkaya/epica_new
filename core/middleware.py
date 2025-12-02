from typing import Optional
from django.http import HttpRequest, HttpResponsePermanentRedirect
from django.utils.deprecation import MiddlewareMixin
from django.utils import translation
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
    Redirect old /tr/ and /en/ URLs to root paths (for bookmarks/old links).
    """
    
    def process_request(self, request: HttpRequest):
        # Always activate Turkish locale (no redirect, just set language)
        translation.activate('tr')
        request.LANGUAGE_CODE = 'tr'
        
        # Only redirect if path explicitly starts with /tr/ or /en/
        # This handles old bookmarks and links
        if request.path.startswith('/tr/'):
            new_path = request.path[3:]  # Remove /tr prefix
            if not new_path:  # If it was just /tr/, redirect to /
                new_path = '/'
            return HttpResponsePermanentRedirect(new_path)
        
        if request.path.startswith('/en/'):
            new_path = request.path[3:]  # Remove /en prefix
            if not new_path:  # If it was just /en/, redirect to /
                new_path = '/'
            return HttpResponsePermanentRedirect(new_path)
        
        # No redirect for normal paths - just set language
        return None
