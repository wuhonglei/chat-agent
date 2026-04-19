"""add kb_file_chunk_embeddings table

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-04-18

"""

from __future__ import annotations

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import inspect

from alembic import op

revision = "w3x4y5z6a7b8"
down_revision = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSION = 1024


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_name = "kb_file_chunk_embeddings"

    if not inspector.has_table(table_name):
        op.create_table(
            table_name,
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
        )

    # 兼容“表已被 create_all 提前创建”的场景：补齐唯一约束和索引。
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_kb_file_chunk_embeddings_user_file_chunk_idx'
                  AND conrelid = 'kb_file_chunk_embeddings'::regclass
            ) THEN
                ALTER TABLE kb_file_chunk_embeddings
                ADD CONSTRAINT uq_kb_file_chunk_embeddings_user_file_chunk_idx
                UNIQUE (user_id, file_id, chunk_idx);
            END IF;
        END $$;
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kb_file_chunk_embeddings_id ON kb_file_chunk_embeddings (id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kb_file_chunk_embeddings_user_id ON kb_file_chunk_embeddings (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kb_file_chunk_embeddings_file_id ON kb_file_chunk_embeddings (file_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kb_file_chunk_embeddings_created_at ON kb_file_chunk_embeddings (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kb_file_chunk_embeddings_user_file ON kb_file_chunk_embeddings (user_id, file_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_kb_file_chunk_embeddings_user_file")
    op.execute("DROP INDEX IF EXISTS ix_kb_file_chunk_embeddings_created_at")
    op.execute("DROP INDEX IF EXISTS ix_kb_file_chunk_embeddings_file_id")
    op.execute("DROP INDEX IF EXISTS ix_kb_file_chunk_embeddings_user_id")
    op.execute("DROP INDEX IF EXISTS ix_kb_file_chunk_embeddings_id")
    op.execute(
        """
        ALTER TABLE IF EXISTS kb_file_chunk_embeddings
        DROP CONSTRAINT IF EXISTS uq_kb_file_chunk_embeddings_user_file_chunk_idx
        """
    )
    op.execute("DROP TABLE IF EXISTS kb_file_chunk_embeddings")
