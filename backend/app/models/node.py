from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Node(UUIDMixin, TimestampMixin, Base):
    """远程边缘节点：注册后由平台下发算法包并接收运行结果。"""

    __tablename__ = "nodes"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="offline")
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NodeDeployment(UUIDMixin, TimestampMixin, Base):
    """节点部署记录：某算法包版本部署到某节点。"""

    __tablename__ = "node_deployments"

    node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"))
    package_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("algorithm_package_versions.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(20), default="deployed")
    pending_params: Mapped[dict | None] = mapped_column(JSON)
    last_result: Mapped[dict | None] = mapped_column(JSON)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
