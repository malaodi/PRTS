import os
from app.core.security import get_password_hash
from app.database import Base, engine, async_session_factory
from app.models import User, Space, SpaceMember
from app.models.space import MemberRole, SpaceType
import asyncio
from sqlalchemy import text


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Phase 7 asset migration: add visibility/published columns if not exists
        columns_to_add = [
            ("visibility", "VARCHAR(20) DEFAULT 'private' NOT NULL"),
            ("tags", "TEXT"),
            ("published_version", "VARCHAR(50)"),
            ("published_at", "TIMESTAMPTZ"),
        ]
        for col_name, col_def in columns_to_add:
            try:
                await conn.execute(text(
                    f"ALTER TABLE assets ADD COLUMN IF NOT EXISTS {col_name} {col_def}"
                ))
            except Exception:
                pass

        try:
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_assets_visibility ON assets (visibility)"
            ))
        except Exception:
            pass

    async with async_session_factory() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none() is not None:
            return

        admin_email = os.getenv("ADMIN_EMAIL", "admin@prts.local")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
        admin = User(
            email=admin_email,
            username="admin",
            hashed_password=get_password_hash(admin_password),
            display_name="PRTS Admin",
        )
        session.add(admin)
        await session.flush()

        demo_space = Space(
            name="Demo Team",
            type=SpaceType.TEAM,
            owner_id=admin.id,
            team_context="这是一个演示团队空间。请在此配置您的团队信息、规范和目标。",
        )
        session.add(demo_space)
        await session.flush()

        demo_member = SpaceMember(
            space_id=demo_space.id,
            user_id=admin.id,
            role=MemberRole.OWNER,
        )
        session.add(demo_member)

        personal_space = Space(
            name=f"{admin.display_name} 的空间",
            type=SpaceType.PERSONAL,
            owner_id=admin.id,
        )
        session.add(personal_space)
        await session.flush()

        personal_member = SpaceMember(
            space_id=personal_space.id,
            user_id=admin.id,
            role=MemberRole.OWNER,
        )
        session.add(personal_member)

        await session.commit()
        print("Database initialized with default admin user and demo spaces.")


if __name__ == "__main__":
    asyncio.run(init_db())
