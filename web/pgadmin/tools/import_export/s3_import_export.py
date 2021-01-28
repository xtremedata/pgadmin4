##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

from os import environ

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
from pgadmin.utils.s3 import S3

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

        s3 = S3()
        filename_url = None
        bucket = None
        filename = None
        ds_id = None
        gd_id = None
        try:
            bucket = data['bucket']
            filename = s3.fix_pgadmin_path(data['filename'])
            mapper = data['nodes_info_map']
            ds = data['datasource']
            gd = data['data_group']
            ds_id = mapper['datasource'][ds]['_id']
            gd_id = mapper['data_group'][gd]['_id']
        except KeyError as e:
            return bad_request(errormsg=_( \
                    'Please specify a valid file and/or S3 bucket ({0})').format(str(e)))

        s3.authenticate(gd_id, ds_id)
        if s3.exists(bucket, filename):
            filename_url = S3.create_s3_url(bucket, filename)
        else:
            current_app.logger.info( \
                    "Not found import/export file:%s, bucket:%s" % (filename, bucket))
            return bad_request(errormsg=_('Please specify a valid file'))

        cols = None
        icols = None

        # format the ignore column list required as per copy command
        # requirement
        try:
            icols = data['icolumns']
        except KeyError:
            icols = None
        else:
            if icols and len(icols) > 0:
                icols = [driver.qtIdent(conn, col) for col in icols]


        # format the column import/export list required as per copy command
        # requirement
        try:
            cols = data['cols']
        except KeyError:
            cols = None
        else:
            if cols and len(cols) > 0:
                cols = [driver.qtIdent(conn, col) for col in data['cols']]

        cred1 = environ['AWS_ACCESS_KEY_ID'] if 'AWS_ACCESS_KEY_ID' in environ else None
        cred2 = environ['AWS_SECRET_ACCESS_KEY'] if 'AWS_SECRET_ACCESS_KEY' in environ else None
        cred3 = None
        import_path = filename_url
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
        with open("/tmp/pload_config.yaml", "w") as fd:
            pload_config.save(fd)


        storage_dir = 's3'
        # for tests ssh is needed
        ssh_call = [ \
                '-l', \
                'ec2-user', \
                server.host, \
                'sudo', \
                '-i', \
                '-u', \
                server.username, \
                '--', \
                utility, \
                '--file', \
                'stdin']
        utility = 'ssh'
        args = ssh_call

        #current_app.logger.debug("#### cmd:%s, args:%s" % (utility, args))

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
            env['DBX_PLOAD_CONFIG'] = str(pload_config)
            p.set_env_variables(server, env=env)
            p.start(data_in=pload_config)
            jid = p.id

        except Exception as e:
            current_app.logger.exception(e)
            return bad_request(errormsg=str(e))

        # Return response
        return make_json_response(
            data={'job_id': jid, 'success': 1}
        )
        

