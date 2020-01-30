##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

"""Bucket helper utilities"""



def convert_bucket_acl_to_props(bucket_id, bucket_acl):
    """ Converts bucket acl (see s3 documentation) to pgadmin properties.
    """

    try:
        bucket_props = {
            'bucket': bucket_id
        }

        bucket_props.update(bucket_acl)

    except KeyError as e:
        raise

    else:
        return bucket_props
