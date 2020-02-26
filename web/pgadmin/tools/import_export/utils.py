##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

from os import path

from flask_babelex import gettext as _
from flask_security import current_user

from pgadmin.utils import \
        get_storage_directory, \
        document_dir, \
        fs_short_path, \
        html
from pgadmin.misc.bgprocess.processes import \
        IProcessDesc
from pgadmin.model import Server


def filename_with_file_manager_path(_file, _present=False):
    """
    Args:
        file: File name returned from client file manager

    Returns:
        Filename to use for backup with full path taken from preference
    """
    # Set file manager directory from preference
    storage_dir = get_storage_directory()

    if storage_dir:
        _file = path.join(storage_dir, _file.lstrip(u'/').lstrip(u'\\'))
    elif not path.isabs(_file):
        _file = path.join(document_dir(), _file)

    if not _present:
        # Touch the file to get the short path of the file on windows.
        with open(_file, 'a'):
            pass
    else:
        if not path.isfile(_file):
            return None

    return fs_short_path(_file)




class IEMessage(IProcessDesc):
    """
    IEMessage(IProcessDesc)

    Defines the message shown for the import/export operation.
    """

    def __init__(self, _sid, _schema, _tbl, _database, _storage, *_args):
        self.sid = _sid
        self.schema = _schema
        self.table = _tbl
        self.database = _database
        self._cmd = ''

        if _storage:
            _storage = _storage.replace('\\', '/')

        def cmdArg(x):
            if x:
                x = x.replace('\\', '\\\\')
                x = x.replace('"', '\\"')
                x = x.replace('""', '\\"')

                return ' "' + x + '"'
            return ''

        replace_next = False
        for arg in _args:
            if arg and len(arg) >= 2 and arg[:2] == '--':
                if arg == '--command':
                    replace_next = True
                self._cmd += ' ' + arg
            elif replace_next:
                arg = cmdArg(arg)
                if _storage is not None:
                    arg = arg.replace(_storage, '<STORAGE_DIR>')
                self._cmd += ' "' + arg + '"'
            else:
                self._cmd += cmdArg(arg)

    @property
    def message(self):
        # Fetch the server details like hostname, port, roles etc
        s = Server.query.filter_by(
            id=self.sid, user_id=current_user.id
        ).first()

        return _(
            "Copying table data '{0}.{1}' on database '{2}' "
            "and server ({3}:{4})"
        ).format(
            html.safe_str(self.schema),
            html.safe_str(self.table),
            html.safe_str(self.database),
            html.safe_str(s.host),
            html.safe_str(s.port)
        )

    @property
    def type_desc(self):
        return _("Copying table data")

    def details(self, cmd, args):
        # Fetch the server details like hostname, port, roles etc
        s = Server.query.filter_by(
            id=self.sid, user_id=current_user.id
        ).first()

        res = '<div>'
        res += _(
            "Copying table data '{0}.{1}' on database '{2}' "
            "for the server '{3}'"
        ).format(
            html.safe_str(self.schema),
            html.safe_str(self.table),
            html.safe_str(self.database),
            "{0} ({1}:{2})".format(
                html.safe_str(s.name),
                html.safe_str(s.host),
                html.safe_str(s.port)
            )
        )

        res += '</div><div class="py-1">'
        res += _("Running command:")
        res += '<div class="pg-bg-cmd enable-selection p-1">'
        res += html.safe_str(self._cmd)
        res += '</div></div>'

        return res
