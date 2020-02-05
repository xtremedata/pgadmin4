##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################


from flask import render_template, current_app
from flask_babelex import gettext


class DataSourceType(object):
    """
    DataSource Type

    Create an instance of this class to define new type of the data source support,
    In order to define new type of instance, you may want to override this
    class with overriden function - instanceOf for type checking for
    identification based on the version.
    """
    ID = 'LFS'

    registry = dict()

    def __init__(self, datasource_type, description, priority):
        self._type = datasource_type
        self.desc = description
        self._priority = priority
        self.utility_path = None

        assert (datasource_type not in DataSourceType.registry)
        DataSourceType.registry[datasource_type] = self

    @property
    def icon(self):
        return "%s.svg" % self._type.lower()

    @property
    def datasource_type(self):
        return self._type

    @property
    def description(self):
        return self.desc

    @property
    def priority(self):
        return self._priority

    @property
    def required(self):
        return [u'name', u'ds_type']

    def __str__(self):
        return "Type: {0}, Description:{1}, Priority: {2}".format(
            self._type, self.desc, self._priority
        )

    def instanceOf(self, obj):
        return True

    @property
    def csssnippets(self):
        """
        Returns a snippet of css to include in the page
        """
        return [
            render_template(
                "css/datasource_type.css",
                datasource_type=self._type,
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

    @classmethod
    def type(cls, datasource_type):
        try:
            return cls.registry[datasource_type]
        except KeyError as e:
            current_app.logger.exception("Not implemented data source type:", e)


    def get_manager(self):
        return None


# Default DataSource Type
DataSourceType(DataSourceType.ID, gettext("Local File System"), -1)
