"""Subscribe new users to notifications by default."""

from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("users", "broadcast_subscribed", server_default=sa.true())


def downgrade():
    op.alter_column("users", "broadcast_subscribed", server_default=sa.false())
