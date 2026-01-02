# Epica AI Coding Agent Instructions

## Architecture Overview

**Multi-tenant B2B procurement platform** with shared database + organization-based isolation. Each organization has separate data contexts but shares the same Django app and database.

### Key Components
- **accounts/**: Multi-tenant auth (Organization, Membership, custom permissions)
- **core/**: Business logic (Ticket, Quote, Supplier, Category, Customer)
- **billing/**: Orders and invoicing (Order, OrderItem)
- **ai_assistant/**: OpenAI GPT-4o-mini with function calling (9 business functions)

### Critical Middleware Flow
1. `TenantMiddleware` (core/middleware.py) - Resolves org from `?org=slug` or session
2. Sets `request.tenant` for all views
3. `ForceLocaleMiddleware` - Forces Turkish, redirects old `/tr/` `/en/` URLs

## Permission System (CRITICAL)

**Custom granular permissions** - NOT Django's default system.

### Template Checks (Always use these patterns):
```django
{% if 'customers_create' in tenant_permissions %}
  <a href="{% url 'customers_create' %}">New Customer</a>
{% endif %}
```

**NEVER** use `tenant_is_owner` or `tenant_is_admin` directly - use specific permission keys from `accounts/permissions_config.py`.

### View Decorators:
```python
from accounts.permissions import require_permission

@require_permission('customers_edit')
def customers_edit(request, pk):
    # Only users with 'customers_edit' permission can access
```

### Available Permissions (see `accounts/permissions_config.py`):
- `customers_list/create/edit/delete`
- `suppliers_list/create/edit/delete`
- `tickets_list/create`
- `orders_list/manage`
- `categories_list/manage`
- `products_list/manage`
- `dashboard`, `reports`, `settings`

## Database Architecture

### Multi-Database Setup
- **default**: Auth tables (User, Organization, Membership) - ALWAYS use `.using('default')`
- **tenant DBs**: Business data (Ticket, Quote, Order, etc.) - routed automatically by middleware

### Critical Pattern - Always specify database for auth queries:
```python
# ✅ CORRECT
org = Organization.objects.using('default').get(slug=slug)
membership = Membership.objects.using('default').filter(user=user, organization=org).first()

# ❌ WRONG - will use tenant DB and fail
org = Organization.objects.get(slug=slug)
```

### Business models (core/, billing/) use automatic routing - DON'T add `.using()`:
```python
# ✅ CORRECT
ticket = Ticket.objects.filter(organization=request.tenant).first()

# ❌ WRONG
ticket = Ticket.objects.using('default').filter(...)
```

## AI Assistant Integration

Located in `ai_assistant/services/`:
- `agent.py` - Main OpenAI chat loop with function calling
- `actions.py` - 9 business functions (search_tickets, get_ticket_stats, etc.)
- `retriever.py` - RAG context retrieval
- `embedder.py` - Text embeddings for semantic search

### Adding New AI Functions:
1. Add function definition in `agent.py` → `get_available_functions()`
2. Implement handler in `actions.py`
3. Function name must match exactly (snake_case)
4. Always return dict with `success`, `data`, and `message` keys

## VS Code Tasks (Use Command Palette)

- **"Deploy to Production"** - SSH deploy with service restart
- **"Run Tests"** - `python manage.py test`
- **"Make Migrations"** / **"Migrate Database"** - DB operations

## Template Patterns

### Context Variables (from `accounts/context_processors.py`):
- `tenant_org` - Current Organization
- `tenant_permissions` - List of permission keys for current user
- `tenant_is_owner/admin/member` - Role flags (avoid using directly)

### Common Template Pattern:
```django
{% extends "base.html" %}
{% load i18n %}

{% block content %}
<div class="card shadow-sm">
  <div class="card-header d-flex justify-content-between align-items-center">
    <h5>{{ org.name }} - {% trans "Title" %}</h5>
    {% if 'entity_create' in tenant_permissions %}
      <a class="btn btn-sm btn-primary" href="{% url 'entity_create' %}">New</a>
    {% endif %}
  </div>
  ...
</div>
{% endblock %}
```

## Deployment

**Production server:** `/opt/epica` on Hetzner (78.46.162.116)
- Service: `systemctl restart epica` (Gunicorn + systemd)
- Nginx proxies to port 8000
- Use VS Code "Deploy to Production" task

### Manual Deploy:
```bash
cd /opt/epica
git pull
source venv/bin/activate
python manage.py collectstatic --noinput
systemctl restart epica
```

## Testing

```bash
python manage.py test                    # All tests
python manage.py test ai_assistant       # Specific app
python manage.py test core.tests.test_permissions  # Specific module
```

## Common Pitfalls

1. **Using `.using('default')` on business models** - router handles it automatically
2. **Using role flags in templates** - use permission keys instead
3. **Forgetting `request.tenant`** - always filter by `organization=request.tenant`
4. **Not checking permissions** - always gate create/edit/delete actions
5. **Hardcoding URLs** - use `{% url 'view_name' %}` in templates

## Key Files Reference

- `accounts/permissions_config.py` - All permission definitions
- `accounts/context_processors.py` - Template context injection
- `core/middleware.py` - Tenant resolution logic
- `epica/settings.py` - Multi-database config (lines 200-250)
- `ai_assistant/services/actions.py` - AI function implementations
