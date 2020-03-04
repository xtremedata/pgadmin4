##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

"""A blueprint module implementing the import and export functionality"""

import simplejson as json
import os

from flask import url_for, Response, render_template, request, current_app
from flask_babelex import gettext as _
from flask_security import login_required, current_user
from pgadmin.misc.bgprocess.processes import BatchProcess
from pgadmin.utils import PgAdminModule, get_storage_directory, html, \
    fs_short_path, document_dir, IS_WIN, does_utility_exist
from pgadmin.utils.ajax import make_json_response, bad_request

from config import PG_DEFAULT_DRIVER
from pgadmin.model import Server

from .utils import filename_with_file_manager_path, IEMessage
from .def_import_export import DefImportExport
from .s3_import_export import S3ImportExport

MODULE_NAME = 'import_export'


class ImportExportModule(PgAdminModule):
    """
    class ImportExportModule(PgAdminModule)

        A module class for import which is derived from PgAdminModule.

    Methods:
    -------
    * get_own_javascripts(self)
      - Method is used to load the required javascript files for import module
    """

    LABEL = _('Import/Export')

    def get_own_javascripts(self):
        scripts = list()
        for name, script in [
            ['pgadmin.tools.import_export', 'js/import_export']
        ]:
            scripts.append({
                'name': name,
                'path': url_for('import_export.index') + script,
                'when': None
            })

        return scripts

    def get_exposed_url_endpoints(self):
        """
        Returns:
            list: URL endpoints for backup module
        """
        return ['import_export.create_job', 'import_export.utility_exists']


blueprint = ImportExportModule(MODULE_NAME, __name__)


@blueprint.route("/")
@login_required
def index():
    return bad_request(errormsg=_("This URL cannot be called directly."))


@blueprint.route("/js/import_export.js")
@login_required
def script():
    """render the import/export javascript file"""
    return Response(
        response=render_template("import_export/js/import_export.js", _=_),
        status=200,
        mimetype="application/javascript"
    )


@blueprint.route('/job/<int:sid>', methods=['POST'], endpoint="create_job")
@login_required
def create_import_export_job(sid):
    """
    Args:
        sid: Server ID

        Creates a new job for import and export table data functionality

    Returns:
        None
    """
    if request.form:
        data = json.loads(request.form['data'], encoding='utf-8')
    else:
        data = json.loads(request.data, encoding='utf-8')

    # Fetch the server details like hostname, port, roles etc
    server = Server.query.filter_by(
        id=sid).first()

    if server is None:
        return bad_request(errormsg=_("Could not find the given server"))

    # To fetch MetaData for the server
    from pgadmin.utils.driver import get_driver
    driver = get_driver(PG_DEFAULT_DRIVER)
    manager = driver.connection_manager(server.id)
    conn = manager.connection()
    connected = conn.connected()

    if not connected:
        return bad_request(errormsg=_("Please connect to the server first..."))

    # Get the utility path from the connection manager
    utility = manager.utility('import_export')
    ret_val = does_utility_exist(utility)
    # todo: testing remote calls
    if False and ret_val:
        return make_json_response(
            success=0,
            errormsg=ret_val
        )

    try:
        is_def_ds = data['is_def_ds']
    except KeyError:
        is_def_ds = True


    if is_def_ds:
        return DefImportExport.create_job( \
                conn, \
                driver, \
                manager, \
                utility, \
                server, \
                sid, \
                data)

    if not is_def_ds:
        # For now only support for S3 import/exports
        # todo: loading registered module based on datasource type
        return S3ImportExport.create_job( \
                conn, \
                driver, \
                manager, \
                utility, \
                server, \
                sid, \
                data)

    return bad_request(errormsg=_("Invalid request parameters, cannot find proper import module"))


@blueprint.route(
    '/utility_exists/<int:sid>', endpoint='utility_exists'
)
@login_required
def check_utility_exists (sid):
    """
    This function checks the utility file exist on the given path.

    Args:
        sid: Server ID
    Returns:
        None
    """
    server = Server.query.filter_by(
        id=sid, user_id=current_user.id
    ).first()

    if server is None:
        return make_json_response(
            success=0,
            errormsg=_("Could not find the specified server.")
        )

    from pgadmin.utils.driver import get_driver
    driver = get_driver(PG_DEFAULT_DRIVER)
    manager = driver.connection_manager(server.id)

    utility = manager.utility('sql')
    current_app.logger.info("###### ver:%s, server_type:%s, sid:%s, utility:%s" \
            % (manager.version, str(manager.server_type), str(server.id), utility))
    ret_val = does_utility_exist(utility)
    # todo: temporarily for tests of remote load
    if False and ret_val:
        return make_json_response(
            success=0,
            errormsg=ret_val
        )

    return make_json_response(success=1)
