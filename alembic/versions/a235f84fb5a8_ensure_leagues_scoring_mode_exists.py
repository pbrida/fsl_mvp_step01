"""ensure leagues.scoring_mode exists"""

from alembic import op
import sqlalchemy as sa

# IDs
revision = "a235f84fb5a8"
down_revision = "ce17688f8283"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("leagues")}
    if "scoring_mode" not in cols:
        op.add_column(
            "leagues",
            sa.Column(
                "scoring_mode",
                sa.String(length=20),
                nullable=False,
                server_default="projections",
            ),
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("leagues")}
    if "scoring_mode" in cols:
        op.drop_column("leagues", "scoring_mode")
