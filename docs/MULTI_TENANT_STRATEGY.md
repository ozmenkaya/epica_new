# Multi-Tenant Deployment Strategy

## Current Architecture
- **Type**: Shared Database Multi-Tenancy
- **Isolation Level**: Organization-based (Django middleware)
- **Server**: Single Hetzner VPS (2 CPU, 3.7GB RAM)
- **Capacity**: ~50-100 concurrent users

## Strategy: Tiered Approach

### Tier 1: Shared Hosting (Default)
**Target**: Small to medium customers (< 20 users, < 1000 orders/month)

**Infrastructure**:
- Domain: `{customer}.epica.com.tr` or `epica.com.tr/{customer}`
- Server: Shared VPS
- Database: Shared PostgreSQL with organization-based isolation
- Cost: Low (€20-50/month for all customers)

**Resource Limits**:
```python
# settings.py
TENANT_RESOURCE_LIMITS = {
    'max_users': 20,
    'max_storage_mb': 1000,
    'max_api_calls_per_hour': 1000,
}
```

**Pros**:
- Low operational cost
- Easy updates (one deployment)
- Fast customer onboarding
- Centralized monitoring

**Cons**:
- Shared resources
- No custom configuration
- Downtime affects all customers

---

### Tier 2: Dedicated Servers (Premium)
**Target**: Large customers (> 50 users, > 5000 orders/month, compliance needs)

**Infrastructure**:
- Domain: `{customer}.epica.com.tr` (dedicated IP)
- Server: Dedicated Hetzner VPS per customer
- Database: Isolated PostgreSQL instance
- Cost: Medium (€40-100/month per customer)

**Setup**:
```bash
# Automated provisioning script
./deploy/provision_dedicated.sh \
  --customer helmex \
  --server-size cx21 \
  --domain helmex.epica.com.tr
```

**Pros**:
- Full isolation (security + compliance)
- Custom configuration per customer
- Independent scaling
- SLA guarantees

**Cons**:
- Higher infrastructure cost
- Update complexity (need orchestration)
- More maintenance overhead

---

## Update Management

### Shared Hosting Updates
```bash
# Single deployment updates all customers
cd /opt/epica
git pull origin main
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
systemctl restart epica

# Zero-downtime deployment (future):
# - Blue-green deployment
# - Database migrations run before code deploy
# - Health checks before switching traffic
```

### Dedicated Server Updates
```bash
# Central orchestration script
./deploy/update_all_customers.sh

# What it does:
# 1. Pull latest code on each server
# 2. Run migrations (if needed)
# 3. Restart services one by one
# 4. Health check after each restart
# 5. Rollback if errors detected
```

**Orchestration Tool Options**:
- **Ansible**: Simple, SSH-based (Recommended for your scale)
- **Terraform**: Infrastructure provisioning
- **Custom bash scripts**: Works for 5-10 customers

---

## Implementation Phases

### Phase 1: Optimize Current Shared Setup (Week 1-2)
- [ ] Add subdomain routing in nginx
- [ ] Implement rate limiting per organization
- [ ] Add resource usage monitoring (CPU/memory per org)
- [ ] Setup organization-based backup/restore
- [ ] Create admin dashboard for resource monitoring

### Phase 2: Prepare for Dedicated Deployments (Week 3-4)
- [ ] Create provisioning scripts (Ansible)
- [ ] Setup central monitoring (Prometheus + Grafana)
- [ ] Build automated deployment pipeline
- [ ] Document server setup process
- [ ] Create customer migration script (shared → dedicated)

### Phase 3: Hybrid Operation (Week 5+)
- [ ] Move first premium customer to dedicated server
- [ ] Test update orchestration
- [ ] Monitor both tiers
- [ ] Refine based on experience

---

## Technical Implementation

### 1. Subdomain Routing (Nginx)
```nginx
# /etc/nginx/sites-available/epica-multi-tenant

# Shared hosting - wildcard subdomain
server {
    listen 80;
    server_name *.epica.com.tr;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Main domain
server {
    listen 80;
    server_name epica.com.tr;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
```

