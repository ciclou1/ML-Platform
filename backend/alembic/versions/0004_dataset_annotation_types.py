"""dataset category and annotation types

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("scene_category", sa.String(50)))
    op.add_column("datasets", sa.Column("annotation_types", JSON))
    op.add_column("labels", sa.Column("skeleton", JSON))


def downgrade() -> None:
    op.drop_column("labels", "skeleton")
    op.drop_column("datasets", "annotation_types")
    op.drop_column("datasets", "scene_category")
