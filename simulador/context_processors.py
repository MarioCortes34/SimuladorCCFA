from .models import Tenant


def tenant_context(request):
    tenants = list(Tenant.objects.order_by('nombre'))
    if not tenants:
        return {}
    tid = request.session.get('tenant_id')
    tenant = next((t for t in tenants if t.id == tid), tenants[0])
    return {'tenant': tenant, 'tenants': tenants}
