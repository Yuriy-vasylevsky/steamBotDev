"""Persist the start of receipt manual review."""
import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payment_receipts", sa.Column("manual_review_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE payment_receipts SET manual_review_at = CURRENT_TIMESTAMP WHERE status IN ('manual_review', 'retry_allowed_review')")


def downgrade():
    op.drop_column("payment_receipts", "manual_review_at")
