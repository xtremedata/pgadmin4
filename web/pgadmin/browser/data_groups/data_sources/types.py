##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

import os
import sys

from flask import render_template
from flask_babelex import gettext as _
from pgadmin.utils.preferences import Preferences

import config


class DataSourceType(object):
    """
    DataSource Type

    Create an instance of this class to define new type of the data source support,
    In order to define new type of instance, you may want to override this
    class with overriden function - instanceOf for type checking for
    identification based on the version.
    """
    registry = dict()

    def __init__(self, datasource_type, description, priority):
        self.stype = datasource_type
        self.desc = description
        self.spriority = priority
        self.utility_path = None

        assert (datasource_type not in DataSourceType.registry)
        DataSourceType.registry[datasource_type] = self

    @property
    def icon(self):
        return "%s.svg" % self.stype.lower()

    @property
    def datasource_type(self):
        return self.stype

    @property
    def description(self):
        return self.desc

    @property
    def priority(self):
        return self.spriority

    def __str__(self):
        return "Type: {0}, Description:{1}, Priority: {2}".format(
            self.stype, self.desc, self.spriority
        )

    def instanceOf(self, version):
        return True

    @property
    def csssnippets(self):
        """
        Returns a snippet of css to include in the page
        """
        return [
            render_template(
                "css/datasource_type.css",
                datasource_type=self.stype,
                icon=self.icon
            )
        ]

    @classmethod
    def types(cls):
        return sorted(
            DataSourceType.registry.values(),
            key=lambda x: x.priority,
            reverse=True
        )


# Default DataSource Type
DataSourceType('lfs', _("Local FileSystem"), -1)
