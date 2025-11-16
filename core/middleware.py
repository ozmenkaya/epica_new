from typing import Optional
from django.http import HttpRequest
from django.utils.deprecation import MiddlewareMixin
from accounts.models import Organization, Membership


class TenantMiddleware(MiddlewareMixin):
    """
    Resolve current tenant from subdomain, ?org=<slug>, or session.
    Also sets the appropriate database for multi-tenant database isolation.
    
    Priority:
    1. Subdomain (helmex.epica.com.tr → 'helmex')
    2. Query parameter (?org=helmex)
    3. Session (stored from previous request)
    """

    def process_request(self, request: HttpRequest):
        # Extract subdomain from host
        host = request.get_host().split(':')[0]  # Remove port if present
        subdomain = self._extract_subdomain(host)
        
        # Priority: subdomain > query param > session
        slug = subdomain or request.GET.get("org") or request.session.get("current_org")
        
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
    
    def _extract_subdomain(self, host: str) -> Optional[str]:
        """
        Extract subdomain from host.
        
        Examples:
            helmex.epica.com.tr → 'helmex'
            acme.epica.com.tr → 'acme'
            epica.com.tr → None (main site)
            localhost → None
        """
        # List of main domains (no subdomain)
        main_domains = ['epica.com.tr', 'localhost', '127.0.0.1']
        
        # Check if it's a main domain
        if host in main_domains:
            return None
        
        # Split by dots
        parts = host.split('.')
        
        # If host is like helmex.epica.com.tr (4 parts)
        # or acme.epica.com.tr (4 parts)
        if len(parts) >= 3:
            # Check if it matches *.epica.com.tr pattern
            if '.'.join(parts[-3:]) == 'epica.com.tr':
                return parts[0]  # Return subdomain
        
        return None
