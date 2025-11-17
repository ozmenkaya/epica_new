from typing import Optional
from django.http import HttpRequest
from accounts.models import Membership


def tenant(request: HttpRequest):
    """
    Inject tenant organization and role flags into templates.
    Exposes:
      - tenant_org: Organization or None
      - tenant_membership: Membership or None
      - tenant_is_owner/admin/member: bool
      - tenant_role_key: optional custom role key (from Membership.role_fk)
    """
    org = getattr(request, "tenant", None)
    mem: Optional[Membership] = None
    is_owner = is_admin = is_member = False
    role_key = None

    user = getattr(request, "user", None)
    if org is not None and getattr(user, "is_authenticated", False):
        mem = Membership.objects.using('default').filter(user=user, organization=org).first()
        if mem:
            is_owner = mem.role == Membership.Role.OWNER
            is_admin = mem.role == Membership.Role.ADMIN or is_owner
            is_member = True
            if mem.role_fk:
                role_key = mem.role_fk.key

    return {
        "tenant_org": org,
        "tenant_membership": mem,
        "tenant_is_owner": is_owner,
        "tenant_is_admin": is_admin,
        "tenant_is_member": is_member,
        "tenant_role_key": role_key,
    }
