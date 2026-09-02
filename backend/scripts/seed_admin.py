"""Seed builtin roles and the admin user. Idempotent; run after migrations.

Usage::

    uv run python scripts/seed_admin.py

默认管理员账号 admin / admin123，首次登录后请修改密码。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 允许按文档命令直接运行：uv run python scripts/seed_admin.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password  # noqa: E402
from app.db.postgres import async_session_factory  # noqa: E402
from app.models.user import Role, User  # noqa: E402
from app.repositories.user import RoleRepository, UserRepository  # noqa: E402

READ_PERMISSIONS = [
    "dataset:read",
    "annotation:read",
    "model:read",
]
OPERATOR_PERMISSIONS = READ_PERMISSIONS + [
    "dataset:write",
    "annotation:write",
    "model:write",
    "task:run",
    "node:manage",
]

BUILTIN_ROLES = (
    ("admin", "管理员，拥有全部权限", ["*"]),
    ("operator", "操作员，可管理数据/标注/模型并运行任务", OPERATOR_PERMISSIONS),
    ("viewer", "只读角色，仅可查看数据与结果", READ_PERMISSIONS),
)

ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


async def seed() -> None:
    async with async_session_factory() as session:
        role_repo = RoleRepository(session)
        user_repo = UserRepository(session)

        roles: dict[str, Role] = {}
        for name, description, permissions in BUILTIN_ROLES:
            role = await role_repo.get_by_name(name)
            if role is None:
                role = await role_repo.create(
                    Role(
                        name=name,
                        description=description,
                        permissions=permissions,
                        is_builtin=True,
                    )
                )
                print(f"[seed-admin] created role: {name}")
            roles[name] = role

        if await user_repo.get_by_username(ADMIN_USERNAME) is None:
            await user_repo.create(
                User(
                    username=ADMIN_USERNAME,
                    password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                    display_name="管理员",
                    role_id=roles["admin"].id,
                )
            )
            print(
                f"[seed-admin] created admin user: {ADMIN_USERNAME} / "
                f"{DEFAULT_ADMIN_PASSWORD}（请尽快修改密码）"
            )
        else:
            print("[seed-admin] admin user already exists, skipped")
        await session.commit()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed())
