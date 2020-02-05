
"""empty message

Revision ID: e39f9acd642f
Revises: aff1436e3c8c
Create Date: 2020-01-24 15:45:08.144437

"""
from pgadmin.model import db


# revision identifiers, used by Alembic.
revision = 'e39f9acd642f'
down_revision = 'aff1436e3c8c'
branch_labels = None
depends_on = None


def upgrade():
    db.engine.execute("""
            CREATE TABLE datagroup (
                id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                name VARCHAR(128) NOT NULL,
                can_delete INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (id),
                FOREIGN KEY(user_id) REFERENCES "user" (id),
                UNIQUE (user_id, name))
    """)

    db.engine.execute("""
            CREATE TABLE datasource (
                id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                datagroup_id INTEGER NOT NULL,
                name VARCHAR(128) NOT NULL,
                ds_type VARCHAR(16) NOT NULL CHECK(ds_type IN ('S3')),
                key_name VARCHAR(128) NOT NULL,
                key_secret VARCHAR(128),
                bgcolor VARCHAR(10),
                fgcolor VARCHAR(10),
                PRIMARY KEY (id),
                FOREIGN KEY(user_id) REFERENCES "user" (id),
                FOREIGN KEY(datagroup_id) REFERENCES "datagroup" (id),
                UNIQUE (user_id, name))
    """)
    db.engine.execute("""
INSERT INTO "datagroup"
VALUES(1, 1, 'Datas', 0)
""")


def downgrade():
    op.drop_table('datasource')
    op.drop_table('datagroup')
