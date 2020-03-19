##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

"""A blueprint module providing utility functions for the application."""

from flask import url_for
from pgadmin.utils import PgAdminModule

MODULE_NAME = 'profiling'


class ProfilingModule(PgAdminModule):
    """
    ProfilingModule

    This module will render the profiling of the browser nodes on selection
    when profiling panel is active.
    """

    def get_own_javascripts(self):
        return [{
            'name': 'pgadmin.browser.object_profiling',
            'path': url_for('profiling.static', filename='js/profiling'),
            'when': None
        }]


# Initialise the module
blueprint = ProfilingModule(
    MODULE_NAME, __name__, url_prefix='/misc/profiling'
)
