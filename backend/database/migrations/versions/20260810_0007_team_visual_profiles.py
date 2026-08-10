"""Add team visual profiles.

Revision ID: 20260810_0007
Revises: 20260806_0006
Create Date: 2026-08-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260810_0007"
down_revision = "20260806_0006"
branch_labels = None
depends_on = None


VISUAL_ROWS = [
    {"provider_team_id": 10, "primary_colour": "#CE1124", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 33, "primary_colour": "#DA291C", "secondary_colour": "#FBE122"},
    {"provider_team_id": 34, "primary_colour": "#241F20", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 35, "primary_colour": "#DA291C", "secondary_colour": "#000000"},
    {"provider_team_id": 36, "primary_colour": "#FFFFFF", "secondary_colour": "#000000"},
    {"provider_team_id": 39, "primary_colour": "#FDB913", "secondary_colour": "#231F20"},
    {"provider_team_id": 40, "primary_colour": "#C8102E", "secondary_colour": "#00B2A9"},
    {"provider_team_id": 41, "primary_colour": "#D71920", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 42, "primary_colour": "#EF0107", "secondary_colour": "#063672"},
    {"provider_team_id": 45, "primary_colour": "#003399", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 46, "primary_colour": "#003090", "secondary_colour": "#FDBE11"},
    {"provider_team_id": 47, "primary_colour": "#132257", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 48, "primary_colour": "#7A263A", "secondary_colour": "#1BB1E7"},
    {"provider_team_id": 49, "primary_colour": "#034694", "secondary_colour": "#D1D3D4"},
    {"provider_team_id": 50, "primary_colour": "#6CABDD", "secondary_colour": "#1C2C5B"},
    {"provider_team_id": 51, "primary_colour": "#0057B8", "secondary_colour": "#FFCD00"},
    {"provider_team_id": 52, "primary_colour": "#1B458F", "secondary_colour": "#C4122E"},
    {"provider_team_id": 55, "primary_colour": "#E30613", "secondary_colour": "#FBB800"},
    {"provider_team_id": 63, "primary_colour": "#FFCD00", "secondary_colour": "#1D428A"},
    {"provider_team_id": 65, "primary_colour": "#DD0000", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 66, "primary_colour": "#95BFE5", "secondary_colour": "#670E36"},
    {"provider_team_id": 79, "primary_colour": "#E01E3C", "secondary_colour": "#1D3C89"},
    {"provider_team_id": 80, "primary_colour": "#DA001A", "secondary_colour": "#003A70"},
    {"provider_team_id": 81, "primary_colour": "#00A3E0", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 85, "primary_colour": "#004170", "secondary_colour": "#DA291C"},
    {"provider_team_id": 91, "primary_colour": "#E30613", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 157, "primary_colour": "#DC052D", "secondary_colour": "#0066B2"},
    {"provider_team_id": 165, "primary_colour": "#FDE100", "secondary_colour": "#000000"},
    {"provider_team_id": 168, "primary_colour": "#E32221", "secondary_colour": "#000000"},
    {"provider_team_id": 173, "primary_colour": "#DD0741", "secondary_colour": "#001F5B"},
    {"provider_team_id": 194, "primary_colour": "#D2122E", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 197, "primary_colour": "#FF0000", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 209, "primary_colour": "#D71920", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 211, "primary_colour": "#E83030", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 212, "primary_colour": "#00428C", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 228, "primary_colour": "#00843D", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 487, "primary_colour": "#87D8F7", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 489, "primary_colour": "#FB090B", "secondary_colour": "#000000"},
    {"provider_team_id": 492, "primary_colour": "#12A0D7", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 496, "primary_colour": "#FFFFFF", "secondary_colour": "#000000"},
    {"provider_team_id": 497, "primary_colour": "#8E1F2F", "secondary_colour": "#F0BC42"},
    {"provider_team_id": 499, "primary_colour": "#1D71B8", "secondary_colour": "#000000"},
    {"provider_team_id": 502, "primary_colour": "#5B2A86", "secondary_colour": "#D71920"},
    {"provider_team_id": 505, "primary_colour": "#0057A8", "secondary_colour": "#000000"},
    {"provider_team_id": 529, "primary_colour": "#A50044", "secondary_colour": "#004D98"},
    {"provider_team_id": 530, "primary_colour": "#CB3524", "secondary_colour": "#272E61"},
    {"provider_team_id": 532, "primary_colour": "#F18A00", "secondary_colour": "#000000"},
    {"provider_team_id": 533, "primary_colour": "#FFE667", "secondary_colour": "#005187"},
    {"provider_team_id": 536, "primary_colour": "#D71920", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 541, "primary_colour": "#FFFFFF", "secondary_colour": "#FEBE10"},
    {"provider_team_id": 549, "primary_colour": "#000000", "secondary_colour": "#FFFFFF"},
    {"provider_team_id": 611, "primary_colour": "#002D72", "secondary_colour": "#FFED00"},
    {"provider_team_id": 645, "primary_colour": "#A90432", "secondary_colour": "#FDB912"},
]


def upgrade() -> None:
    op.create_table(
        "team_visual_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=40), server_default=sa.text("'api_football'"), nullable=False),
        sa.Column("provider_team_id", sa.Integer(), nullable=False),
        sa.Column("primary_colour", sa.String(length=16), nullable=False),
        sa.Column("secondary_colour", sa.String(length=16), nullable=True),
        sa.Column("colour_source", sa.String(length=80), server_default=sa.text("'manual_registry'"), nullable=False),
        sa.Column("colour_status", sa.String(length=40), server_default=sa.text("'known'"), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_team_id", name="uq_team_visual_profiles_provider_team"),
        sa.UniqueConstraint("team_id", name="uq_team_visual_profiles_team"),
    )
    op.create_index("ix_team_visual_profiles_status", "team_visual_profiles", ["colour_status"])
    team_visuals = sa.table(
        "team_visual_profiles",
        sa.column("provider", sa.String),
        sa.column("provider_team_id", sa.Integer),
        sa.column("primary_colour", sa.String),
        sa.column("secondary_colour", sa.String),
        sa.column("colour_source", sa.String),
        sa.column("colour_status", sa.String),
    )
    op.bulk_insert(
        team_visuals,
        [
            {
                "provider": "api_football",
                "colour_source": "manual_registry",
                "colour_status": "known",
                **row,
            }
            for row in VISUAL_ROWS
        ],
    )
    op.execute(
        """
        UPDATE team_visual_profiles AS visual
        SET team_id = teams.id
        FROM teams
        WHERE teams.provider = visual.provider
          AND teams.provider_team_id = visual.provider_team_id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_team_visual_profiles_status", table_name="team_visual_profiles")
    op.drop_table("team_visual_profiles")
