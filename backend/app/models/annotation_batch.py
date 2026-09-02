from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class AnnotationBatch(UUIDMixin, TimestampMixin, Base):
    """A reviewable slice of images assigned to an annotation workflow."""

    __tablename__ = "annotation_batches"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    dataset: Mapped[Dataset] = relationship()  # noqa: F821
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_user_id])  # noqa: F821
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])  # noqa: F821
    items: Mapped[list[AnnotationBatchItem]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="AnnotationBatchItem.created_at",
    )


class AnnotationBatchItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "annotation_batch_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "image_id", name="uq_annotation_batch_item_image"),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("annotation_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"), nullable=False, index=True
    )
    annotator_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)

    batch: Mapped[AnnotationBatch] = relationship(back_populates="items")
    image: Mapped[Image] = relationship()  # noqa: F821
    annotator: Mapped[User | None] = relationship(foreign_keys=[annotator_user_id])  # noqa: F821
    reviews: Mapped[list[AnnotationReview]] = relationship(
        back_populates="batch_item",
        cascade="all, delete-orphan",
        order_by="AnnotationReview.created_at",
    )


class AnnotationReview(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "annotation_reviews"

    batch_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("annotation_batch_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"), nullable=False, index=True
    )
    annotator_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    quality_score: Mapped[float | None] = mapped_column(Float)
    comment: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    batch_item: Mapped[AnnotationBatchItem] = relationship(back_populates="reviews")
    image: Mapped[Image] = relationship()  # noqa: F821
    annotator: Mapped[User | None] = relationship(foreign_keys=[annotator_user_id])  # noqa: F821
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewer_user_id])  # noqa: F821
