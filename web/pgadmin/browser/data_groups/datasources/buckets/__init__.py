##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

"""Implements the Data source Bucket Node"""

from functools import wraps
from boto3 import client

import simplejson as json
from flask import render_template, current_app, request, jsonify
from flask_babelex import gettext as _
from flask_security import current_user

import pgadmin.browser.data_groups.datasources as datasources
from pgadmin.browser.collection import CollectionNodeModule
from pgadmin.browser.utils import PGChildNodeView
from pgadmin.utils.ajax import gone
from pgadmin.utils.ajax import \
         make_json_response, \
         make_response as ajax_response, \
         internal_server_error, \
         unauthorized
from pgadmin.utils.driver import get_driver
from pgadmin.tools.sqleditor.utils.query_history import QueryHistory

from pgadmin.model import DataSource


class BucketModule(CollectionNodeModule):
    NODE_TYPE = 'bucket'
    COLLECTION_LABEL = _("Bucket")

    def __init__(self, *args, **kwargs):
        self.min_ver = None
        self.max_ver = None

        super().__init__(*args, **kwargs)

    def get_nodes(self, gid, sid):
        """
        Generate the collection node
        """
        if self.show_node:
            yield self.generate_browser_collection_node(sid)

    @property
    def script_load(self):
        """
        Load the module script for bucket, when any of the datasource node is
        initialized.
        """
        return datasource.DataSourceModule.NODE_TYPE

    @property
    def csssnippets(self):
        """
        Returns a snippet of css to include in the page
        """
        snippets = [
            render_template(
                "browser/css/collection.css",
                node_type=self.node_type,
                _=_
            ),
            render_template(
                "buckets/css/bucket.css",
                node_type=self.node_type,
                _=_
            )
        ]

        for submodule in self.submodules:
            snippets.extend(submodule.csssnippets)

        return snippets

    @property
    def module_use_template_javascript(self):
        """
        Returns whether Jinja2 template is used for generating the javascript
        module.
        """
        return False


blueprint = BucketModule(__name__)


