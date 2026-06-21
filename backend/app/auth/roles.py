from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    DOCTOR = "doctor"
    NURSE = "nurse"
    BILLING_EXECUTIVE = "billing_executive"
    TECHNICIAN = "technician"
    ADMIN = "admin"


ROLE_COLLECTIONS: dict[UserRole, list[str]] = {
    UserRole.DOCTOR: ["clinical", "nursing", "general"],
    UserRole.NURSE: ["nursing", "general"],
    UserRole.BILLING_EXECUTIVE: ["billing", "general"],
    UserRole.TECHNICIAN: ["equipment", "general"],
    UserRole.ADMIN: ["clinical", "nursing", "general", "billing", "equipment"],
}

SQL_ALLOWED_ROLES: set[UserRole] = {
    UserRole.BILLING_EXECUTIVE,
    UserRole.ADMIN,
}
