"""initial schema

Revision ID: 20261011_0001
Revises:
Create Date: 2026-10-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261011_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "call_sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("business_id", sa.String(length=64), nullable=False),
        sa.Column("room_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("caller_number_redacted", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_call_sessions_business_id", "call_sessions", ["business_id"])

    op.create_table(
        "bookings",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("business_id", sa.String(length=64), nullable=False),
        sa.Column("service_id", sa.String(length=64), nullable=False),
        sa.Column("customer_name", sa.String(length=120), nullable=False),
        sa.Column("customer_phone_redacted", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="confirmed"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_booking_idempotency"),
    )
    op.create_index("ix_bookings_business_id", "bookings", ["business_id"])
    op.create_index("ix_booking_business_start", "bookings", ["business_id", "starts_at"])


def downgrade() -> None:
    op.drop_index("ix_booking_business_start", table_name="bookings")
    op.drop_index("ix_bookings_business_id", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index("ix_call_sessions_business_id", table_name="call_sessions")
    op.drop_table("call_sessions")