class BucketView(NodeView):
    node_type = blueprint.node_type

    parent_ids = [
        {'type': 'int', 'id': 'gid'},
        {'type': 'int', 'id': 'sid'}
    ]
    ids = [
        {'type': 'int', 'id': 'did'}
    ]

    operations = dict({
        'obj': [
            {'get': 'properties', 'delete': 'delete', 'put': 'update'},
            {'get': 'list', 'post': 'create', 'delete': 'delete'}
        ],
        'nodes': [
            {'get': 'node'},
            {'get': 'nodes'}
        ],
        'get_buckets': [
            {'get': 'get_buckets'},
            {'get': 'get_buckets'}
        ],
        'stats': [
            {'get': 'statistics'},
            {'get': 'statistics'}
        ],
        'dependency': [
            {'get': 'dependencies'}
        ],
        'dependent': [
            {'get': 'dependents'}
        ],
        'children': [
            {'get': 'children'}
        ],
    })



    def list(self, gid, sid):

        try:
            response = client('s3').list_buckets()
        except Exception as e:
            return internal_server_error(errormsg=e)
        else:
            return ajax_response(
                    response=response['Buckets'],
                    status=200
                    )



    def get_nodes(self, gid, sid, show_system_templates=False):
        res = []

        db_disp_res = None
        params = None
        if server_node_res and server_node_res.db_res:
            db_disp_res = ", ".join(
                ['%s'] * len(server_node_res.db_res.split(','))
            )
            params = tuple(server_node_res.db_res.split(','))
        SQL = render_template(
            "/".join([self.template_path, 'nodes.sql']),
            last_system_oid=last_system_oid,
            db_restrictions=db_disp_res
        )
        status, rset = self.conn.execute_dict(SQL, params)

        if not status:
            return internal_server_error(errormsg=rset)

        for row in rset['rows']:
            dbname = row['name']
            if self.manager.db == dbname:
                connected = True
                canDrop = canDisConn = False
            else:
                conn = self.manager.connection(dbname, did=row['did'])
                connected = conn.connected()
                canDrop = canDisConn = True

            res.append(
                self.blueprint.generate_browser_node(
                    row['did'],
                    sid,
                    row['name'],
                    icon="icon-bucket-not-connected" if not connected
                    else "pg-icon-bucket",
                    connected=connected,
                    tablespace=row['spcname'],
                    allowConn=row['datallowconn'],
                    canCreate=row['cancreate'],
                    canDisconn=canDisConn,
                    canDrop=canDrop,
                    inode=True if row['datallowconn'] else False
                )
            )

        return res

    def nodes(self, gid, sid):
        res = self.get_nodes(gid, sid)

        return make_json_response(
            data=res,
            status=200
        )

    def get_buckets(self, gid, sid):
        """
        This function is used to get all the buckets irrespective of
        show_system_object flag for templates in create bucket dialog.
        :param gid:
        :param sid:
        :return:
        """
        res = []
        SQL = render_template(
            "/".join([self.template_path, 'nodes.sql']),
            last_system_oid=0,
        )
        status, rset = self.conn.execute_dict(SQL)

        if not status:
            return internal_server_error(errormsg=rset)

        for row in rset['rows']:
            res.append(row['name'])

        return make_json_response(
            data=res,
            status=200
        )

    def node(self, gid, sid, did):
        SQL = render_template(
            "/".join([self.template_path, 'nodes.sql']),
            did=did, conn=self.conn, last_system_oid=0
        )
        status, rset = self.conn.execute_2darray(SQL)

        if not status:
            return internal_server_error(errormsg=rset)

        for row in rset['rows']:
            db = row['name']
            if self.manager.db == db:
                connected = True
            else:
                conn = self.manager.connection(row['name'])
                connected = conn.connected()
            icon_css_class = "pg-icon-bucket"
            if not connected:
                icon_css_class = "icon-bucket-not-connected"
            return make_json_response(
                data=self.blueprint.generate_browser_node(
                    row['did'],
                    sid,
                    row['name'],
                    icon=icon_css_class,
                    connected=connected,
                    spcname=row['spcname'],
                    allowConn=row['datallowconn'],
                    canCreate=row['cancreate']
                ),
                status=200
            )

        return gone(errormsg=_("Could not find the bucket on the server."))

    def properties(self, gid, sid, did):

        SQL = render_template(
            "/".join([self.template_path, 'properties.sql']),
            did=did, conn=self.conn, last_system_oid=0
        )
        status, res = self.conn.execute_dict(SQL)

        if not status:
            return internal_server_error(errormsg=res)

        if len(res['rows']) == 0:
            return gone(
                _("Could not find the bucket on the server.")
            )

        SQL = render_template(
            "/".join([self.template_path, 'acl.sql']),
            did=did, conn=self.conn
        )
        status, dataclres = self.conn.execute_dict(SQL)
        if not status:
            return internal_server_error(errormsg=res)

        res = self.formatdbacl(res, dataclres['rows'])

        SQL = render_template(
            "/".join([self.template_path, 'defacl.sql']),
            did=did, conn=self.conn
        )
        status, defaclres = self.conn.execute_dict(SQL)
        if not status:
            return internal_server_error(errormsg=res)

        res = self.formatdbacl(res, defaclres['rows'])

        result = res['rows'][0]
        # Fetching variable for bucket
        SQL = render_template(
            "/".join([self.template_path, 'get_variables.sql']),
            did=did, conn=self.conn
        )

        status, res1 = self.conn.execute_dict(SQL)

        if not status:
            return internal_server_error(errormsg=res1)

        # Get Formatted Security Labels
        if 'seclabels' in result:
            # Security Labels is not available for PostgreSQL <= 9.1
            frmtd_sec_labels = parse_sec_labels_from_db(result['seclabels'])
            result.update(frmtd_sec_labels)

        # Get Formatted Variables
        frmtd_variables = parse_variables_from_db(res1['rows'])
        result.update(frmtd_variables)

        return ajax_response(
            response=result,
            status=200
        )

    @staticmethod
    def formatdbacl(res, dbacl):
        for row in dbacl:
            priv = parse_priv_from_db(row)
            res['rows'][0].setdefault(row['deftype'], []).append(priv)
        return res


    def get_encodings(self, gid, sid, did=None):
        """
        This function to return list of avialable encodings
        """
        res = [{'label': '', 'value': ''}]
        SQL = render_template(
            "/".join([self.template_path, 'get_encodings.sql'])
        )
        status, rset = self.conn.execute_dict(SQL)
        if not status:
            return internal_server_error(errormsg=rset)

        for row in rset['rows']:
            res.append(
                {'label': row['encoding'], 'value': row['encoding']}
            )

        return make_json_response(
            data=res,
            status=200
        )

    def get_ctypes(self, gid, sid, did=None):
        """
        This function to return list of available collation/character types
        """
        res = [{'label': '', 'value': ''}]
        default_list = ['C', 'POSIX']
        for val in default_list:
            res.append(
                {'label': val, 'value': val}
            )
        SQL = render_template(
            "/".join([self.template_path, 'get_ctypes.sql'])
        )
        status, rset = self.conn.execute_dict(SQL)
        if not status:
            return internal_server_error(errormsg=rset)

        for row in rset['rows']:
            if row['cname'] not in default_list:
                res.append({'label': row['cname'], 'value': row['cname']})

        return make_json_response(
            data=res,
            status=200
        )

    def create(self, gid, sid):
        """Create the bucket."""
        required_args = [
            u'name'
        ]

        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8'
        )

        for arg in required_args:
            if arg not in data:
                return make_json_response(
                    status=410,
                    success=0,
                    errormsg=_(
                        "Could not find the required parameter (%s)." % arg
                    )
                )
        # The below SQL will execute CREATE DDL only
        SQL = render_template(
            "/".join([self.template_path, 'create.sql']),
            data=data, conn=self.conn
        )
        status, msg = self.conn.execute_scalar(SQL)
        if not status:
            return internal_server_error(errormsg=msg)

        if 'datacl' in data:
            data['datacl'] = parse_priv_to_db(data['datacl'], 'DATABASE')

        # The below SQL will execute rest DMLs because we cannot execute
        # CREATE with any other
        SQL = render_template(
            "/".join([self.template_path, 'grant.sql']),
            data=data, conn=self.conn
        )
        SQL = SQL.strip('\n').strip(' ')
        if SQL and SQL != "":
            status, msg = self.conn.execute_scalar(SQL)
            if not status:
                return internal_server_error(errormsg=msg)

        # We need oid of newly created bucket
        SQL = render_template(
            "/".join([self.template_path, 'properties.sql']),
            name=data['name'], conn=self.conn, last_system_oid=0
        )
        SQL = SQL.strip('\n').strip(' ')
        if SQL and SQL != "":
            status, res = self.conn.execute_dict(SQL)
            if not status:
                return internal_server_error(errormsg=res)

        response = res['rows'][0]

        return jsonify(
            node=self.blueprint.generate_browser_node(
                response['did'],
                sid,
                response['name'],
                icon="icon-bucket-not-connected",
                connected=False,
                tablespace=response['default_tablespace'],
                allowConn=True,
                canCreate=response['cancreate'],
                canDisconn=True,
                canDrop=True
            )
        )

    def update(self, gid, sid, did):
        """Update the bucket."""

        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8'
        )

        # Generic connection for offline updates
        conn = self.manager.connection(conn_id='db_offline_update')
        status, errmsg = conn.connect()
        if not status:
            current_app.logger.error(
                "Could not create bucket connection for offline updates\n"
                "Err: {0}".format(errmsg)
            )
            return internal_server_error(errmsg)

        if did is not None:
            # Fetch the name of bucket for comparison
            status, rset = self.conn.execute_dict(
                render_template(
                    "/".join([self.template_path, 'nodes.sql']),
                    did=did, conn=self.conn, last_system_oid=0
                )
            )
            if not status:
                return internal_server_error(errormsg=rset)

            if len(rset['rows']) == 0:
                return gone(
                    _('Could not find the bucket on the server.')
                )

            data['old_name'] = (rset['rows'][0])['name']
            if 'name' not in data:
                data['name'] = data['old_name']

        # Release any existing connection from connection manager
        # to perform offline operation
        self.manager.release(did=did)

        for action in ["rename_bucket", "tablespace"]:
            SQL = self.get_offline_sql(gid, sid, data, did, action)
            SQL = SQL.strip('\n').strip(' ')
            if SQL and SQL != "":
                status, msg = conn.execute_scalar(SQL)
                if not status:
                    # In case of error from server while rename it,
                    # reconnect to the bucket with old name again.
                    self.conn = self.manager.connection(
                        bucket=data['old_name'], auto_reconnect=True
                    )
                    status, errmsg = self.conn.connect()
                    if not status:
                        current_app.logger.error(
                            'Could not reconnected to bucket(#{0}).\n'
                            'Error: {1}'.format(did, errmsg)
                        )
                    return internal_server_error(errormsg=msg)

                QueryHistory.update_history_dbname(
                    current_user.id, sid, data['old_name'], data['name'])
        # Make connection for bucket again
        if self._db['datallowconn']:
            self.conn = self.manager.connection(
                bucket=data['name'], auto_reconnect=True
            )
            status, errmsg = self.conn.connect()

            if not status:
                current_app.logger.error(
                    'Could not connected to bucket(#{0}).\n'
                    'Error: {1}'.format(did, errmsg)
                )
                return internal_server_error(errmsg)

        SQL = self.get_online_sql(gid, sid, data, did)
        SQL = SQL.strip('\n').strip(' ')
        if SQL and SQL != "":
            status, msg = self.conn.execute_scalar(SQL)
            if not status:
                return internal_server_error(errormsg=msg)

        # Release any existing connection from connection manager
        # used for offline updates
        self.manager.release(conn_id="db_offline_update")

        # Fetch the new data again after update for proper node
        # generation
        status, rset = self.conn.execute_dict(
            render_template(
                "/".join([self.template_path, 'nodes.sql']),
                did=did, conn=self.conn, last_system_oid=0
            )
        )
        if not status:
            return internal_server_error(errormsg=rset)

        if len(rset['rows']) == 0:
            return gone(
                _("Could not find the bucket on the server.")
            )

        res = rset['rows'][0]

        canDrop = canDisConn = True
        if self.manager.db == res['name']:
            canDrop = canDisConn = False

        return jsonify(
            node=self.blueprint.generate_browser_node(
                did,
                sid,
                res['name'],
                icon="pg-icon-{0}".format(self.node_type) if
                self._db['datallowconn'] and self.conn.connected() else
                "icon-bucket-not-connected",
                connected=self.conn.connected() if
                self._db['datallowconn'] else False,
                tablespace=res['spcname'],
                allowConn=res['datallowconn'],
                canCreate=res['cancreate'],
                canDisconn=canDisConn,
                canDrop=canDrop,
                inode=True if res['datallowconn'] else False
            )
        )

    def delete(self, gid, sid, did=None):
        """Delete the bucket."""

        if did is None:
            data = request.form if request.form else json.loads(
                request.data, encoding='utf-8'
            )
        else:
            data = {'ids': [did]}

        for did in data['ids']:
            default_conn = self.manager.connection()
            SQL = render_template(
                "/".join([self.template_path, 'delete.sql']),
                did=did, conn=self.conn
            )
            status, res = default_conn.execute_scalar(SQL)
            if not status:
                return internal_server_error(errormsg=res)

            if res is None:
                return make_json_response(
                    status=410,
                    success=0,
                    errormsg=_(
                        'Error: Object not found.'
                    ),
                    info=_(
                        'The specified bucket could not be found.\n'
                    )
                )
            else:

                status = self.manager.release(did=did)

                SQL = render_template(
                    "/".join([self.template_path, 'delete.sql']),
                    datname=res, conn=self.conn
                )

                status, msg = default_conn.execute_scalar(SQL)
                if not status:
                    # reconnect if bucket drop failed.
                    conn = self.manager.connection(did=did,
                                                   auto_reconnect=True)
                    status, errmsg = conn.connect()

                    return internal_server_error(errormsg=msg)

        return make_json_response(success=1)

    def msql(self, gid, sid, did=None):
        """
        This function to return modified SQL.
        """
        data = {}
        for k, v in request.args.items():
            try:
                # comments should be taken as is because if user enters a
                # json comment it is parsed by loads which should not happen
                if k in ('comments',):
                    data[k] = v
                else:
                    data[k] = json.loads(v, encoding='utf-8')
            except ValueError:
                data[k] = v
        status, res = self.get_sql(gid, sid, data, did)

        if not status:
            return res

        res = re.sub('\n{2,}', '\n\n', res)
        SQL = res.strip('\n').strip(' ')

        return make_json_response(
            data=SQL,
            status=200
        )

    def get_sql(self, gid, sid, data, did=None):
        SQL = ''
        if did is not None:
            # Fetch the name of bucket for comparison
            conn = self.manager.connection()
            status, rset = conn.execute_dict(
                render_template(
                    "/".join([self.template_path, 'nodes.sql']),
                    did=did, conn=conn, last_system_oid=0
                )
            )
            if not status:
                return False, internal_server_error(errormsg=rset)

            if len(rset['rows']) == 0:
                return gone(
                    _("Could not find the bucket on the server.")
                )

            data['old_name'] = (rset['rows'][0])['name']
            if 'name' not in data:
                data['name'] = data['old_name']

            SQL = ''
            for action in ["rename_bucket", "tablespace"]:
                SQL += self.get_offline_sql(gid, sid, data, did, action)

            SQL += self.get_online_sql(gid, sid, data, did)
        else:
            SQL += self.get_new_sql(gid, sid, data, did)

        return True, SQL

    def get_new_sql(self, gid, sid, data, did=None):
        """
        Generates sql for creating new bucket.
        """
        required_args = [
            u'name'
        ]

        for arg in required_args:
            if arg not in data:
                return _(" -- definition incomplete")

        acls = []
        SQL_acl = ''

        try:
            acls = render_template(
                "/".join([self.template_path, 'allowed_privs.json'])
            )
            acls = json.loads(acls, encoding='utf-8')
        except Exception as e:
            current_app.logger.exception(e)

        # Privileges
        for aclcol in acls:
            if aclcol in data:
                allowedacl = acls[aclcol]
                data[aclcol] = parse_priv_to_db(
                    data[aclcol], allowedacl['acl']
                )

        SQL_acl = render_template(
            "/".join([self.template_path, 'grant.sql']),
            data=data,
            conn=self.conn
        )

        SQL = render_template(
            "/".join([self.template_path, 'create.sql']),
            data=data, conn=self.conn
        )
        SQL += "\n"
        SQL += SQL_acl
        return SQL

    def get_online_sql(self, gid, sid, data, did=None):
        """
        Generates sql for altering bucket which don not require
        bucket to be disconnected before applying.
        """
        acls = []
        try:
            acls = render_template(
                "/".join([self.template_path, 'allowed_privs.json'])
            )
            acls = json.loads(acls, encoding='utf-8')
        except Exception as e:
            current_app.logger.exception(e)

        # Privileges
        for aclcol in acls:
            if aclcol in data:
                allowedacl = acls[aclcol]

                for key in ['added', 'changed', 'deleted']:
                    if key in data[aclcol]:
                        data[aclcol][key] = parse_priv_to_db(
                            data[aclcol][key], allowedacl['acl']
                        )

        return render_template(
            "/".join([self.template_path, 'alter_online.sql']),
            data=data, conn=self.conn
        )

    def get_offline_sql(self, gid, sid, data, did=None, action=None):
        """
        Generates sql for altering bucket which require
        bucket to be disconnected before applying.
        """

        return render_template(
            "/".join([self.template_path, 'alter_offline.sql']),
            data=data, conn=self.conn, action=action
        )

    def variable_options(self, gid, sid):
        SQL = render_template(
            "/".join([self.template_path, 'variables.sql'])
        )
        status, rset = self.conn.execute_dict(SQL)

        if not status:
            return internal_server_error(errormsg=rset)

        return make_json_response(
            data=rset['rows'],
            status=200
        )

    def statistics(self, gid, sid, did=None):
        """
        statistics
        Returns the statistics for a particular bucket if did is specified,
        otherwise it will return statistics for all the buckets in that
        server.
        """
        last_system_oid = self.retrieve_last_system_oid()

        db_disp_res = None
        params = None
        if self.manager and self.manager.db_res:
            db_disp_res = ", ".join(
                ['%s'] * len(self.manager.db_res.split(','))
            )
            params = tuple(self.manager.db_res.split(','))

        conn = self.manager.connection()
        status, res = conn.execute_dict(render_template(
            "/".join([self.template_path, 'stats.sql']),
            did=did,
            conn=conn,
            last_system_oid=last_system_oid,
            db_restrictions=db_disp_res),
            params
        )

        if not status:
            return internal_server_error(errormsg=res)

        return make_json_response(
            data=res,
            status=200
        )

    def sql(self, gid, sid, did):
        """
        This function will generate sql for sql panel
        """

        conn = self.manager.connection()
        SQL = render_template(
            "/".join([self.template_path, 'properties.sql']),
            did=did, conn=conn, last_system_oid=0
        )
        status, res = conn.execute_dict(SQL)

        if not status:
            return internal_server_error(errormsg=res)

        if len(res['rows']) == 0:
            return gone(
                _("Could not find the bucket on the server.")
            )

        SQL = render_template(
            "/".join([self.template_path, 'acl.sql']),
            did=did, conn=self.conn
        )
        status, dataclres = self.conn.execute_dict(SQL)
        if not status:
            return internal_server_error(errormsg=dataclres)
        res = self.formatdbacl(res, dataclres['rows'])

        SQL = render_template(
            "/".join([self.template_path, 'defacl.sql']),
            did=did, conn=self.conn
        )
        status, defaclres = self.conn.execute_dict(SQL)
        if not status:
            return internal_server_error(errormsg=defaclres)

        res = self.formatdbacl(res, defaclres['rows'])

        result = res['rows'][0]

        SQL = render_template(
            "/".join([self.template_path, 'get_variables.sql']),
            did=did, conn=self.conn
        )
        status, res1 = self.conn.execute_dict(SQL)
        if not status:
            return internal_server_error(errormsg=res1)

        # Get Formatted Security Labels
        if 'seclabels' in result:
            # Security Labels is not available for PostgreSQL <= 9.1
            frmtd_sec_labels = parse_sec_labels_from_db(result['seclabels'])
            result.update(frmtd_sec_labels)

        # Get Formatted Variables
        frmtd_variables = parse_variables_from_db(res1['rows'])
        result.update(frmtd_variables)

        sql_header = u"-- Bucket: {0}\n\n-- ".format(result['name'])

        sql_header += render_template(
            "/".join([self.template_path, 'delete.sql']),
            datname=result['name'], conn=conn
        )

        SQL = self.get_new_sql(gid, sid, result, did)
        SQL = re.sub('\n{2,}', '\n\n', SQL)
        SQL = sql_header + '\n' + SQL
        SQL = SQL.strip('\n')

        return ajax_response(response=SQL)

    def dependents(self, gid, sid, did):
        """
        This function gets the dependents and returns an ajax response
        for the bucket.

        Args:
            gid: DataSource Group ID
            sid: DataSource ID
            did: Bucket ID
        """
        dependents_result = self.get_dependents(self.conn, did) if \
            self.conn.connected() else []
        return ajax_response(
            response=dependents_result,
            status=200
        )

    def dependencies(self, gid, sid, did):
        """
        This function gets the dependencies and returns an ajax response
        for the bucket.

        Args:
            gid: DataSource Group ID
            sid: DataSource ID
            did: Bucket ID
        """
        dependencies_result = self.get_dependencies(self.conn, did) if \
            self.conn.connected() else []
        return ajax_response(
            response=dependencies_result,
            status=200
        )


BucketView.register_node_view(blueprint)
