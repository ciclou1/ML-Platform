"""model lineage fields

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "models",
        sa.Column("parent_model_id", UUID(as_uuid=True), sa.ForeignKey("models.id", ondelete="SET NULL")),
    )
    op.add_column(
        "models",
        sa.Column("model_task", sa.String(20), server_default="detect", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("models", "model_task")
    op.drop_column("models", "parent_model_id")
