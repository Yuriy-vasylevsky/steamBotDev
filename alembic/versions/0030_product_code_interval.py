"""Add the availability window for additional code deliveries.

Revision ID: 0030
Revises: 0029
"""

import sqlalchemy as sa

from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "products",
        sa.Column("code_window_hours", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_products_code_window_hours",
        "products",
        "code_window_hours BETWEEN 0 AND 1000",
    )


def downgrade():
    op.drop_constraint("ck_products_code_window_hours", "products", type_="check")
    op.drop_column("products", "code_window_hours")
