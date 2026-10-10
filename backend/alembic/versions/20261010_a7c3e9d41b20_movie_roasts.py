"""movie roasts: replace article columns with TMDB movie + reaction GIF columns

News roasts can't be converted into movie roasts, so existing roast rows are deleted.
Users and refresh tokens are kept. The downgrade restores the article columns (empty table).

Revision ID: a7c3e9d41b20
Revises: 6bac50f1c1ac
Create Date: 2026-10-10 17:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7c3e9d41b20'
down_revision: str | Sequence[str] | None = '6bac50f1c1ac'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DELETE FROM roasts")
    op.drop_index('ix_roasts_cache_lookup', table_name='roasts')
    for column in ('source_url', 'url_hash', 'source_domain', 'article_title', 'article_excerpt'):
        op.drop_column('roasts', column)
    op.add_column('roasts', sa.Column('tmdb_id', sa.Integer(), nullable=False))
    op.add_column('roasts', sa.Column('movie_title', sa.String(length=300), nullable=False))
    op.add_column('roasts', sa.Column('release_year', sa.Integer(), nullable=True))
    op.add_column('roasts', sa.Column('original_language', sa.String(length=8), nullable=False))
    op.add_column('roasts', sa.Column('poster_path', sa.String(length=255), nullable=True))
    op.add_column('roasts', sa.Column('gif_url', sa.String(length=500), nullable=True))
    op.add_column('roasts', sa.Column('gif_page_url', sa.String(length=500), nullable=True))
    op.create_index(
        'ix_roasts_cache_lookup',
        'roasts',
        ['tmdb_id', 'spice_level', 'status', 'created_at'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM roasts")
    op.drop_index('ix_roasts_cache_lookup', table_name='roasts')
    for column in (
        'tmdb_id',
        'movie_title',
        'release_year',
        'original_language',
        'poster_path',
        'gif_url',
        'gif_page_url',
    ):
        op.drop_column('roasts', column)
    op.add_column('roasts', sa.Column('source_url', sa.String(length=2048), nullable=False))
    op.add_column('roasts', sa.Column('url_hash', sa.String(length=64), nullable=False))
    op.add_column('roasts', sa.Column('source_domain', sa.String(length=255), nullable=False))
    op.add_column('roasts', sa.Column('article_title', sa.String(length=500), nullable=False))
    op.add_column('roasts', sa.Column('article_excerpt', sa.String(length=500), nullable=False))
    op.create_index(
        'ix_roasts_cache_lookup',
        'roasts',
        ['url_hash', 'spice_level', 'status', 'created_at'],
        unique=False,
    )
