##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

from flask_babelex import gettext
from pgadmin.browser.server_groups.servers.types import ServerType


class DBX(ServerType):
    UTILITY_PATH_LABEL = gettext("dbX Database Binary Path")
    UTILITY_PATH_HELP = gettext(
        "Path to the directory containing the dbX Database utility"
        " programs (pg_dump, pg_restore etc)."
    )

    @property
    def icon(self):
        return "dbx.png"

    def instanceOf(self, ver):
        return "PostgreSQL 8.1.2" in ver


# Default Server Type
DBX('dbx', gettext("dbX Database"), 4)
