"""create payments and outbox tables

Revision ID: 0001
Revises:
Create Date: 2026-10-14

"""

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


def upgrade():
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.Enum("RUB", "USD", "EUR", name="payment_currency"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # ORM-атрибут называется meta: «metadata» зарезервировано SQLAlchemy Declarative
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "succeeded", "failed", name="payment_status"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_payments_status", "payments", ["status"])

    op.create_table(
        "outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_published_at", "outbox", ["published_at"])


def downgrade():
    op.drop_index("ix_outbox_published_at", table_name="outbox")
    op.drop_table("outbox")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_table("payments")
    op.execute("DROP TYPE payment_status")
    op.execute("DROP TYPE payment_currency")
