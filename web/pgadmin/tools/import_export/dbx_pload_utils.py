##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

from yaml import dump

from flask import render_template, current_app
from flask_babelex import gettext as _


class DBXPLoadConfig(object):
    """ Configuration file for dbx-pload
    """


    @classmethod
    def from_template(cls, data, columns, cred1, cred2, cred3, import_path, template):
        config = render_template( \
            'import_export/yaml/dbx_pload_config.yaml', \
            database=data['database'], \
            dbserver=data['server'], \
            columns=columns, \
            delimiter=data['delimiter'], \
            escape=data['escape'], \
            fmode=data['format'], \
            quote=data['quote'], \
            table=data['table'], \
            cred1=cred1, \
            cred2=cred2, \
            cred3=cred3, \
            import_path=import_path, \
            fformat='text')
        return cls(config)


    def __init__(self, config):
        self._config = config


    def __repr__(self):
        return self.__class__.__name__ + ":" + str(self)

    def __str__(self):
        return dump(self._config)
