from __future__ import annotations

from app.auth.roles import UserRole

DEMO_USERS: dict[str, UserRole] = {
    "dr.mehta": UserRole.DOCTOR,
    "nurse.priya": UserRole.NURSE,
    "billing.ravi": UserRole.BILLING_EXECUTIVE,
    "tech.anand": UserRole.TECHNICIAN,
    "admin.sys": UserRole.ADMIN,
}
