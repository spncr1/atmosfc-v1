"""Add archive sync status tracking.

Revision ID: 20260804_0002
Revises: 20260803_0001
Create Date: 2026-08-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260804_0002"
down_revision = "20260803_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "archive_sync_status",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("scope_type", sa.String(length=80), nullable=False),
        sa.Column("scope_key", sa.String(length=260), nullable=False),
        sa.Column("provider_team_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provider_competition_id", sa.Integer(), nullable=True),
        sa.Column("season_year", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("records_seen", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("records_changed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "scope_key", name="uq_archive_sync_status_provider_scope_key"),
    )
    op.create_index(
        "ix_archive_sync_status_lookup",
        "archive_sync_status",
        ["provider_competition_id", "season_year"],
    )
    op.create_index(
        "ix_archive_sync_status_scope_status",
        "archive_sync_status",
        ["scope_type", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_archive_sync_status_scope_status", table_name="archive_sync_status")
    op.drop_index("ix_archive_sync_status_lookup", table_name="archive_sync_status")
    op.drop_table("archive_sync_status")
