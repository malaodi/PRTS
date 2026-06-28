from app.models.space import MemberRole

ROLE_PERMISSIONS: dict[MemberRole, set[str]] = {
    MemberRole.OWNER: {"*"},
    MemberRole.ADMIN: {
        "member:invite", "member:remove", "member:list",
        "role:member:modify", "role:viewer:modify",
        "agent:*", "asset:*",
        "space:settings:write",
        "model:config:*",
        "credential:team:*",
        "file:*",
        "session:*",
        "read:*",
    },
    MemberRole.MEMBER: {
        "agent:invoke", "agent:create", "agent:self:*",
        "asset:create", "asset:self:*",
        "market:install", "market:uninstall",
        "file:read", "file:write", "file:self:*",
        "agent:read",
        "credential:user:*",
        "session:self:*",
        "read:*",
    },
    MemberRole.VIEWER: {
        "read:*",
    },
}


def has_permission(role: MemberRole, permission: str) -> bool:
    if role == MemberRole.OWNER:
        return True

    role_perms = ROLE_PERMISSIONS.get(role, set())

    if "*" in role_perms:
        return True

    if permission in role_perms:
        return True

    for rp in role_perms:
        if rp.endswith(":*"):
            prefix = rp[:-2]
            if permission.startswith(prefix):
                return True

    return False


def require_role(required_roles: list[MemberRole], user_role: MemberRole) -> bool:
    return user_role in required_roles
