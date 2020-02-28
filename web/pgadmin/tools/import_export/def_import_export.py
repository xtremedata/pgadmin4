##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

from flask import render_template, current_app
from flask_babelex import gettext as _

from pgadmin.misc.bgprocess.processes import \
        BatchProcess
from pgadmin.utils import \
        get_storage_directory, \
        document_dir, \
        fs_short_path, \
        IS_WIN
from pgadmin.utils.ajax import \
        make_json_response, \
        bad_request

from .utils import \
        filename_with_file_manager_path, \
        IEMessage



class DefImportExport(object):


    import_export_registry = {}


    @classmethod
    def create_job(cls, conn, driver, manager, utility, server, sid, data):
        
        return bad_request(errormsg=_('Not implemented yet'))

        # Get the storage path from preference
        storage_dir = get_storage_directory()

        if 'filename' in data:
            try:
                _file = filename_with_file_manager_path(
                    data['filename'], data['is_import'])
            except Exception as e:
                return bad_request(errormsg=str(e))

            if not _file:
                return bad_request(errormsg=_('Please specify a valid file'))

            if IS_WIN:
                _file = _file.replace('\\', '/')

            data['filename'] = _file
        else:
            return bad_request(errormsg=_('Please specify a valid file'))

        cols = None
        icols = None

        if data['icolumns']:
            ignore_cols = data['icolumns']

            # format the ignore column list required as per copy command
            # requirement
            if ignore_cols and len(ignore_cols) > 0:
                icols = ", ".join([
                    driver.qtIdent(conn, col)
                    for col in ignore_cols])

        # format the column import/export list required as per copy command
        # requirement
        if data['columns']:
            columns = data['columns']
            if columns and len(columns) > 0:
                for col in columns:
                    if cols:
                        cols += ', '
                    else:
                        cols = '('
                    cols += driver.qtIdent(conn, col)
                cols += ')'

        # Create the COPY FROM/TO  from template
        query = render_template(
            'import_export/sql/cmd.sql',
            conn=conn,
            data=data,
            columns=cols,
            ignore_column_list=icols
        )

        args = ['--command', query]

        try:
            p = BatchProcess(
                desc=IEMessage(
                    sid,
                    data['schema'],
                    data['table'],
                    data['database'],
                    storage_dir,
                    utility, *args
                ),
                cmd=utility, args=args
            )
            manager.export_password_env(p.id)

            env = dict()
            env['PGHOST'] = server.host
            env['PGPORT'] = str(server.port)
            env['PGUSER'] = server.username
            env['PGDATABASE'] = data['database']
            p.set_env_variables(server, env=env)
            p.start()
            jid = p.id
        except Exception as e:
            current_app.logger.exception(e)
            return bad_request(errormsg=str(e))

        # Return response
        return make_json_response(
            data={'job_id': jid, 'success': 1}
        )
        