### 2. Organization Detection Middleware
```python
# core/middleware.py (already exists, enhance it)

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Extract subdomain
        host = request.get_host()
        subdomain = self.extract_subdomain(host)
        
        if subdomain:
            # Find organization by subdomain
            try:
                org = Organization.objects.get(slug=subdomain)
                request.tenant = org
            except Organization.DoesNotExist:
                # Redirect to main site or 404
                pass
        
        # Track resource usage
        self.track_resource_usage(request)
        
        response = self.get_response(request)
        return response
    
    def track_resource_usage(self, request):
        """Track API calls, DB queries, etc per organization"""
        if hasattr(request, 'tenant'):
            # Increment counter in Redis/Cache
            cache_key = f"org:{request.tenant.id}:api_calls:{hour}"
            cache.incr(cache_key)
```

### 3. Resource Monitoring
```python
# core/management/commands/monitor_resources.py

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from core.models import Organization, Order, Ticket

class Command(BaseCommand):
    help = 'Monitor resource usage per organization'
    
    def handle(self, *args, **options):
        for org in Organization.objects.all():
            stats = {
                'users': org.memberships.count(),
                'orders': Order.objects.filter(organization=org).count(),
                'tickets': Ticket.objects.filter(organization=org).count(),
                'storage_mb': self.calculate_storage(org),
            }
            
            # Check limits
            if stats['users'] > TIER_LIMITS[org.tier]['max_users']:
                self.stdout.write(
                    self.style.WARNING(
                        f"{org.name} exceeded user limit"
                    )
                )
            
            # Log to monitoring system
            self.log_metrics(org, stats)
```

### 4. Automated Provisioning (Ansible)
```yaml
# deploy/ansible/provision_customer.yml

---
- name: Provision dedicated Epica server for customer
  hosts: localhost
  gather_facts: no
  
  vars:
    customer_name: "{{ customer }}"
    server_size: "cx21"  # Hetzner server type
    domain: "{{ customer }}.epica.com.tr"
  
  tasks:
    - name: Create Hetzner server
      hcloud_server:
        name: "epica-{{ customer_name }}"
        server_type: "{{ server_size }}"
        image: ubuntu-22.04
        location: fsn1
        ssh_keys:
          - epica-deploy
        state: present
      register: server
    
    - name: Wait for SSH
      wait_for:
        host: "{{ server.hcloud_server.ipv4_address }}"
        port: 22
        timeout: 300
    
    - name: Setup DNS
      cloudflare_dns:
        domain: epica.com.tr
        record: "{{ customer_name }}"
        type: A
        value: "{{ server.hcloud_server.ipv4_address }}"
    
    - name: Run setup script
      shell: |
        scp -r /opt/epica root@{{ server.hcloud_server.ipv4_address }}:/opt/
        ssh root@{{ server.hcloud_server.ipv4_address }} 'cd /opt/epica/deploy && ./setup_hetzner.sh'
```

### 5. Update Orchestration Script
```bash
#!/bin/bash
# deploy/update_all_customers.sh

CUSTOMERS_FILE="deploy/customers.txt"
LOG_DIR="deploy/logs"
ROLLBACK_ON_ERROR=true

echo "Starting deployment to all customer servers..."
echo "Date: $(date)"

# Read customer list
while IFS=',' read -r customer_name server_ip; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Deploying to: $customer_name ($server_ip)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Deploy
    ssh root@$server_ip 'cd /opt/epica && \
        git fetch origin && \
        git checkout main && \
        git pull && \
        source venv/bin/activate && \
        python manage.py migrate && \
        python manage.py collectstatic --noinput && \
        systemctl restart epica'
    
    # Health check
    sleep 5
    health_status=$(curl -s -o /dev/null -w "%{http_code}" http://$server_ip/health/)
    
    if [ $health_status -ne 200 ]; then
        echo "❌ Health check failed for $customer_name"
        
        if [ "$ROLLBACK_ON_ERROR" = true ]; then
            echo "Rolling back..."
            ssh root@$server_ip 'cd /opt/epica && \
                git checkout HEAD~1 && \
                systemctl restart epica'
        fi
        
        # Send alert
        curl -X POST "https://slack.com/api/chat.postMessage" \
            -H "Authorization: Bearer $SLACK_TOKEN" \
            -d "text=Deployment failed for $customer_name"
        
        exit 1
    fi
    
    echo "✅ Deployment successful for $customer_name"
    
done < "$CUSTOMERS_FILE"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "All deployments completed successfully!"
```

