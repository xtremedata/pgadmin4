##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

import os, sys

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

    def utility(self, operation, sversion):
        res = None

        if operation == 'backup':
            res = 'pg_dump'
        elif operation == 'backup_server':
            res = 'pg_dumpall'
        elif operation == 'restore':
            res = 'pg_restore'
        elif operation == 'sql':
            res = 'psql'
        elif operation == 'import_export':
            res = 'dbx-pload'
        else:
            raise Exception(
                gettext("Could not find the utility for the operation '%s'" \
                        % operation
                ))

        bin_path = self.utility_path.get()
        if "$DIR" in bin_path:
            # When running as an WSGI application, we will not find the
            # '__file__' attribute for the '__main__' module.
            main_module_file = getattr(
                sys.modules['__main__'], '__file__', None
            )

            if main_module_file is not None:
                bin_path = bin_path.replace(
                    "$DIR", os.path.dirname(main_module_file)
                )

        return os.path.abspath(os.path.join(
            bin_path,
            (res if os.name != 'nt' else (res + '.exe'))
        ))


# Default Server Type
DBX('dbx', gettext("dbX Database"), 4)
