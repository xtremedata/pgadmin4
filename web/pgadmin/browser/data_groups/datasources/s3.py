##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

from flask_babelex import gettext
from pgadmin.browser.data_groups.datasources.types import DataSourceType

try:
    from boto3 import client
    has_boto3 = True
except ImportError:
    has_boto3 = False


class S3(DataSourceType):
    """
    Data source type
    
    This data source support access to S3 buckets.
    """
    ID = 'S3'
    AWS_ID = 's3'

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._obj_types = { \
                gettext(u'text'): u'txt', \
                gettext(u'csv'): u'csv', \
                gettext(u'parquet'): u'par', \
                gettext(u'all'): u'*'}

    @property
    def required(self):
        s3_required = [u'key_name', u'key_secret']
        return super().required.append(s3_required)

    def instanceOf(self, obj):
        return True

    def get_manager(self):
        return client(self.AWS_ID)


# Default Data Source Type
if has_boto3:
    S3(S3.ID, gettext("AWS S3"), 0)
