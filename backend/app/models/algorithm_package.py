from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class AlgorithmPackage(UUIDMixin, TimestampMixin, Base):
    """算法包：用户自研算法的载体，含一个或多个版本。"""

    __tablename__ = "algorithm_packages"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    framework: Mapped[str] = mapped_column(String(50), default="custom")
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")


class AlgorithmPackageVersion(UUIDMixin, TimestampMixin, Base):
    """算法包版本：manifest + 推理代码 + 权重。"""

    __tablename__ = "algorithm_package_versions"

    package_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("algorithm_packages.id", ondelete="CASCADE")
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    entrypoint: Mapped[str] = mapped_column(String(255), nullable=False)
    runtime_config: Mapped[dict | None] = mapped_column(JSON)
    weights_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="draft")
