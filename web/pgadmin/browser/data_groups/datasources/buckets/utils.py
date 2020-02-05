##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

"""Bucket helper utilities"""

from flask import current_app


def convert_bucket_acl_to_props(bucket_id, bucket_acl):
    """ Converts bucket acl (see s3 documentation) to pgadmin properties.
    """

    try:
        bucket_props = {
            'id': bucket_id,
            'name': bucket_id,
            'bucket': bucket_id,
            'dataowner' : bucket_acl['Owner']['DisplayName'],
            'access': {o['Grantee']['DisplayName']: o['Permission'] for o in bucket_acl['Grants']}
        }

    except KeyError as e:
        current_app.logger.exception(e)
        raise

    else:
        return bucket_props
