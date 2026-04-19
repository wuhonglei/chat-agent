"""add ivfflat index for kb chunk embeddings

Revision ID: x9y8z7a6b5c4
Revises: w3x4y5z6a7b8
Create Date: 2026-04-19

"""

from __future__ import annotations

from alembic import op

revision = "x9y8z7a6b5c4"
down_revision = "w3x4y5z6a7b8"
branch_labels = None
depends_on = None

_INDEX_NAME = "ix_kb_file_chunk_embeddings_embedding_vector_ivfflat"
_TABLE_NAME = "kb_file_chunk_embeddings"


def upgrade() -> None:
    context = op.get_context()
    with context.autocommit_block():
        op.execute(
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX_NAME}
            ON {_TABLE_NAME}
            USING ivfflat (embedding_vector vector_cosine_ops)
            WITH (lists = 100)
            """
        )
    op.execute(f"ANALYZE {_TABLE_NAME}")


def downgrade() -> None:
    context = op.get_context()
    with context.autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")
