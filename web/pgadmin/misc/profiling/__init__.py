##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

"""A blueprint module providing utility functions for the application."""

from flask import \
        url_for, \
        render_template
from flask_security import \
        current_user, \
        login_required
from pgadmin.utils import \
        PgAdminModule

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

    def get_exposed_url_endpoints(self):
        """
        Returns:
            list: a list of url endpoints exposed to the client.
        """
        return [
            'profiling.index'
            ]


# Initialise the module
blueprint = ProfilingModule(
    MODULE_NAME, __name__, url_prefix='/misc/profiling'
)



@blueprint.route('/', endpoint='index')
@login_required
def index():
    """
    Renders profiling template.
    Args:

    Returns: 
        Profiling template

    """

    return render_template(
        '/profiling/index.html',
    )
