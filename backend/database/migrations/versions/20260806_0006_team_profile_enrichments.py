"""Add team profile enrichment cache.

Revision ID: 20260806_0006
Revises: 20260805_0005
Create Date: 2026-08-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260806_0006"
down_revision = "20260805_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_profile_enrichments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), server_default=sa.text("'api_football'"), nullable=False),
        sa.Column("provider_team_id", sa.Integer(), nullable=False),
        sa.Column("wikidata_qid", sa.String(length=32), nullable=True),
        sa.Column("wikipedia_title", sa.String(length=240), nullable=True),
        sa.Column("wikipedia_url", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("facts_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attribution_url", sa.Text(), nullable=True),
        sa.Column("license_label", sa.String(length=80), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", name="uq_team_profile_enrichments_team"),
        sa.UniqueConstraint("provider", "provider_team_id", name="uq_team_profile_enrichments_provider_team"),
    )
    op.create_index(
        "ix_team_profile_enrichments_needs_review",
        "team_profile_enrichments",
        ["needs_review"],
    )
    op.create_index(
        "ix_team_profile_enrichments_wikidata_qid",
        "team_profile_enrichments",
        ["wikidata_qid"],
    )


def downgrade() -> None:
    op.drop_index("ix_team_profile_enrichments_wikidata_qid", table_name="team_profile_enrichments")
    op.drop_index("ix_team_profile_enrichments_needs_review", table_name="team_profile_enrichments")
    op.drop_table("team_profile_enrichments")
