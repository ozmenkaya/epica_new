"""
Multi-tenant database router for subdomain-based database isolation.

Each organization gets its own database:
- helmex.epica.com.tr → epica_helmex
- acme.epica.com.tr → epica_acme
- Default fallback → epica_default (or 'default')

Usage:
    - Add to settings.py: DATABASE_ROUTERS = ['core.db_router.TenantDatabaseRouter']
    - Configure databases in settings.py based on subdomain
"""

import threading
from django.conf import settings


# Thread-local storage for current tenant database
_thread_local = threading.local()


class TenantDatabaseRouter:
    """
    Route database operations based on current tenant (organization).
    
    The tenant is determined by:
    1. Subdomain (helmex.epica.com.tr → 'helmex')
    2. Query parameter (?org=helmex → 'helmex')
    3. Session (stored by TenantMiddleware)
    
    Each tenant gets its own database with naming convention:
    - Database name: epica_{org_slug}
    - Example: Organization(slug='helmex') → database 'epica_helmex'
    """
    
    def get_tenant_db(self):
        """Get current tenant's database alias."""
        return getattr(_thread_local, 'db_alias', 'default')
    
    def set_tenant_db(self, db_alias):
        """Set current tenant's database alias."""
        _thread_local.db_alias = db_alias
    
    def db_for_read(self, model, **hints):
        """
        Route read operations to tenant database.
        """
        # Auth models always go to default database
        if model._meta.app_label == 'auth':
            return 'default'
        
        return self.get_tenant_db()
    
    def db_for_write(self, model, **hints):
        """
        Route write operations to tenant database.
        """
        # Auth models always go to default database
        if model._meta.app_label == 'auth':
            return 'default'
        
        return self.get_tenant_db()
    
    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between objects in the same database.
        """
        db1 = obj1._state.db or self.get_tenant_db()
        db2 = obj2._state.db or self.get_tenant_db()
        return db1 == db2
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Allow migrations to run on all databases.
        
        Auth models only migrate to default database.
        All other models migrate to all databases.
        """
        if app_label == 'auth':
            return db == 'default'
        
        # Allow migrations for all tenant databases
        return True


def set_tenant_db_for_request(request):
    """
    Helper function to set tenant database based on request.
    Should be called from middleware.
    
    Example:
        from core.db_router import set_tenant_db_for_request
        set_tenant_db_for_request(request)
    """
    from core.db_router import TenantDatabaseRouter
    
    router = TenantDatabaseRouter()
    
    # Get tenant from request (set by TenantMiddleware)
    tenant = getattr(request, 'tenant', None)
    
    if tenant:
        db_alias = f'tenant_{tenant.slug}'
        
        # Check if database is configured
        if db_alias in settings.DATABASES:
            router.set_tenant_db(db_alias)
        else:
            # Fallback to default if tenant DB not configured
            router.set_tenant_db('default')
    else:
        router.set_tenant_db('default')
