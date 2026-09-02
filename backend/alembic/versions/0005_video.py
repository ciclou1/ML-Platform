"""video samples and frame linkage

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dataset_id",
            UUID(as_uuid=True),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("fps", sa.Float()),
        sa.Column("duration_s", sa.Float()),
        sa.Column("frame_count", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(20), server_default="uploaded"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column(
        "images",
        sa.Column(
            "video_id",
            UUID(as_uuid=True),
            sa.ForeignKey("videos.id", ondelete="SET NULL"),
        ),
    )
    op.add_column("images", sa.Column("frame_index", sa.Integer()))


def downgrade() -> None:
    op.drop_column("images", "frame_index")
    op.drop_column("images", "video_id")
    op.drop_table("videos")
