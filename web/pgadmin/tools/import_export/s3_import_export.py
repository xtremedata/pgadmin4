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
from .dbx_pload_utils import DBXPLoadConfig



class S3ImportExport(object):
    """

    Excample:
        path:   s3://oleg-test/cluster1/s3test.txt
        url:    https://oleg-test.s3.amazonaws.com/cluster1/s3test.txt
    """


    import_export_registry = {}


    @classmethod
    def create_job(cls, conn, driver, manager, utility, server, sid, data):

        if 'filename' in data:
            try:
                _file = filename_with_file_manager_path(
                    data['filename'], data['is_import'])
            except Exception as e:
                return bad_request(errormsg=str(e))

            if False and not _file:
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

        cred1 = None
        cred2 = None
        cred3 = None
        import_path = None
        # Create pload configuration
        pload_config = DBXPLoadConfig.from_template( \
                data, \
                cols, \
                cred1, \
                cred2, \
                cred3, \
                import_path, \
                'import_export/yaml/dbx_pload_config.yaml')

        current_app.logger.debug(pload_config)

        storage_dir = 's3'
        # for tests ssh is needed
        ssh_call = [ \
                '-l', \
                'ec2-user', \
                server.host, \
                utility, \
                ]
        utility = 'ssh'
        args = ssh_call
        args.extend(['--file', 'stdin'])

        current_app.logger.debug("#### cmd:%s, args:%s" % (utility, args))

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
        

