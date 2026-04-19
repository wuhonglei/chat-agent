"""add kb_file_chunk_embeddings table

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-04-18

"""

from __future__ import annotations

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "w3x4y5z6a7b8"
down_revision = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSION = 1024


def upgrade() -> None:
    op.create_table(
        "kb_file_chunk_embeddings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("file_id", sa.String(length=64), nullable=False),
        sa.Column("chunk_idx", sa.Integer(), nullable=False),
        sa.Column("chunk_content", sa.Text(), nullable=False),
        sa.Column("embedding_vector", Vector(EMBEDDING_DIMENSION), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "file_id",
            "chunk_idx",
            name="uq_kb_file_chunk_embeddings_user_file_chunk_idx",
        ),
    )
    op.create_index(
        "ix_kb_file_chunk_embeddings_id",
        "kb_file_chunk_embeddings",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_kb_file_chunk_embeddings_user_id",
        "kb_file_chunk_embeddings",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_kb_file_chunk_embeddings_file_id",
        "kb_file_chunk_embeddings",
        ["file_id"],
        unique=False,
    )
    op.create_index(
        "ix_kb_file_chunk_embeddings_created_at",
        "kb_file_chunk_embeddings",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_kb_file_chunk_embeddings_user_file",
        "kb_file_chunk_embeddings",
        ["user_id", "file_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_kb_file_chunk_embeddings_user_file",
        table_name="kb_file_chunk_embeddings",
    )
    op.drop_index(
        "ix_kb_file_chunk_embeddings_created_at",
        table_name="kb_file_chunk_embeddings",
    )
    op.drop_index(
        "ix_kb_file_chunk_embeddings_file_id",
        table_name="kb_file_chunk_embeddings",
    )
    op.drop_index(
        "ix_kb_file_chunk_embeddings_user_id",
        table_name="kb_file_chunk_embeddings",
    )
    op.drop_index(
        "ix_kb_file_chunk_embeddings_id",
        table_name="kb_file_chunk_embeddings",
    )
    op.drop_table("kb_file_chunk_embeddings")
