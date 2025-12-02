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