### 6. Central Monitoring Dashboard
```python
# admin_dashboard/views.py

def multi_tenant_dashboard(request):
    """Central monitoring for all customers"""
    
    customers = []
    
    # Shared hosting customers
    shared_orgs = Organization.objects.filter(hosting_tier='shared')
    for org in shared_orgs:
        customers.append({
            'name': org.name,
            'tier': 'Shared',
            'status': 'online',  # Check health endpoint
            'users': org.memberships.count(),
            'cpu_usage': get_org_cpu_usage(org),
            'memory_usage': get_org_memory_usage(org),
            'last_update': get_last_deploy_time(),
        })
    
    # Dedicated hosting customers
    dedicated_orgs = Organization.objects.filter(hosting_tier='dedicated')
    for org in dedicated_orgs:
        server_ip = org.dedicated_server_ip
        customers.append({
            'name': org.name,
            'tier': 'Dedicated',
            'status': check_server_health(server_ip),
            'users': org.memberships.count(),
            'cpu_usage': get_server_cpu(server_ip),
            'memory_usage': get_server_memory(server_ip),
            'last_update': get_server_deploy_time(server_ip),
        })
    
    return render(request, 'admin_dashboard/multi_tenant.html', {
        'customers': customers,
        'total_customers': len(customers),
        'shared_count': shared_orgs.count(),
        'dedicated_count': dedicated_orgs.count(),
    })
```

---

## Cost Analysis

### Shared Hosting (Current)
- **Server**: €20/month (Hetzner CX11)
- **Backup**: €5/month
- **Domain**: €10/year
- **Total**: €25/month for ALL customers
- **Per customer cost**: €25 / N customers

### Dedicated Hosting
- **Server**: €40-100/month per customer (Hetzner CX21-CX31)
- **Backup**: €5/month per customer
- **Monitoring**: €10/month (shared cost)
- **Total**: €45-105/month per customer

### Break-even Analysis
- **Shared**: Good for 5-20 customers (€1-5 per customer)
- **Dedicated**: Needed when:
  - Customer has > 50 users
  - Compliance requirements (data isolation)
  - High traffic (> 100k requests/day)
  - Custom configuration needs

---

## Decision Matrix

| Criteria | Shared | Dedicated |
|----------|--------|-----------|
| **Cost** | ★★★★★ | ★★☆☆☆ |
| **Isolation** | ★★☆☆☆ | ★★★★★ |
| **Updates** | ★★★★★ | ★★☆☆☆ |
| **Customization** | ★☆☆☆☆ | ★★★★★ |
| **Scaling** | ★★☆☆☆ | ★★★★☆ |
| **Compliance** | ★★☆☆☆ | ★★★★★ |

---

## Recommendation

### Start with Shared Hosting
- First 5-10 customers → Shared hosting
- Low risk, low cost, easy to manage
- Focus on product development, not infrastructure

### Transition to Hybrid
- When revenue allows (> €1000/month)
- When you get first enterprise customer
- When compliance becomes requirement

### Long-term (2+ years)
- Consider Kubernetes if > 50 customers
- Or managed PaaS (Heroku, Railway, Fly.io)
- Focus on business, not server management

---

## Next Steps

1. **Implement subdomain routing** (1-2 days)
2. **Add resource monitoring** (2-3 days)
3. **Create provisioning scripts** (3-5 days)
4. **Test with pilot customer** (1 week)
5. **Document runbooks** (ongoing)

Would you like me to implement any of these components?
