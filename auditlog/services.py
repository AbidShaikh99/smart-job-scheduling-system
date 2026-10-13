
from auditlog.models import AuditLog


def record_audit(
    *,
    action,
    target,
    description,
    performed_by=None,
    changes=None,
    ip_address=None,
):
    return AuditLog.objects.create(
        performed_by=performed_by,
        action=action,
        target_model=target.__class__.__name__,
        target_id=str(target.pk),
        description=description,
        changes=changes or {},
        ip_address=ip_address,
    )
