from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add the local_file_path column to entregas table
    with op.batch_alter_table('entregas') as batch_op:
        batch_op.add_column(sa.Column('local_file_path', sa.String(), nullable=True))

def downgrade():
    # Remove the local_file_path column from entregas table
    with op.batch_alter_table('entregas') as batch_op:
        batch_op.drop_column('local_file_path')
