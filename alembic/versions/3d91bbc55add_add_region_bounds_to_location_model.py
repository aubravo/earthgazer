"""Add region bounds to Location model

Revision ID: 3d91bbc55add
Revises: 827538c95467
Create Date: 2026-01-25 02:06:13.491372

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d91bbc55add'
down_revision: Union[str, Sequence[str], None] = '827538c95467'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Add new columns as nullable first
    op.add_column('locations', sa.Column('min_lon', sa.Float(), nullable=True), schema='earthgazer')
    op.add_column('locations', sa.Column('min_lat', sa.Float(), nullable=True), schema='earthgazer')
    op.add_column('locations', sa.Column('max_lon', sa.Float(), nullable=True), schema='earthgazer')
    op.add_column('locations', sa.Column('max_lat', sa.Float(), nullable=True), schema='earthgazer')

    # Step 2: Populate with default values based on existing point coordinates
    # Creates a small bounding box around the existing point (approx 0.5 degree buffer)
    op.execute("""
        UPDATE earthgazer.locations
        SET min_lon = longitude - 0.25,
            min_lat = latitude - 0.25,
            max_lon = longitude + 0.25,
            max_lat = latitude + 0.25
        WHERE min_lon IS NULL
    """)

    # Step 3: Make the new columns NOT NULL
    op.alter_column('locations', 'min_lon',
               existing_type=sa.Float(),
               nullable=False,
               schema='earthgazer')
    op.alter_column('locations', 'min_lat',
               existing_type=sa.Float(),
               nullable=False,
               schema='earthgazer')
    op.alter_column('locations', 'max_lon',
               existing_type=sa.Float(),
               nullable=False,
               schema='earthgazer')
    op.alter_column('locations', 'max_lat',
               existing_type=sa.Float(),
               nullable=False,
               schema='earthgazer')

    # Step 4: Make legacy point columns nullable
    op.alter_column('locations', 'longitude',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True,
               schema='earthgazer')
    op.alter_column('locations', 'latitude',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True,
               schema='earthgazer')


def downgrade() -> None:
    """Downgrade schema."""
    # Restore longitude/latitude as NOT NULL (use center of bounds)
    op.execute("""
        UPDATE earthgazer.locations
        SET longitude = (min_lon + max_lon) / 2,
            latitude = (min_lat + max_lat) / 2
        WHERE longitude IS NULL OR latitude IS NULL
    """)

    op.alter_column('locations', 'latitude',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False,
               schema='earthgazer')
    op.alter_column('locations', 'longitude',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False,
               schema='earthgazer')

    # Drop the new columns
    op.drop_column('locations', 'max_lat', schema='earthgazer')
    op.drop_column('locations', 'max_lon', schema='earthgazer')
    op.drop_column('locations', 'min_lat', schema='earthgazer')
    op.drop_column('locations', 'min_lon', schema='earthgazer')
