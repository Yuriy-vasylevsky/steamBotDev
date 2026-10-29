"""Preserve encrypted account credentials for each purchase."""

import sqlalchemy as sa

from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade():
    for field in ("steam_login_encrypted", "steam_password_encrypted"):
        op.add_column("orders", sa.Column(field, sa.Text(), nullable=True))
        op.execute(sa.text(
            f"UPDATE orders SET {field} = "
            f"(SELECT products.{field} FROM products WHERE products.id = orders.product_id)"
        ))


def downgrade():
    op.drop_column("orders", "steam_password_encrypted")
    op.drop_column("orders", "steam_login_encrypted")
