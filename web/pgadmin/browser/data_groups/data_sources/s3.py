##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

from flask_babelex import gettext
from pgadmin.browser.data_groups.data_sources.types import DataSourceType


class S3(DataSourceType):
    UTILITY_PATH_LABEL = gettext("AWS S3 Data Source")
    UTILITY_PATH_HELP = gettext(
        "Path to the directory containing the dbX Database utility"
        " programs (pg_dump, pg_restore etc)."
    )

    def instanceOf(self, ver):
        return True


# Default Data Source Type
S3('S3', gettext("AWS S3 Data Source"), 0)