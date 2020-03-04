##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

from yaml import dump, safe_dump, safe_load, load
from json import dumps

from flask import render_template, current_app
from flask_babelex import gettext as _


class DBXPLoadConfig(object):
    """ Configuration file for dbx-pload
    """


    @classmethod
    def get_template_value(cls, value):
        """ Returns quoted strings for yaml templates.
        """
        return dumps(value)


    @classmethod
    def from_template(cls, data, columns, cred1, cred2, cred3, import_path, template):
        columns = cls.get_template_value(data['columns'])
        config = safe_load(render_template( \
            'import_export/yaml/dbx_pload_config.yaml', \
            database=cls.get_template_value(data['database']), \
            dbserver=cls.get_template_value(data['server']), \
            columns=cls.get_template_value(columns), \
            delimiter=cls.get_template_value(data['delimiter']), \
            escape=cls.get_template_value(data['escape']), \
            fmode=cls.get_template_value(data['format']), \
            quote=cls.get_template_value(data['quote']), \
            table=cls.get_template_value(data['table']), \
            cred1=cls.get_template_value(cred1), \
            cred2=cls.get_template_value(cred2), \
            cred3=cls.get_template_value(cred3), \
            import_path=cls.get_template_value(import_path), \
            fformat=cls.get_template_value('text')))
        return cls(config)


    def __init__(self, config):
        self._config = config


    def __repr__(self):
        return self.__class__.__name__ + ":" + str(self)

    def __str__(self):
        return dump(self._config)

    def save(self, stream):
        stream.write(str(self._config))
