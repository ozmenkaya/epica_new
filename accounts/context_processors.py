from typing import Optional
from django.http import HttpRequest
from accounts.models import Membership, Organization


def tenant(request: HttpRequest):
    """
    Inject tenant organization and role flags into templates.
    Exposes:
      - tenant_org: Organization or None
      - tenant_membership: Membership or None
      - tenant_is_owner/admin/member: bool
      - tenant_role_key: optional custom role key (from Membership.role_fk)
      - tenant_permissions: list of permission keys for the current user
      - has_perm: function to check if user has a specific permission
    """
    # First try to get org from request (set by TenantMiddleware from subdomain)
    org = getattr(request, "tenant", None)
    
    # If not from subdomain, try to get from session
    if org is None:
        current_org_slug = request.session.get("current_org")
        if current_org_slug:
            org = Organization.objects.using('default').filter(slug=current_org_slug).first()
            # Set it on request for consistency
            if org:
                request.tenant = org
    
    mem: Optional[Membership] = None
    is_owner = is_admin = is_member = False
    role_key = None
    permissions = []

    user = getattr(request, "user", None)
    if org is not None and getattr(user, "is_authenticated", False):
        mem = Membership.objects.using('default').filter(user=user, organization=org).first()
        if mem:
            is_owner = mem.role == Membership.Role.OWNER
            is_admin = mem.role == Membership.Role.ADMIN or is_owner
            is_member = True
            permissions = mem.get_permissions()
            if mem.role_fk:
                role_key = mem.role_fk.key

    # Helper function to check permissions in templates
    def has_perm(perm_key):
        return perm_key in permissions

    return {
        "tenant_org": org,
        "tenant_membership": mem,
        "tenant_is_owner": is_owner,
        "tenant_is_admin": is_admin,
        "tenant_is_member": is_member,
        "tenant_role_key": role_key,
        "tenant_permissions": permissions,
        "has_perm": has_perm,
    }
