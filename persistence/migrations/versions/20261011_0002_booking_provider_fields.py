"""booking provider_kind and duration_minutes

Revision ID: 20261011_0002
Revises: 20261011_0001
Create Date: 2026-10-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261011_0002"
down_revision: Union[str, None] = "20261011_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.add_column(
            sa.Column("duration_minutes", sa.Integer(), server_default="30", nullable=False)
        )
        batch_op.add_column(
            sa.Column("provider_kind", sa.String(length=16), server_default="mock", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.drop_column("provider_kind")
        batch_op.drop_column("duration_minutes")
