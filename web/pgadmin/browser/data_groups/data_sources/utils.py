##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

"""Data source helper utilities"""
import config
from pgadmin.model import db, DataSource



def remove_saved_secrets(user_id):
    """
    This function will remove all the saved secrets for the data source
    """

    try:
        db.session.query(DataSource) \
            .filter(DataSource.user_id == user_id) \
            .update({DataSource.key_secret: None, DataSource.key_name: None})
        db.session.commit()
    except Exception as _:
        db.session.rollback()
        raise
