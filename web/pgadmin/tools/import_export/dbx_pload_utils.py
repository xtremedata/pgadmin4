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
    def get_escape_value(cls, value):
        """ Special processing for the escape character.
        """
        escape = value
        if escape and escape in "'\\":
            escape = '\\%s' % escape
            escape = cls.get_template_value(escape)
        return escape if escape else None


    @classmethod
    def get_delimiter_value(cls, value):
        """ Special processing for the delimiter character.
        """
        return cls.get_template_value(value) if value else None


    @classmethod
    def from_template(cls, data, columns, cred1, cred2, cred3, import_path, template):
        escape = cls.get_escape_value(data['escape'])
        delimiter = cls.get_delimiter_value(data['delimiter'])
        config = safe_load(render_template( \
            template, \
            database=cls.get_template_value(data['database']), \
            dbserver=cls.get_template_value(data['server']), \
            columns=cls.get_template_value(columns), \
            delimiter=delimiter, \
            error_log=cls.get_template_value("/dbxvol/node-data/_stage/log/my_error.log"), \
            escape=escape, \
            fmode=cls.get_template_value(data['format'].upper()), \
            quote=cls.get_template_value(data['quote']), \
            table=cls.get_template_value(data['table']), \
            log_file=cls.get_template_value("/home/dbxdba/loader/loader.log"), \
            cred1=cls.get_template_value(cred1), \
            cred2=cls.get_template_value(cred2), \
            cred3=cls.get_template_value(cred3), \
            import_path=cls.get_template_value(import_path), \
            fformat=cls.get_template_value('TEXT'), \
            job_dir=cls.get_template_value("/xdlog/temp/job"), \
            stage_dir=cls.get_template_value("/dbxvol/node-data/_stage/work")))
        return cls(config)


    def __init__(self, config):
        self._config = config


    def __repr__(self):
        return self.__class__.__name__ + ":" + str(self)

    def __str__(self):
        return dump(self._config)

    def save(self, stream):
        stream.write(str(self._config))