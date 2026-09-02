"""annotation batches and quality reviews

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "annotation_batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dataset_id",
            UUID(as_uuid=True),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column(
            "assignee_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column(
            "created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_annotation_batches_dataset_id", "annotation_batches", ["dataset_id"])
    op.create_index("ix_annotation_batches_status", "annotation_batches", ["status"])
    op.create_index(
        "ix_annotation_batches_assignee_user_id", "annotation_batches", ["assignee_user_id"]
    )
    op.create_index(
        "ix_annotation_batches_created_by_user_id", "annotation_batches", ["created_by_user_id"]
    )

    op.create_table(
        "annotation_batch_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("annotation_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "image_id",
            UUID(as_uuid=True),
            sa.ForeignKey("images.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "annotator_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("batch_id", "image_id", name="uq_annotation_batch_item_image"),
    )
    op.create_index("ix_annotation_batch_items_batch_id", "annotation_batch_items", ["batch_id"])
    op.create_index("ix_annotation_batch_items_image_id", "annotation_batch_items", ["image_id"])
    op.create_index(
        "ix_annotation_batch_items_annotator_user_id",
        "annotation_batch_items",
        ["annotator_user_id"],
    )
    op.create_index("ix_annotation_batch_items_status", "annotation_batch_items", ["status"])

    op.create_table(
        "annotation_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("annotation_batch_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "image_id",
            UUID(as_uuid=True),
            sa.ForeignKey("images.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "annotator_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column(
            "reviewer_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("quality_score", sa.Float()),
        sa.Column("comment", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_annotation_reviews_batch_item_id", "annotation_reviews", ["batch_item_id"])
    op.create_index("ix_annotation_reviews_image_id", "annotation_reviews", ["image_id"])
    op.create_index(
        "ix_annotation_reviews_annotator_user_id", "annotation_reviews", ["annotator_user_id"]
    )
    op.create_index(
        "ix_annotation_reviews_reviewer_user_id", "annotation_reviews", ["reviewer_user_id"]
    )
    op.create_index("ix_annotation_reviews_status", "annotation_reviews", ["status"])


def downgrade() -> None:
    for index_name, table_name in (
        ("ix_annotation_reviews_status", "annotation_reviews"),
        ("ix_annotation_reviews_reviewer_user_id", "annotation_reviews"),
        ("ix_annotation_reviews_annotator_user_id", "annotation_reviews"),
        ("ix_annotation_reviews_image_id", "annotation_reviews"),
        ("ix_annotation_reviews_batch_item_id", "annotation_reviews"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("annotation_reviews")

    for index_name, table_name in (
        ("ix_annotation_batch_items_status", "annotation_batch_items"),
        ("ix_annotation_batch_items_annotator_user_id", "annotation_batch_items"),
        ("ix_annotation_batch_items_image_id", "annotation_batch_items"),
        ("ix_annotation_batch_items_batch_id", "annotation_batch_items"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("annotation_batch_items")

    for index_name in (
        "ix_annotation_batches_created_by_user_id",
        "ix_annotation_batches_assignee_user_id",
        "ix_annotation_batches_status",
        "ix_annotation_batches_dataset_id",
    ):
        op.drop_index(index_name, table_name="annotation_batches")
    op.drop_table("annotation_batches")
