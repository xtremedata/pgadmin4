##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

import simplejson as json
import re
import pgadmin.browser.datasource_groups as sg
from flask import render_template, request, make_response, jsonify, \
    current_app, url_for
from flask_babelex import gettext
from flask_security import current_user, login_required
from pgadmin.browser.datasource_groups.datasources.types import DataSourceType
from pgadmin.browser.utils import PGChildNodeView
from pgadmin.utils.ajax import make_json_response, bad_request, forbidden, \
    make_response as ajax_response, internal_datasource_error, unauthorized, gone
from pgadmin.utils.crypto import encrypt, decrypt, pqencryptpassword
from pgadmin.utils.menu import MenuItem
from pgadmin.tools.sqleditor.utils.query_history import QueryHistory

import config
from config import PG_DEFAULT_DRIVER
from pgadmin.model import db, DataSource, DataGroup, User
from pgadmin.utils.driver import get_driver
from pgadmin.utils.master_password import get_crypt_key
from pgadmin.utils.exception import CryptKeyMissing
from pgadmin.tools.schema_diff.node_registry import SchemaDiffRegistry
from psycopg2 import Error as psycopg2_Error, OperationalError


def has_any(data, keys):
    """
    Checks any one of the keys present in the data given
    """
    if data is None and type(data) != dict:
        return False

    if keys is None and type(keys) != list:
        return False

    for key in keys:
        if key in data:
            return True

    return False



def datasource_icon_and_background(is_connected, manager, datasource):
    """

    Args:
        is_connected: Flag to check if datasource is connected
        manager: Connection manager
        datasource: Sever object

    Returns:
        DataSource Icon CSS class
    """
    datasource_background_color = ''
    if datasource and datasource.bgcolor:
        datasource_background_color = ' {0}'.format(
            datasource.bgcolor
        )
        # If user has set font color also
        if datasource.fgcolor:
            datasource_background_color = '{0} {1}'.format(
                datasource_background_color,
                datasource.fgcolor
            )

    if is_connected:
        return 'icon-{0}{1}'.format(
            manager.datasource_type, datasource_background_color
        )
    else:
        return 'icon-datasource-not-connected{0}'.format(
            datasource_background_color
        )


class DataSourceModule(sg.DataGroupPluginModule):
    NODE_TYPE = "datasource"
    LABEL = gettext("DataSources")

    @property
    def node_type(self):
        return self.NODE_TYPE

    @property
    def script_load(self):
        """
        Load the module script for datasource, when any of the data-group node is
        initialized.
        """
        return sg.DataGroupModule.NODE_TYPE

    @login_required
    def get_nodes(self, gid):
        """Return a JSON document listing the data groups for the user"""
        datasources = DataSource.query.filter_by(user_id=current_user.id,
                                         datagroup_id=gid)

        driver = get_driver(PG_DEFAULT_DRIVER)

        for datasource in datasources:
            connected = False
            manager = None
            errmsg = None
            was_connected = False
            in_recovery = None
            wal_paused = None
            try:
                manager = driver.connection_manager(datasource.id)
                conn = manager.connection()
                was_connected = conn.wasConnected
            except CryptKeyMissing:
                # show the nodes at least even if not able to connect.
                pass
            except psycopg2_Error as e:
                current_app.logger.exception(e)
                errmsg = str(e)

            yield self.generate_browser_node(
                "%d" % (datasource.id),
                gid,
                datasource.name,
                datasource_icon_and_background(connected, manager, datasource),
                True,
                self.NODE_TYPE,
                connected=connected,
                datasource_type=manager.datasource_type if connected else "pg",
                version=manager.version,
                db=manager.db,
                user=manager.user_info if connected else None,
                in_recovery=in_recovery,
                wal_pause=wal_paused,
                is_password_saved=True if datasource.password is not None
                else False,
                is_tunnel_password_saved=True
                if datasource.tunnel_password is not None else False,
                was_connected=was_connected,
                errmsg=errmsg
            )

    @property
    def jssnippets(self):
        return []

    @property
    def csssnippets(self):
        """
        Returns a snippet of css to include in the page
        """
        snippets = [render_template("css/datasources.css")]

        for submodule in self.submodules:
            snippets.extend(submodule.csssnippets)

        for st in DataSourceType.types():
            snippets.extend(st.csssnippets)

        return snippets

    def get_own_javascripts(self):
        scripts = []

        scripts.extend([{
            'name': 'pgadmin.browser.datasource.privilege',
            'path': url_for('%s.static' % self.name, filename='js/privilege'),
            'when': self.node_type,
            'is_template': False,
            'deps': ['pgadmin.browser.node.ui']
        }, {
            'name': 'pgadmin.browser.datasource.variable',
            'path': url_for('%s.static' % self.name, filename='js/variable'),
            'when': self.node_type,
            'is_template': False
        }, {
            'name': 'pgadmin.datasource.supported_datasources',
            'path': url_for('browser.index') + 'datasource/supported_datasources',
            'is_template': True,
            'when': self.node_type
        }])
        scripts.extend(sg.DataGroupPluginModule.get_own_javascripts(self))

        return scripts

    def register(self, app, options, first_registration=False):
        """
        Override the default register function to automagically register
        sub-modules at once.
        """
        if first_registration:
            driver = get_driver(PG_DEFAULT_DRIVER, app)
            app.jinja_env.filters['qtLiteral'] = driver.qtLiteral
            app.jinja_env.filters['qtIdent'] = driver.qtIdent
            app.jinja_env.filters['qtTypeIdent'] = driver.qtTypeIdent
            app.jinja_env.filters['hasAny'] = has_any

        super(DataSourceModule, self).register(app, options, first_registration)

    # We do not have any preferences for datasource node.
    def register_preferences(self):
        """
        register_preferences
        Override it so that - it does not register the show_node preference for
        datasource type.
        """
        DataSourceType.register_preferences()

    def get_exposed_url_endpoints(self):
        return ['NODE-datasource.connect_id']


class DataSourceMenuItem(MenuItem):
    def __init__(self, **kwargs):
        kwargs.setdefault("type", DataSourceModule.NODE_TYPE)
        super(DataSourceMenuItem, self).__init__(**kwargs)


blueprint = DataSourceModule(__name__)


class DataSourceNode(PGChildNodeView):
    node_type = DataSourceModule.NODE_TYPE

    parent_ids = [{'type': 'int', 'id': 'gid'}]
    ids = [{'type': 'int', 'id': 'sid'}]
    operations = dict({
        'obj': [
            {'get': 'properties', 'delete': 'delete', 'put': 'update'},
            {'get': 'list', 'post': 'create'}
        ],
        'nodes': [{'get': 'node'}, {'get': 'nodes'}],
        'sql': [{'get': 'sql'}],
        'msql': [{'get': 'modified_sql'}],
        'stats': [{'get': 'statistics'}],
        'dependency': [{'get': 'dependencies'}],
        'dependent': [{'get': 'dependents'}],
        'children': [{'get': 'children'}],
        'supported_datasources.js': [{}, {}, {'get': 'supported_datasources'}],
        'reload':
            [{'get': 'reload_configuration'}],
        'restore_point':
            [{'post': 'create_restore_point'}],
        'connect': [{
            'get': 'connect_status', 'post': 'connect', 'delete': 'disconnect'
        }],
        'change_password': [{'post': 'change_password'}],
        'wal_replay': [{
            'delete': 'pause_wal_replay', 'put': 'resume_wal_replay'
        }],
        'check_pgpass': [{'get': 'check_pgpass'}],
        'clear_saved_password': [{'put': 'clear_saved_password'}],
        'clear_sshtunnel_password': [{'put': 'clear_sshtunnel_password'}]
    })
    EXP_IP4 = "^\s*((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\." \
              "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\." \
              "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\." \
              "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?))\s*$"
    EXP_IP6 = '^\s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|' \
              '(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|' \
              '2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d))' \
              '{3})|:))|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|' \
              ':((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d' \
              '|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]' \
              '{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]\d|1\d\d|' \
              '[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|' \
              '(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:[0-9A-' \
              'Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25' \
              '[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:)' \
              '{2}(((:[0-9A-Fa-f]{1,4}){1,5})|((:[0-9A-Fa-f]{1,4}){0,3}:(' \
              '(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|' \
              '[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]' \
              '{1,4}){1,6})|((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\d|'\
              '1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))' \
              '|(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((' \
              '25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|' \
              '[1-9]?\d)){3}))|:)))(%.+)?\s*$'
    pat4 = re.compile(EXP_IP4)
    pat6 = re.compile(EXP_IP6)
    SSL_MODES = ['prefer', 'require', 'verify-ca', 'verify-full']

    def check_ssl_fields(self, data):
        """
        This function will allow us to check and set defaults for
        SSL fields

        Args:
            data: Response data

        Returns:
            Flag and Data
        """
        flag = False

        if 'sslmode' in data and data['sslmode'] in self.SSL_MODES:
            flag = True
            ssl_fields = [
                'sslcert', 'sslkey', 'sslrootcert', 'sslcrl', 'sslcompression'
            ]
            # Required SSL fields for SERVER mode from user
            required_ssl_fields_datasource_mode = ['sslcert', 'sslkey']

            for field in ssl_fields:
                if field not in data:
                    # In DataSource mode,
                    # we will set dummy SSL certificate file path which will
                    # prevent using default SSL certificates from web datasources

                    if config.SERVER_MODE and \
                            field in required_ssl_fields_datasource_mode:
                        # Set file manager directory from preference
                        import os
                        file_extn = '.key' if field.endswith('key') else '.crt'
                        dummy_ssl_file = os.path.join(
                            '<STORAGE_DIR>', '.postgresql',
                            'postgresql' + file_extn
                        )
                        data[field] = dummy_ssl_file
                    # For Desktop mode, we will allow to default
                    else:
                        data[field] = None

        return flag, data

    @login_required
    def nodes(self, gid):
        res = []
        """
        Return a JSON document listing the datasources under this datasource group
        for the user.
        """
        datasources = DataSource.query.filter_by(user_id=current_user.id,
                                         datagroup_id=gid)

        driver = get_driver(PG_DEFAULT_DRIVER)

        for datasource in datasources:
            manager = driver.connection_manager(datasource.id)
            conn = manager.connection()
            connected = conn.connected()
            errmsg = None
            in_recovery = None
            wal_paused = None
            if connected:
                status, result, in_recovery, wal_paused =\
                    recovery_state(conn, manager.version)
                if not status:
                    connected = False
                    manager.release()
                    errmsg = "{0} : {1}".format(datasource.name, result)

            res.append(
                self.blueprint.generate_browser_node(
                    "%d" % (datasource.id),
                    gid,
                    datasource.name,
                    datasource_icon_and_background(connected, manager, datasource),
                    True,
                    self.node_type,
                    connected=connected,
                    datasource_type=manager.datasource_type if connected else 'pg',
                    version=manager.version,
                    db=manager.db,
                    user=manager.user_info if connected else None,
                    in_recovery=in_recovery,
                    wal_pause=wal_paused,
                    is_password_saved=True if datasource.password is not None
                    else False,
                    is_tunnel_password_saved=True
                    if datasource.tunnel_password is not None else False,
                    errmsg=errmsg
                )
            )

        if not len(res):
            return gone(errormsg=gettext(
                'The specified datasource group with id# {0} could not be found.'
            ))

        return make_json_response(result=res)

    @login_required
    def node(self, gid, sid):
        """Return a JSON document listing the datasource groups for the user"""
        datasource = DataSource.query.filter_by(user_id=current_user.id,
                                        datagroup_id=gid,
                                        id=sid).first()

        if datasource is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext(
                    gettext(
                        "Could not find the datasource with id# {0}."
                    ).format(sid)
                )
            )

        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(datasource.id)
        conn = manager.connection()
        connected = conn.connected()
        errmsg = None
        in_recovery = None
        wal_paused = None
        if connected:
            status, result, in_recovery, wal_paused =\
                recovery_state(conn, manager.version)
            if not status:
                connected = False
                manager.release()
                errmsg = "{0} : {1}".format(datasource.name, result)

        return make_json_response(
            result=self.blueprint.generate_browser_node(
                "%d" % (datasource.id),
                gid,
                datasource.name,
                datasource_icon_and_background(connected, manager, datasource),
                True,
                self.node_type,
                connected=connected,
                datasource_type=manager.datasource_type if connected else 'pg',
                version=manager.version,
                db=manager.db,
                user=manager.user_info if connected else None,
                in_recovery=in_recovery,
                wal_pause=wal_paused,
                is_password_saved=True if datasource.password is not None
                else False,
                is_tunnel_password_saved=True
                if datasource.tunnel_password is not None else False,
                errmsg=errmsg
            ),
        )

    @login_required
    def delete(self, gid, sid):
        """Delete a datasource node in the settings database."""
        datasources = DataSource.query.filter_by(user_id=current_user.id, id=sid)

        # TODO:: A datasource, which is connected, cannot be deleted
        if datasources is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext(
                    'The specified datasource could not be found.\n'
                    'Does the user have permission to access the '
                    'datasource?'
                )
            )
        else:
            try:
                for s in datasources:
                    get_driver(PG_DEFAULT_DRIVER).delete_manager(s.id)
                    db.session.delete(s)
                db.session.commit()

                QueryHistory.clear_history(current_user.id, sid)

            except Exception as e:
                current_app.logger.exception(e)
                return make_json_response(
                    success=0,
                    errormsg=e.message)

        return make_json_response(success=1,
                                  info=gettext("DataSource deleted"))

    @login_required
    def update(self, gid, sid):
        """Update the datasource settings"""
        datasource = DataSource.query.filter_by(
            user_id=current_user.id, id=sid).first()

        if datasource is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext("Could not find the required datasource.")
            )

        # Not all parameters can be modified, while the datasource is connected
        config_param_map = {
            'name': 'name',
            'host': 'host',
            'hostaddr': 'hostaddr',
            'port': 'port',
            'db': 'maintenance_db',
            'username': 'username',
            'sslmode': 'ssl_mode',
            'gid': 'datagroup_id',
            'comment': 'comment',
            'role': 'role',
            'db_res': 'db_res',
            'passfile': 'passfile',
            'sslcert': 'sslcert',
            'sslkey': 'sslkey',
            'sslrootcert': 'sslrootcert',
            'sslcrl': 'sslcrl',
            'sslcompression': 'sslcompression',
            'bgcolor': 'bgcolor',
            'fgcolor': 'fgcolor',
            'service': 'service',
            'connect_timeout': 'connect_timeout',
            'use_ssh_tunnel': 'use_ssh_tunnel',
            'tunnel_host': 'tunnel_host',
            'tunnel_port': 'tunnel_port',
            'tunnel_username': 'tunnel_username',
            'tunnel_authentication': 'tunnel_authentication',
            'tunnel_identity_file': 'tunnel_identity_file',
        }

        disp_lbl = {
            'name': gettext('name'),
            'host': gettext('Host name/address'),
            'port': gettext('Port'),
            'db': gettext('Maintenance database'),
            'username': gettext('Username'),
            'sslmode': gettext('SSL Mode'),
            'comment': gettext('Comments'),
            'role': gettext('Role')
        }

        idx = 0
        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8'
        )
        if 'db_res' in data:
            data['db_res'] = ','.join(data['db_res'])

        if 'hostaddr' in data and data['hostaddr'] and data['hostaddr'] != '':
            if not self.pat4.match(data['hostaddr']):
                if not self.pat6.match(data['hostaddr']):
                    return make_json_response(
                        success=0,
                        status=400,
                        errormsg=gettext('Host address not valid')
                    )

        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
        conn = manager.connection()
        connected = conn.connected()

        if connected:
            for arg in (
                    'host', 'hostaddr', 'port', 'db', 'username', 'sslmode',
                    'role', 'service'
            ):
                if arg in data:
                    return forbidden(
                        errormsg=gettext(
                            "'{0}' is not allowed to modify, "
                            "when datasource is connected."
                        ).format(disp_lbl[arg])
                    )

        for arg in config_param_map:
            if arg in data:
                value = data[arg]
                # sqlite3 do not have boolean type so we need to convert
                # it manually to integer
                if arg == 'sslcompression':
                    value = 1 if value else 0
                setattr(datasource, config_param_map[arg], value)
                idx += 1

        if idx == 0:
            return make_json_response(
                success=0,
                errormsg=gettext('No parameters were changed.')
            )

        try:
            db.session.commit()
        except Exception as e:
            current_app.logger.exception(e)
            return make_json_response(
                success=0,
                errormsg=e.message
            )

        # When datasource is connected, we don't require to update the connection
        # manager. Because - we don't allow to change any of the parameters,
        # which will affect the connections.
        if not conn.connected():
            manager.update(datasource)

        return jsonify(
            node=self.blueprint.generate_browser_node(
                "%d" % (datasource.id), datasource.datagroup_id,
                datasource.name,
                datasource_icon_and_background(connected, manager, datasource),
                True,
                self.node_type,
                connected=connected,
                user=manager.user_info if connected else None,
                datasource_type='pg'  # default datasource type
            )
        )

    @login_required
    def list(self, gid):
        """
        Return list of attributes of all datasources.
        """
        datasources = DataSource.query.filter_by(
            user_id=current_user.id,
            datagroup_id=gid).order_by(DataSource.name)
        sg = DataGroup.query.filter_by(
            user_id=current_user.id,
            id=gid
        ).first()
        res = []

        driver = get_driver(PG_DEFAULT_DRIVER)

        for datasource in datasources:
            manager = driver.connection_manager(datasource.id)
            conn = manager.connection()
            connected = conn.connected()

            res.append({
                'id': datasource.id,
                'name': datasource.name,
                'host': datasource.host,
                'port': datasource.port,
                'db': datasource.maintenance_db,
                'username': datasource.username,
                'gid': datasource.datagroup_id,
                'group-name': sg.name,
                'comment': datasource.comment,
                'role': datasource.role,
                'connected': connected,
                'version': manager.ver,
                'datasource_type': manager.datasource_type if connected else 'pg',
                'db_res': datasource.db_res.split(',') if datasource.db_res else None
            })

        return ajax_response(
            response=res
        )

    @login_required
    def properties(self, gid, sid):
        """Return list of attributes of a datasource"""
        datasource = DataSource.query.filter_by(
            user_id=current_user.id,
            id=sid).first()

        if datasource is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext("Could not find the required datasource.")
            )

        sg = DataGroup.query.filter_by(
            user_id=current_user.id,
            id=datasource.datagroup_id
        ).first()

        driver = get_driver(PG_DEFAULT_DRIVER)

        manager = driver.connection_manager(sid)
        conn = manager.connection()
        connected = conn.connected()

        is_ssl = True if datasource.ssl_mode in self.SSL_MODES else False

        return ajax_response(
            response={
                'id': datasource.id,
                'name': datasource.name,
                'host': datasource.host,
                'hostaddr': datasource.hostaddr,
                'port': datasource.port,
                'db': datasource.maintenance_db,
                'username': datasource.username,
                'gid': str(datasource.datagroup_id),
                'group-name': sg.name,
                'comment': datasource.comment,
                'role': datasource.role,
                'connected': connected,
                'version': manager.ver,
                'sslmode': datasource.ssl_mode,
                'datasource_type': manager.datasource_type if connected else 'pg',
                'bgcolor': datasource.bgcolor,
                'fgcolor': datasource.fgcolor,
                'db_res': datasource.db_res.split(',') if datasource.db_res else None,
                'passfile': datasource.passfile if datasource.passfile else None,
                'sslcert': datasource.sslcert if is_ssl else None,
                'sslkey': datasource.sslkey if is_ssl else None,
                'sslrootcert': datasource.sslrootcert if is_ssl else None,
                'sslcrl': datasource.sslcrl if is_ssl else None,
                'sslcompression': True if is_ssl and datasource.sslcompression
                else False,
                'service': datasource.service if datasource.service else None,
                'connect_timeout':
                    datasource.connect_timeout if datasource.connect_timeout else 0,
                'use_ssh_tunnel': datasource.use_ssh_tunnel
                if datasource.use_ssh_tunnel else 0,
                'tunnel_host': datasource.tunnel_host if datasource.tunnel_host
                else None,
                'tunnel_port': datasource.tunnel_port if datasource.tunnel_port
                else 22,
                'tunnel_username': datasource.tunnel_username
                if datasource.tunnel_username else None,
                'tunnel_identity_file': datasource.tunnel_identity_file
                if datasource.tunnel_identity_file else None,
                'tunnel_authentication': datasource.tunnel_authentication
                if datasource.tunnel_authentication else 0
            }
        )

    @login_required
    def create(self, gid):
        """Add a datasource node to the settings database"""
        required_args = [
            u'name',
            u'db',
            u'sslmode',
        ]

        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8'
        )

        # Get enc key
        crypt_key_present, crypt_key = get_crypt_key()
        if not crypt_key_present:
            raise CryptKeyMissing

        # Some fields can be provided with service file so they are optional
        if 'service' in data and not data['service']:
            required_args.extend([
                u'host',
                u'port',
                u'username',
                u'role'
            ])
        for arg in required_args:
            if arg not in data:
                return make_json_response(
                    status=410,
                    success=0,
                    errormsg=gettext(
                        "Could not find the required parameter (%s)." % arg
                    )
                )

        if 'hostaddr' in data and data['hostaddr'] and data['hostaddr'] != '':
            if not self.pat4.match(data['hostaddr']):
                if not self.pat6.match(data['hostaddr']):
                    return make_json_response(
                        success=0,
                        status=400,
                        errormsg=gettext('Host address not valid')
                    )

        # To check ssl configuration
        is_ssl, data = self.check_ssl_fields(data)

        datasource = None

        try:
            datasource = DataSource(
                user_id=current_user.id,
                datagroup_id=data.get('gid', gid),
                name=data.get('name'),
                host=data.get('host', None),
                hostaddr=data.get('hostaddr', None),
                port=data.get('port'),
                maintenance_db=data.get('db', None),
                username=data.get('username'),
                ssl_mode=data.get('sslmode'),
                comment=data.get('comment', None),
                role=data.get('role', None),
                db_res=','.join(data[u'db_res'])
                if u'db_res' in data else None,
                sslcert=data.get('sslcert', None),
                sslkey=data.get('sslkey', None),
                sslrootcert=data.get('sslrootcert', None),
                sslcrl=data.get('sslcrl', None),
                sslcompression=1 if is_ssl and data['sslcompression'] else 0,
                bgcolor=data.get('bgcolor', None),
                fgcolor=data.get('fgcolor', None),
                service=data.get('service', None),
                connect_timeout=data.get('connect_timeout', 0),
                use_ssh_tunnel=data.get('use_ssh_tunnel', 0),
                tunnel_host=data.get('tunnel_host', None),
                tunnel_port=data.get('tunnel_port', 22),
                tunnel_username=data.get('tunnel_username', None),
                tunnel_authentication=data.get('tunnel_authentication', 0),
                tunnel_identity_file=data.get('tunnel_identity_file', None)
            )
            db.session.add(datasource)
            db.session.commit()

            connected = False
            user = None
            manager = None

            if 'connect_now' in data and data['connect_now']:
                manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(
                    datasource.id)
                manager.update(datasource)
                conn = manager.connection()

                have_password = False
                have_tunnel_password = False
                password = None
                passfile = None
                tunnel_password = ''
                if 'password' in data and data["password"] != '':
                    # login with password
                    have_password = True
                    password = data['password']
                    password = encrypt(password, crypt_key)
                elif 'passfile' in data and data["passfile"] != '':
                    passfile = data['passfile']
                    setattr(datasource, 'passfile', passfile)
                    db.session.commit()

                if 'tunnel_password' in data and data["tunnel_password"] != '':
                    have_tunnel_password = True
                    tunnel_password = data['tunnel_password']
                    tunnel_password = \
                        encrypt(tunnel_password, crypt_key)

                status, errmsg = conn.connect(
                    password=password,
                    passfile=passfile,
                    tunnel_password=tunnel_password,
                    datasource_types=DataSourceType.types()
                )
                if hasattr(str, 'decode') and errmsg is not None:
                    errmsg = errmsg.decode('utf-8')
                if not status:
                    db.session.delete(datasource)
                    db.session.commit()
                    return make_json_response(
                        status=401,
                        success=0,
                        errormsg=gettext(
                            u"Unable to connect to datasource:\n\n%s" % errmsg)
                    )
                else:
                    if 'save_password' in data and data['save_password'] and \
                            have_password and config.ALLOW_SAVE_PASSWORD:
                        setattr(datasource, 'password', password)
                        db.session.commit()

                    if 'save_tunnel_password' in data and \
                        data['save_tunnel_password'] and \
                        have_tunnel_password and \
                            config.ALLOW_SAVE_TUNNEL_PASSWORD:
                        setattr(datasource, 'tunnel_password', tunnel_password)
                        db.session.commit()

                    user = manager.user_info
                    connected = True

            return jsonify(
                node=self.blueprint.generate_browser_node(
                    "%d" % datasource.id, datasource.datagroup_id,
                    datasource.name,
                    datasource_icon_and_background(connected, manager, datasource),
                    True,
                    self.node_type,
                    user=user,
                    connected=connected,
                    datasource_type=manager.datasource_type
                    if manager and manager.datasource_type
                    else 'pg'
                )
            )

        except Exception as e:
            if datasource:
                db.session.delete(datasource)
                db.session.commit()

            current_app.logger.exception(e)
            return make_json_response(
                status=410,
                success=0,
                errormsg=str(e)
            )

    @login_required
    def sql(self, gid, sid):
        return make_json_response(data='')

    @login_required
    def modified_sql(self, gid, sid):
        return make_json_response(data='')

    @login_required
    def statistics(self, gid, sid):
        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
        conn = manager.connection()

        if conn.connected():
            status, res = conn.execute_dict(
                render_template(
                    "/datasources/sql/#{0}#/stats.sql".format(manager.version),
                    conn=conn, _=gettext
                )
            )

            if not status:
                return internal_datasource_error(errormsg=res)

            return make_json_response(data=res)

        return make_json_response(
            info=gettext(
                "DataSource has no active connection for generating statistics."
            )
        )

    @login_required
    def dependencies(self, gid, sid):
        return make_json_response(data='')

    @login_required
    def dependents(self, gid, sid):
        return make_json_response(data='')

    def supported_datasources(self, **kwargs):
        """
        This property defines (if javascript) exists for this node.
        Override this property for your own logic.
        """

        return make_response(
            render_template(
                "datasources/supported_datasources.js",
                datasource_types=DataSourceType.types()
            ),
            200, {'Content-Type': 'application/javascript'}
        )

    def connect_status(self, gid, sid):
        """Check and return the connection status."""
        datasource = DataSource.query.filter_by(id=sid).first()
        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
        conn = manager.connection()
        connected = conn.connected()
        in_recovery = None
        wal_paused = None
        errmsg = None
        if connected:
            status, result, in_recovery, wal_paused =\
                recovery_state(conn, manager.version)

            if not status:
                connected = False
                manager.release()
                errmsg = "{0} : {1}".format(datasource.name, result)

        return make_json_response(
            data={
                'icon': datasource_icon_and_background(connected, manager, datasource),
                'connected': connected,
                'in_recovery': in_recovery,
                'wal_pause': wal_paused,
                'datasource_type': manager.datasource_type if connected else "pg",
                'user': manager.user_info if connected else None,
                'errmsg': errmsg
            }
        )

    def connect(self, gid, sid):
        """
        Connect the DataSource and return the connection object.
        Verification Process before Connection:
            Verify requested datasource.

            Check the datasource password is already been stored in the
            database or not.
            If Yes, connect the datasource and return connection.
            If No, Raise HTTP error and ask for the password.

            In case of 'Save Password' request from user, excrypted Pasword
            will be stored in the respected datasource database and
            establish the connection OR just connect the datasource and do not
            store the password.
        """
        current_app.logger.info(
            'Connection Request for datasource#{0}'.format(sid)
        )

        # Fetch DataSource Details
        datasource = DataSource.query.filter_by(id=sid).first()
        if datasource is None:
            return bad_request(gettext("DataSource not found."))

        if current_user and hasattr(current_user, 'id'):
            # Fetch User Details.
            user = User.query.filter_by(id=current_user.id).first()
            if user is None:
                return unauthorized(gettext("Unauthorized request."))
        else:
            return unauthorized(gettext("Unauthorized request."))

        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8'
        ) if request.data else {}

        password = None
        passfile = None
        tunnel_password = None
        save_password = False
        save_tunnel_password = False
        prompt_password = False
        prompt_tunnel_password = False

        # Connect the DataSource
        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
        conn = manager.connection()

        # Get enc key
        crypt_key_present, crypt_key = get_crypt_key()
        if not crypt_key_present:
            raise CryptKeyMissing

        # If datasource using SSH Tunnel
        if datasource.use_ssh_tunnel:
            if 'tunnel_password' not in data:
                if datasource.tunnel_password is None:
                    prompt_tunnel_password = True
                else:
                    tunnel_password = datasource.tunnel_password
            else:
                tunnel_password = data['tunnel_password'] \
                    if 'tunnel_password'in data else ''
                save_tunnel_password = data['save_tunnel_password'] \
                    if tunnel_password and 'save_tunnel_password' in data \
                    else False
                # Encrypt the password before saving with user's login
                # password key.
                try:
                    tunnel_password = encrypt(tunnel_password, crypt_key) \
                        if tunnel_password is not None else \
                        datasource.tunnel_password
                except Exception as e:
                    current_app.logger.exception(e)
                    return internal_datasource_error(errormsg=str(e))

        if 'password' not in data:
            conn_passwd = getattr(conn, 'password', None)
            if conn_passwd is None and datasource.password is None and \
                    datasource.passfile is None and datasource.service is None:
                prompt_password = True
            elif datasource.passfile and datasource.passfile != '':
                passfile = datasource.passfile
            else:
                password = conn_passwd or datasource.password
        else:
            password = data['password'] if 'password' in data else None
            save_password = data['save_password']\
                if password and 'save_password' in data else False

            # Encrypt the password before saving with user's login
            # password key.
            try:
                password = encrypt(password, crypt_key) \
                    if password is not None else datasource.password
            except Exception as e:
                current_app.logger.exception(e)
                return internal_datasource_error(errormsg=str(e))

        # Check do we need to prompt for the database datasource or ssh tunnel
        # password or both. Return the password template in case password is
        # not provided, or password has not been saved earlier.
        if prompt_password or prompt_tunnel_password:
            return self.get_response_for_password(datasource, 428, prompt_password,
                                                  prompt_tunnel_password)

        status = True
        try:
            status, errmsg = conn.connect(
                password=password,
                passfile=passfile,
                tunnel_password=tunnel_password,
                datasource_types=DataSourceType.types()
            )
        except OperationalError as e:
            return internal_datasource_error(errormsg=str(e))
        except Exception as e:
            current_app.logger.exception(e)
            return self.get_response_for_password(
                datasource, 401, True, True, getattr(e, 'message', str(e)))

        if not status:
            if hasattr(str, 'decode'):
                errmsg = errmsg.decode('utf-8')

            current_app.logger.error(
                "Could not connect to datasource(#{0}) - '{1}'.\nError: {2}"
                .format(datasource.id, datasource.name, errmsg)
            )
            return self.get_response_for_password(datasource, 401, True,
                                                  True, errmsg)
        else:
            if save_password and config.ALLOW_SAVE_PASSWORD:
                try:
                    # Save the encrypted password using the user's login
                    # password key.
                    setattr(datasource, 'password', password)
                    db.session.commit()
                except Exception as e:
                    # Release Connection
                    current_app.logger.exception(e)
                    manager.release(database=datasource.maintenance_db)
                    conn = None

                    return internal_datasource_error(errormsg=e.message)

            if save_tunnel_password and config.ALLOW_SAVE_TUNNEL_PASSWORD:
                try:
                    # Save the encrypted tunnel password.
                    setattr(datasource, 'tunnel_password', tunnel_password)
                    db.session.commit()
                except Exception as e:
                    # Release Connection
                    current_app.logger.exception(e)
                    manager.release(database=datasource.maintenance_db)
                    conn = None

                    return internal_datasource_error(errormsg=e.message)

            current_app.logger.info('Connection Established for datasource: \
                %s - %s' % (datasource.id, datasource.name))
            # Update the recovery and wal pause option for the datasource
            # if connected successfully
            _, _, in_recovery, wal_paused =\
                recovery_state(conn, manager.version)

            return make_json_response(
                success=1,
                info=gettext("DataSource connected."),
                data={
                    'icon': datasource_icon_and_background(True, manager, datasource),
                    'connected': True,
                    'datasource_type': manager.datasource_type,
                    'type': manager.datasource_type,
                    'version': manager.version,
                    'db': manager.db,
                    'user': manager.user_info,
                    'in_recovery': in_recovery,
                    'wal_pause': wal_paused,
                    'is_password_saved': True if datasource.password is not None
                    else False,
                    'is_tunnel_password_saved': True
                    if datasource.tunnel_password is not None else False,
                }
            )

    def disconnect(self, gid, sid):
        """Disconnect the DataSource."""

        datasource = DataSource.query.filter_by(id=sid).first()
        if datasource is None:
            return bad_request(gettext("DataSource not found."))

        # Release Connection
        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)

        status = manager.release()

        if not status:
            return unauthorized(gettext("DataSource could not be disconnected."))
        else:
            return make_json_response(
                success=1,
                info=gettext("DataSource disconnected."),
                data={
                    'icon': datasource_icon_and_background(False, manager, datasource),
                    'connected': False
                }
            )

    def reload_configuration(self, gid, sid):
        """Reload the datasource configuration"""

        # Reload the datasource configurations
        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
        conn = manager.connection()

        if conn.connected():
            # Execute the command for reload configuration for the datasource
            status, rid = conn.execute_scalar("SELECT pg_reload_conf();")

            if not status:
                return internal_datasource_error(
                    gettext("Could not reload the datasource configuration.")
                )
            else:
                return make_json_response(data={
                    'status': True,
                    'result': gettext('DataSource configuration reloaded.')
                })

        else:
            return make_json_response(data={
                'status': False,
                'result': gettext(
                    'Not connected to the datasource or the connection to the'
                    ' datasource has been closed.')})

    def create_restore_point(self, gid, sid):
        """
        This method will creates named restore point

        Args:
            gid: DataSource group ID
            sid: DataSource ID

        Returns:
            None
        """
        try:
            data = request.form
            restore_point_name = data['value'] if data else None
            manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
            conn = manager.connection()

            # Execute SQL to create named restore point
            if conn.connected():
                if restore_point_name:
                    status, res = conn.execute_scalar(
                        "SELECT pg_create_restore_point('{0}');".format(
                            restore_point_name
                        )
                    )
                if not status:
                    return internal_datasource_error(
                        errormsg=str(res)
                    )

                return make_json_response(
                    data={
                        'status': 1,
                        'result': gettext(
                            'Named restore point created: {0}'.format(
                                restore_point_name))
                    })

        except Exception as e:
            current_app.logger.error(
                'Named restore point creation failed ({0})'.format(str(e))
            )
            return internal_datasource_error(errormsg=str(e))

    def change_password(self, gid, sid):
        """
        This function is used to change the password of the
        Database DataSource.

        Args:
            gid: Group id
            sid: DataSource id
        """
        try:
            data = json.loads(request.form['data'], encoding='utf-8')
            crypt_key = get_crypt_key()[1]

            # Fetch DataSource Details
            datasource = DataSource.query.filter_by(id=sid).first()
            if datasource is None:
                return bad_request(gettext("DataSource not found."))

            # Fetch User Details.
            user = User.query.filter_by(id=current_user.id).first()
            if user is None:
                return unauthorized(gettext("Unauthorized request."))

            manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
            conn = manager.connection()
            is_passfile = False

            # If there is no password found for the datasource
            # then check for pgpass file
            if not datasource.password and not manager.password:
                if datasource.passfile and \
                        manager.passfile and \
                        datasource.passfile == manager.passfile:
                    is_passfile = True

            # Check for password only if there is no pgpass file used
            if not is_passfile:
                if data and ('password' not in data or data['password'] == ''):
                    return make_json_response(
                        status=400,
                        success=0,
                        errormsg=gettext(
                            "Could not find the required parameter(s)."
                        )
                    )

            if data and ('newPassword' not in data or
                         data['newPassword'] == '' or
                         'confirmPassword' not in data or
                         data['confirmPassword'] == ''):
                return make_json_response(
                    status=400,
                    success=0,
                    errormsg=gettext(
                        "Could not find the required parameter(s)."
                    )
                )

            if data['newPassword'] != data['confirmPassword']:
                return make_json_response(
                    status=200,
                    success=0,
                    errormsg=gettext(
                        "Passwords do not match."
                    )
                )

            # Check against old password only if no pgpass file
            if not is_passfile:
                decrypted_password = decrypt(manager.password, crypt_key)

                if isinstance(decrypted_password, bytes):
                    decrypted_password = decrypted_password.decode()

                password = data['password']

                # Validate old password before setting new.
                if password != decrypted_password:
                    return unauthorized(gettext("Incorrect password."))

            # Hash new password before saving it.
            if manager.sversion >= 100000:
                password = conn.pq_encrypt_password_conn(data['newPassword'],
                                                         manager.user)
                if password is None:
                    # Unable to encrypt the password so used the
                    # old method of encryption
                    password = pqencryptpassword(data['newPassword'],
                                                 manager.user)
            else:
                password = pqencryptpassword(data['newPassword'], manager.user)

            SQL = render_template(
                "/datasources/sql/#{0}#/change_password.sql".format(
                    manager.version),
                conn=conn, _=gettext,
                user=manager.user, encrypted_password=password)

            status, res = conn.execute_scalar(SQL)

            if not status:
                return internal_datasource_error(errormsg=res)

            # Store password in sqlite only if no pgpass file
            if not is_passfile:
                password = encrypt(data['newPassword'], crypt_key)
                # Check if old password was stored in pgadmin4 sqlite database.
                # If yes then update that password.
                if datasource.password is not None and config.ALLOW_SAVE_PASSWORD:
                    setattr(datasource, 'password', password)
                    db.session.commit()
                # Also update password in connection manager.
                manager.password = password
                manager.update_session()

            return make_json_response(
                status=200,
                success=1,
                info=gettext(
                    "Password changed successfully."
                )
            )

        except Exception as e:
            return internal_datasource_error(errormsg=str(e))

    def wal_replay(self, sid, pause=True):
        """
        Utility function for wal_replay for resume/pause.
        """
        datasource = DataSource.query.filter_by(
            user_id=current_user.id, id=sid
        ).first()

        if datasource is None:
            return make_json_response(
                success=0,
                errormsg=gettext("Could not find the required datasource.")
            )

        try:
            manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
            conn = manager.connection()

            # Execute SQL to pause or resume WAL replay
            if conn.connected():
                if pause:
                    sql = "SELECT pg_xlog_replay_pause();"
                    if manager.version >= 100000:
                        sql = "SELECT pg_wal_replay_pause();"

                    status, res = conn.execute_scalar(sql)
                    if not status:
                        return internal_datasource_error(
                            errormsg=str(res)
                        )
                else:
                    sql = "SELECT pg_xlog_replay_resume();"
                    if manager.version >= 100000:
                        sql = "SELECT pg_wal_replay_resume();"

                    status, res = conn.execute_scalar(sql)
                    if not status:
                        return internal_datasource_error(
                            errormsg=str(res)
                        )
                return make_json_response(
                    success=1,
                    info=gettext('WAL replay paused'),
                    data={'in_recovery': True, 'wal_pause': pause}
                )
            return gone(errormsg=_('Please connect the datasource.'))
        except Exception as e:
            current_app.logger.error(
                'WAL replay pause/resume failed'
            )
            return internal_datasource_error(errormsg=str(e))

    def resume_wal_replay(self, gid, sid):
        """
        This method will resume WAL replay

        Args:
            gid: DataSource group ID
            sid: DataSource ID

        Returns:
            None
        """
        return self.wal_replay(sid, False)

    def pause_wal_replay(self, gid, sid):
        """
        This method will pause WAL replay

        Args:
            gid: DataSource group ID
            sid: DataSource ID

        Returns:
            None
        """
        return self.wal_replay(sid, True)

    def check_pgpass(self, gid, sid):
        """
        This function is used to check whether datasource is connected
        using pgpass file or not

        Args:
            gid: Group id
            sid: DataSource id
        """
        is_pgpass = False
        datasource = DataSource.query.filter_by(
            user_id=current_user.id, id=sid
        ).first()

        if datasource is None:
            return make_json_response(
                success=0,
                errormsg=gettext("Could not find the required datasource.")
            )

        try:
            manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
            conn = manager.connection()
            if not conn.connected():
                return gone(
                    errormsg=_('Please connect the datasource.')
                )

            if not datasource.password or not manager.password:
                if datasource.passfile and \
                        manager.passfile and \
                        datasource.passfile == manager.passfile:
                    is_pgpass = True
            return make_json_response(
                success=1,
                data=dict({'is_pgpass': is_pgpass}),
            )
        except Exception as e:
            current_app.logger.error(
                'Cannot able to fetch pgpass status'
            )
            return internal_datasource_error(errormsg=str(e))

    def get_response_for_password(self, datasource, status, prompt_password=False,
                                  prompt_tunnel_password=False, errmsg=None):

        if datasource.use_ssh_tunnel:
            return make_json_response(
                success=0,
                status=status,
                result=render_template(
                    'datasources/tunnel_password.html',
                    datasource_label=datasource.name,
                    username=datasource.username,
                    tunnel_username=datasource.tunnel_username,
                    tunnel_host=datasource.tunnel_host,
                    tunnel_identity_file=datasource.tunnel_identity_file,
                    errmsg=errmsg,
                    _=gettext,
                    prompt_tunnel_password=prompt_tunnel_password,
                    prompt_password=prompt_password
                )
            )
        else:
            return make_json_response(
                success=0,
                status=status,
                result=render_template(
                    'datasources/password.html',
                    datasource_label=datasource.name,
                    username=datasource.username,
                    errmsg=errmsg,
                    _=gettext,
                )
            )

    def clear_saved_password(self, gid, sid):
        """
        This function is used to remove database datasource password stored into
        the pgAdmin's db file.

        :param gid:
        :param sid:
        :return:
        """
        try:
            datasource = DataSource.query.filter_by(
                user_id=current_user.id, id=sid
            ).first()

            if datasource is None:
                return make_json_response(
                    success=0,
                    info=gettext("Could not find the required datasource.")
                )

            setattr(datasource, 'password', None)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(
                "Unable to clear saved password.\nError: {0}".format(str(e))
            )

            return internal_datasource_error(errormsg=str(e))

        return make_json_response(
            success=1,
            info=gettext("The saved password cleared successfully."),
            data={'is_password_saved': False}
        )

    def clear_sshtunnel_password(self, gid, sid):
        """
        This function is used to remove sshtunnel password stored into
        the pgAdmin's db file.

        :param gid:
        :param sid:
        :return:
        """
        try:
            datasource = DataSource.query.filter_by(
                user_id=current_user.id, id=sid
            ).first()

            if datasource is None:
                return make_json_response(
                    success=0,
                    info=gettext("Could not find the required datasource.")
                )

            setattr(datasource, 'tunnel_password', None)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(
                "Unable to clear ssh tunnel password."
                "\nError: {0}".format(str(e))
            )

            return internal_datasource_error(errormsg=str(e))

        return make_json_response(
            success=1,
            info=gettext("The saved password cleared successfully."),
            data={'is_tunnel_password_saved': False}
        )


SchemaDiffRegistry(blueprint.node_type, DataSourceNode)
DataSourceNode.register_node_view(blueprint)



class DataModule(sg.DataGroupPluginModule):
    NODE_TYPE = "datasource"
    LABEL = gettext("Datas")

    @property
    def node_type(self):
        return self.NODE_TYPE

    @property
    def script_load(self):
        """
        Load the module script for datasource, when any of the datasource-group node is
        initialized.
        """
        return sg.DataGroupModule.NODE_TYPE

    @login_required
    def get_nodes(self, gid):
        """Return a JSON document listing the datasource groups for the user"""
        datasources = DataSource.query.filter_by(user_id=current_user.id,
                                         datagroup_id=gid)

        driver = get_driver(PG_DEFAULT_DRIVER)

        for datasource in datasources:
            connected = False
            manager = None
            errmsg = None
            was_connected = False
            in_recovery = None
            wal_paused = None
            try:
                manager = driver.connection_manager(datasource.id)
                conn = manager.connection()
                was_connected = conn.wasConnected
            except CryptKeyMissing:
                # show the nodes at least even if not able to connect.
                pass
            except psycopg2_Error as e:
                current_app.logger.exception(e)
                errmsg = str(e)

            yield self.generate_browser_node(
                "%d" % (datasource.id),
                gid,
                datasource.name,
                datasource_icon_and_background(connected, manager, datasource),
                True,
                self.NODE_TYPE,
                connected=connected,
                datasource_type=manager.datasource_type if connected else "pg",
                version=manager.version,
                db=manager.db,
                user=manager.user_info if connected else None,
                in_recovery=in_recovery,
                wal_pause=wal_paused,
                is_password_saved=True if datasource.password is not None
                else False,
                is_tunnel_password_saved=True
                if datasource.tunnel_password is not None else False,
                was_connected=was_connected,
                errmsg=errmsg
            )

    @property
    def jssnippets(self):
        return []

    @property
    def csssnippets(self):
        """
        Returns a snippet of css to include in the page
        """
        snippets = [render_template("css/datasources.css")]

        for submodule in self.submodules:
            snippets.extend(submodule.csssnippets)

        for st in DataSourceType.types():
            snippets.extend(st.csssnippets)

        return snippets

    def get_own_javascripts(self):
        scripts = []

        scripts.extend([{
            'name': 'pgadmin.browser.datasource.privilege',
            'path': url_for('%s.static' % self.name, filename='js/privilege'),
            'when': self.node_type,
            'is_template': False,
            'deps': ['pgadmin.browser.node.ui']
        }, {
            'name': 'pgadmin.browser.datasource.variable',
            'path': url_for('%s.static' % self.name, filename='js/variable'),
            'when': self.node_type,
            'is_template': False
        }, {
            'name': 'pgadmin.datasource.supported_datasources',
            'path': url_for('browser.index') + 'datasource/supported_datasources',
            'is_template': True,
            'when': self.node_type
        }])
        scripts.extend(sg.DataGroupPluginModule.get_own_javascripts(self))

        return scripts

    def register(self, app, options, first_registration=False):
        """
        Override the default register function to automagically register
        sub-modules at once.
        """
        if first_registration:
            driver = get_driver(PG_DEFAULT_DRIVER, app)
            app.jinja_env.filters['qtLiteral'] = driver.qtLiteral
            app.jinja_env.filters['qtIdent'] = driver.qtIdent
            app.jinja_env.filters['qtTypeIdent'] = driver.qtTypeIdent
            app.jinja_env.filters['hasAny'] = has_any

        super(DataModule, self).register(app, options, first_registration)

    # We do not have any preferences for datasource node.
    def register_preferences(self):
        """
        register_preferences
        Override it so that - it does not register the show_node preference for
        datasource type.
        """
        DataSourceType.register_preferences()

    def get_exposed_url_endpoints(self):
        return ['NODE-datasource.connect_id']


class DataMenuItem(MenuItem):
    def __init__(self, **kwargs):
        kwargs.setdefault("type", DataModule.NODE_TYPE)
        super(DataMenuItem, self).__init__(**kwargs)


blueprint = DataModule(__name__)


class DataNode(PGChildNodeView):
    node_type = DataModule.NODE_TYPE

    parent_ids = [{'type': 'int', 'id': 'gid'}]
    ids = [{'type': 'int', 'id': 'sid'}]
    operations = dict({
        'obj': [
            {'get': 'properties', 'delete': 'delete', 'put': 'update'},
            {'get': 'list', 'post': 'create'}
        ],
        'nodes': [{'get': 'node'}, {'get': 'nodes'}],
        'sql': [{'get': 'sql'}],
        'msql': [{'get': 'modified_sql'}],
        'stats': [{'get': 'statistics'}],
        'dependency': [{'get': 'dependencies'}],
        'dependent': [{'get': 'dependents'}],
        'children': [{'get': 'children'}],
        'supported_datasources.js': [{}, {}, {'get': 'supported_datasources'}],
        'reload':
            [{'get': 'reload_configuration'}],
        'restore_point':
            [{'post': 'create_restore_point'}],
        'connect': [{
            'get': 'connect_status', 'post': 'connect', 'delete': 'disconnect'
        }],
        'change_password': [{'post': 'change_password'}],
        'wal_replay': [{
            'delete': 'pause_wal_replay', 'put': 'resume_wal_replay'
        }],
        'check_pgpass': [{'get': 'check_pgpass'}],
        'clear_saved_password': [{'put': 'clear_saved_password'}],
        'clear_sshtunnel_password': [{'put': 'clear_sshtunnel_password'}]
    })
    EXP_IP4 = "^\s*((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\." \
              "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\." \
              "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\." \
              "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?))\s*$"
    EXP_IP6 = '^\s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|' \
              '(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|' \
              '2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d))' \
              '{3})|:))|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|' \
              ':((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d' \
              '|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]' \
              '{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]\d|1\d\d|' \
              '[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|' \
              '(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:[0-9A-' \
              'Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25' \
              '[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:)' \
              '{2}(((:[0-9A-Fa-f]{1,4}){1,5})|((:[0-9A-Fa-f]{1,4}){0,3}:(' \
              '(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|' \
              '[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]' \
              '{1,4}){1,6})|((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\d|'\
              '1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))' \
              '|(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((' \
              '25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|' \
              '[1-9]?\d)){3}))|:)))(%.+)?\s*$'
    pat4 = re.compile(EXP_IP4)
    pat6 = re.compile(EXP_IP6)
    SSL_MODES = ['prefer', 'require', 'verify-ca', 'verify-full']

    def check_ssl_fields(self, data):
        """
        This function will allow us to check and set defaults for
        SSL fields

        Args:
            data: Response data

        Returns:
            Flag and Data
        """
        flag = False

        if 'sslmode' in data and data['sslmode'] in self.SSL_MODES:
            flag = True
            ssl_fields = [
                'sslcert', 'sslkey', 'sslrootcert', 'sslcrl', 'sslcompression'
            ]
            # Required SSL fields for SERVER mode from user
            required_ssl_fields_datasource_mode = ['sslcert', 'sslkey']

            for field in ssl_fields:
                if field not in data:
                    # In DataSource mode,
                    # we will set dummy SSL certificate file path which will
                    # prevent using default SSL certificates from web datasources

                    if config.SERVER_MODE and \
                            field in required_ssl_fields_datasource_mode:
                        # Set file manager directory from preference
                        import os
                        file_extn = '.key' if field.endswith('key') else '.crt'
                        dummy_ssl_file = os.path.join(
                            '<STORAGE_DIR>', '.postgresql',
                            'postgresql' + file_extn
                        )
                        data[field] = dummy_ssl_file
                    # For Desktop mode, we will allow to default
                    else:
                        data[field] = None

        return flag, data

    @login_required
    def nodes(self, gid):
        res = []
        """
        Return a JSON document listing the datasources under this datasource group
        for the user.
        """
        datasources = DataSource.query.filter_by(user_id=current_user.id,
                                         datagroup_id=gid)

        driver = get_driver(PG_DEFAULT_DRIVER)

        for datasource in datasources:
            manager = driver.connection_manager(datasource.id)
            conn = manager.connection()
            connected = conn.connected()
            errmsg = None
            in_recovery = None
            wal_paused = None
            if connected:
                status, result, in_recovery, wal_paused =\
                    recovery_state(conn, manager.version)
                if not status:
                    connected = False
                    manager.release()
                    errmsg = "{0} : {1}".format(datasource.name, result)

            res.append(
                self.blueprint.generate_browser_node(
                    "%d" % (datasource.id),
                    gid,
                    datasource.name,
                    datasource_icon_and_background(connected, manager, datasource),
                    True,
                    self.node_type,
                    connected=connected,
                    datasource_type=manager.datasource_type if connected else 'pg',
                    version=manager.version,
                    db=manager.db,
                    user=manager.user_info if connected else None,
                    in_recovery=in_recovery,
                    wal_pause=wal_paused,
                    is_password_saved=True if datasource.password is not None
                    else False,
                    is_tunnel_password_saved=True
                    if datasource.tunnel_password is not None else False,
                    errmsg=errmsg
                )
            )

        if not len(res):
            return gone(errormsg=gettext(
                'The specified datasource group with id# {0} could not be found.'
            ))

        return make_json_response(result=res)

    @login_required
    def node(self, gid, sid):
        """Return a JSON document listing the datasource groups for the user"""
        datasource = DataSource.query.filter_by(user_id=current_user.id,
                                        datagroup_id=gid,
                                        id=sid).first()

        if datasource is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext(
                    gettext(
                        "Could not find the datasource with id# {0}."
                    ).format(sid)
                )
            )

        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(datasource.id)
        conn = manager.connection()
        connected = conn.connected()
        errmsg = None
        in_recovery = None
        wal_paused = None
        if connected:
            status, result, in_recovery, wal_paused =\
                recovery_state(conn, manager.version)
            if not status:
                connected = False
                manager.release()
                errmsg = "{0} : {1}".format(datasource.name, result)

        return make_json_response(
            result=self.blueprint.generate_browser_node(
                "%d" % (datasource.id),
                gid,
                datasource.name,
                datasource_icon_and_background(connected, manager, datasource),
                True,
                self.node_type,
                connected=connected,
                datasource_type=manager.datasource_type if connected else 'pg',
                version=manager.version,
                db=manager.db,
                user=manager.user_info if connected else None,
                in_recovery=in_recovery,
                wal_pause=wal_paused,
                is_password_saved=True if datasource.password is not None
                else False,
                is_tunnel_password_saved=True
                if datasource.tunnel_password is not None else False,
                errmsg=errmsg
            ),
        )

    @login_required
    def delete(self, gid, sid):
        """Delete a datasource node in the settings database."""
        datasources = DataSource.query.filter_by(user_id=current_user.id, id=sid)

        # TODO:: A datasource, which is connected, cannot be deleted
        if datasources is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext(
                    'The specified datasource could not be found.\n'
                    'Does the user have permission to access the '
                    'datasource?'
                )
            )
        else:
            try:
                for s in datasources:
                    get_driver(PG_DEFAULT_DRIVER).delete_manager(s.id)
                    db.session.delete(s)
                db.session.commit()

                QueryHistory.clear_history(current_user.id, sid)

            except Exception as e:
                current_app.logger.exception(e)
                return make_json_response(
                    success=0,
                    errormsg=e.message)

        return make_json_response(success=1,
                                  info=gettext("Data deleted"))

    @login_required
    def update(self, gid, sid):
        """Update the datasource settings"""
        datasource = DataSource.query.filter_by(
            user_id=current_user.id, id=sid).first()

        if datasource is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext("Could not find the required datasource.")
            )

        # Not all parameters can be modified, while the datasource is connected
        config_param_map = {
            'name': 'name',
            'host': 'host',
            'hostaddr': 'hostaddr',
            'port': 'port',
            'db': 'maintenance_db',
            'username': 'username',
            'sslmode': 'ssl_mode',
            'gid': 'datagroup_id',
            'comment': 'comment',
            'role': 'role',
            'db_res': 'db_res',
            'passfile': 'passfile',
            'sslcert': 'sslcert',
            'sslkey': 'sslkey',
            'sslrootcert': 'sslrootcert',
            'sslcrl': 'sslcrl',
            'sslcompression': 'sslcompression',
            'bgcolor': 'bgcolor',
            'fgcolor': 'fgcolor',
            'service': 'service',
            'connect_timeout': 'connect_timeout',
            'use_ssh_tunnel': 'use_ssh_tunnel',
            'tunnel_host': 'tunnel_host',
            'tunnel_port': 'tunnel_port',
            'tunnel_username': 'tunnel_username',
            'tunnel_authentication': 'tunnel_authentication',
            'tunnel_identity_file': 'tunnel_identity_file',
        }

        disp_lbl = {
            'name': gettext('name'),
            'host': gettext('Host name/address'),
            'port': gettext('Port'),
            'db': gettext('Maintenance database'),
            'username': gettext('Username'),
            'sslmode': gettext('SSL Mode'),
            'comment': gettext('Comments'),
            'role': gettext('Role')
        }

        idx = 0
        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8'
        )
        if 'db_res' in data:
            data['db_res'] = ','.join(data['db_res'])

        if 'hostaddr' in data and data['hostaddr'] and data['hostaddr'] != '':
            if not self.pat4.match(data['hostaddr']):
                if not self.pat6.match(data['hostaddr']):
                    return make_json_response(
                        success=0,
                        status=400,
                        errormsg=gettext('Host address not valid')
                    )

        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
        conn = manager.connection()
        connected = conn.connected()

        if connected:
            for arg in (
                    'host', 'hostaddr', 'port', 'db', 'username', 'sslmode',
                    'role', 'service'
            ):
                if arg in data:
                    return forbidden(
                        errormsg=gettext(
                            "'{0}' is not allowed to modify, "
                            "when datasource is connected."
                        ).format(disp_lbl[arg])
                    )

        for arg in config_param_map:
            if arg in data:
                value = data[arg]
                # sqlite3 do not have boolean type so we need to convert
                # it manually to integer
                if arg == 'sslcompression':
                    value = 1 if value else 0
                setattr(datasource, config_param_map[arg], value)
                idx += 1

        if idx == 0:
            return make_json_response(
                success=0,
                errormsg=gettext('No parameters were changed.')
            )

        try:
            db.session.commit()
        except Exception as e:
            current_app.logger.exception(e)
            return make_json_response(
                success=0,
                errormsg=e.message
            )

        # When datasource is connected, we don't require to update the connection
        # manager. Because - we don't allow to change any of the parameters,
        # which will affect the connections.
        if not conn.connected():
            manager.update(datasource)

        return jsonify(
            node=self.blueprint.generate_browser_node(
                "%d" % (datasource.id), datasource.datagroup_id,
                datasource.name,
                datasource_icon_and_background(connected, manager, datasource),
                True,
                self.node_type,
                connected=connected,
                user=manager.user_info if connected else None,
                datasource_type='pg'  # default datasource type
            )
        )

    @login_required
    def list(self, gid):
        """
        Return list of attributes of all datasources.
        """
        datasources = DataSource.query.filter_by(
            user_id=current_user.id,
            datagroup_id=gid).order_by(DataSource.name)
        sg = DataGroup.query.filter_by(
            user_id=current_user.id,
            id=gid
        ).first()
        res = []

        driver = get_driver(PG_DEFAULT_DRIVER)

        for datasource in datasources:
            manager = driver.connection_manager(datasource.id)
            conn = manager.connection()
            connected = conn.connected()

            res.append({
                'id': datasource.id,
                'name': datasource.name,
                'host': datasource.host,
                'port': datasource.port,
                'db': datasource.maintenance_db,
                'username': datasource.username,
                'gid': datasource.datagroup_id,
                'group-name': sg.name,
                'comment': datasource.comment,
                'role': datasource.role,
                'connected': connected,
                'version': manager.ver,
                'datasource_type': manager.datasource_type if connected else 'pg',
                'db_res': datasource.db_res.split(',') if datasource.db_res else None
            })

        return ajax_response(
            response=res
        )

    @login_required
    def properties(self, gid, sid):
        """Return list of attributes of a datasource"""
        datasource = DataSource.query.filter_by(
            user_id=current_user.id,
            id=sid).first()

        if datasource is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext("Could not find the required datasource.")
            )

        sg = DataGroup.query.filter_by(
            user_id=current_user.id,
            id=datasource.datagroup_id
        ).first()

        driver = get_driver(PG_DEFAULT_DRIVER)

        manager = driver.connection_manager(sid)
        conn = manager.connection()
        connected = conn.connected()

        is_ssl = True if datasource.ssl_mode in self.SSL_MODES else False

        return ajax_response(
            response={
                'id': datasource.id,
                'name': datasource.name,
                'host': datasource.host,
                'hostaddr': datasource.hostaddr,
                'port': datasource.port,
                'db': datasource.maintenance_db,
                'username': datasource.username,
                'gid': str(datasource.datagroup_id),
                'group-name': sg.name,
                'comment': datasource.comment,
                'role': datasource.role,
                'connected': connected,
                'version': manager.ver,
                'sslmode': datasource.ssl_mode,
                'datasource_type': manager.datasource_type if connected else 'pg',
                'bgcolor': datasource.bgcolor,
                'fgcolor': datasource.fgcolor,
                'db_res': datasource.db_res.split(',') if datasource.db_res else None,
                'passfile': datasource.passfile if datasource.passfile else None,
                'sslcert': datasource.sslcert if is_ssl else None,
                'sslkey': datasource.sslkey if is_ssl else None,
                'sslrootcert': datasource.sslrootcert if is_ssl else None,
                'sslcrl': datasource.sslcrl if is_ssl else None,
                'sslcompression': True if is_ssl and datasource.sslcompression
                else False,
                'service': datasource.service if datasource.service else None,
                'connect_timeout':
                    datasource.connect_timeout if datasource.connect_timeout else 0,
                'use_ssh_tunnel': datasource.use_ssh_tunnel
                if datasource.use_ssh_tunnel else 0,
                'tunnel_host': datasource.tunnel_host if datasource.tunnel_host
                else None,
                'tunnel_port': datasource.tunnel_port if datasource.tunnel_port
                else 22,
                'tunnel_username': datasource.tunnel_username
                if datasource.tunnel_username else None,
                'tunnel_identity_file': datasource.tunnel_identity_file
                if datasource.tunnel_identity_file else None,
                'tunnel_authentication': datasource.tunnel_authentication
                if datasource.tunnel_authentication else 0
            }
        )

    @login_required
    def create(self, gid):
        """Add a datasource node to the settings database"""
        required_args = [
            u'name',
            u'db',
            u'sslmode',
        ]

        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8'
        )

        # Get enc key
        crypt_key_present, crypt_key = get_crypt_key()
        if not crypt_key_present:
            raise CryptKeyMissing

        # Some fields can be provided with service file so they are optional
        if 'service' in data and not data['service']:
            required_args.extend([
                u'host',
                u'port',
                u'username',
                u'role'
            ])
        for arg in required_args:
            if arg not in data:
                return make_json_response(
                    status=410,
                    success=0,
                    errormsg=gettext(
                        "Could not find the required parameter (%s)." % arg
                    )
                )

        if 'hostaddr' in data and data['hostaddr'] and data['hostaddr'] != '':
            if not self.pat4.match(data['hostaddr']):
                if not self.pat6.match(data['hostaddr']):
                    return make_json_response(
                        success=0,
                        status=400,
                        errormsg=gettext('Host address not valid')
                    )

        # To check ssl configuration
        is_ssl, data = self.check_ssl_fields(data)

        datasource = None

        try:
            datasource = DataSource(
                user_id=current_user.id,
                datagroup_id=data.get('gid', gid),
                name=data.get('name'),
                host=data.get('host', None),
                hostaddr=data.get('hostaddr', None),
                port=data.get('port'),
                maintenance_db=data.get('db', None),
                username=data.get('username'),
                ssl_mode=data.get('sslmode'),
                comment=data.get('comment', None),
                role=data.get('role', None),
                db_res=','.join(data[u'db_res'])
                if u'db_res' in data else None,
                sslcert=data.get('sslcert', None),
                sslkey=data.get('sslkey', None),
                sslrootcert=data.get('sslrootcert', None),
                sslcrl=data.get('sslcrl', None),
                sslcompression=1 if is_ssl and data['sslcompression'] else 0,
                bgcolor=data.get('bgcolor', None),
                fgcolor=data.get('fgcolor', None),
                service=data.get('service', None),
                connect_timeout=data.get('connect_timeout', 0),
                use_ssh_tunnel=data.get('use_ssh_tunnel', 0),
                tunnel_host=data.get('tunnel_host', None),
                tunnel_port=data.get('tunnel_port', 22),
                tunnel_username=data.get('tunnel_username', None),
                tunnel_authentication=data.get('tunnel_authentication', 0),
                tunnel_identity_file=data.get('tunnel_identity_file', None)
            )
            db.session.add(datasource)
            db.session.commit()

            connected = False
            user = None
            manager = None

            if 'connect_now' in data and data['connect_now']:
                manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(
                    datasource.id)
                manager.update(datasource)
                conn = manager.connection()

                have_password = False
                have_tunnel_password = False
                password = None
                passfile = None
                tunnel_password = ''
                if 'password' in data and data["password"] != '':
                    # login with password
                    have_password = True
                    password = data['password']
                    password = encrypt(password, crypt_key)
                elif 'passfile' in data and data["passfile"] != '':
                    passfile = data['passfile']
                    setattr(datasource, 'passfile', passfile)
                    db.session.commit()

                if 'tunnel_password' in data and data["tunnel_password"] != '':
                    have_tunnel_password = True
                    tunnel_password = data['tunnel_password']
                    tunnel_password = \
                        encrypt(tunnel_password, crypt_key)

                status, errmsg = conn.connect(
                    password=password,
                    passfile=passfile,
                    tunnel_password=tunnel_password,
                    datasource_types=DataSourceType.types()
                )
                if hasattr(str, 'decode') and errmsg is not None:
                    errmsg = errmsg.decode('utf-8')
                if not status:
                    db.session.delete(datasource)
                    db.session.commit()
                    return make_json_response(
                        status=401,
                        success=0,
                        errormsg=gettext(
                            u"Unable to connect to datasource:\n\n%s" % errmsg)
                    )
                else:
                    if 'save_password' in data and data['save_password'] and \
                            have_password and config.ALLOW_SAVE_PASSWORD:
                        setattr(datasource, 'password', password)
                        db.session.commit()

                    if 'save_tunnel_password' in data and \
                        data['save_tunnel_password'] and \
                        have_tunnel_password and \
                            config.ALLOW_SAVE_TUNNEL_PASSWORD:
                        setattr(datasource, 'tunnel_password', tunnel_password)
                        db.session.commit()

                    user = manager.user_info
                    connected = True

            return jsonify(
                node=self.blueprint.generate_browser_node(
                    "%d" % datasource.id, datasource.datagroup_id,
                    datasource.name,
                    datasource_icon_and_background(connected, manager, datasource),
                    True,
                    self.node_type,
                    user=user,
                    connected=connected,
                    datasource_type=manager.datasource_type
                    if manager and manager.datasource_type
                    else 'pg'
                )
            )

        except Exception as e:
            if datasource:
                db.session.delete(datasource)
                db.session.commit()

            current_app.logger.exception(e)
            return make_json_response(
                status=410,
                success=0,
                errormsg=str(e)
            )

    @login_required
    def sql(self, gid, sid):
        return make_json_response(data='')

    @login_required
    def modified_sql(self, gid, sid):
        return make_json_response(data='')

    @login_required
    def statistics(self, gid, sid):
        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
        conn = manager.connection()

        if conn.connected():
            status, res = conn.execute_dict(
                render_template(
                    "/datasources/sql/#{0}#/stats.sql".format(manager.version),
                    conn=conn, _=gettext
                )
            )

            if not status:
                return internal_datasource_error(errormsg=res)

            return make_json_response(data=res)

        return make_json_response(
            info=gettext(
                "Data has no active connection for generating statistics."
            )
        )

    @login_required
    def dependencies(self, gid, sid):
        return make_json_response(data='')

    @login_required
    def dependents(self, gid, sid):
        return make_json_response(data='')

    def supported_datasources(self, **kwargs):
        """
        This property defines (if javascript) exists for this node.
        Override this property for your own logic.
        """

        return make_response(
            render_template(
                "datasources/supported_datasources.js",
                datasource_types=DataSourceType.types()
            ),
            200, {'Content-Type': 'application/javascript'}
        )

    def connect_status(self, gid, sid):
        """Check and return the connection status."""
        datasource = DataSource.query.filter_by(id=sid).first()
        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
        conn = manager.connection()
        connected = conn.connected()
        in_recovery = None
        wal_paused = None
        errmsg = None
        if connected:
            status, result, in_recovery, wal_paused =\
                recovery_state(conn, manager.version)

            if not status:
                connected = False
                manager.release()
                errmsg = "{0} : {1}".format(datasource.name, result)

        return make_json_response(
            data={
                'icon': datasource_icon_and_background(connected, manager, datasource),
                'connected': connected,
                'in_recovery': in_recovery,
                'wal_pause': wal_paused,
                'datasource_type': manager.datasource_type if connected else "pg",
                'user': manager.user_info if connected else None,
                'errmsg': errmsg
            }
        )

    def connect(self, gid, sid):
        """
        Connect the Data and return the connection object.
        Verification Process before Connection:
            Verify requested datasource.

            Check the datasource password is already been stored in the
            database or not.
            If Yes, connect the datasource and return connection.
            If No, Raise HTTP error and ask for the password.

            In case of 'Save Password' request from user, excrypted Pasword
            will be stored in the respected datasource database and
            establish the connection OR just connect the datasource and do not
            store the password.
        """
        current_app.logger.info(
            'Connection Request for datasource#{0}'.format(sid)
        )

        # Fetch Data Details
        datasource = DataSource.query.filter_by(id=sid).first()
        if datasource is None:
            return bad_request(gettext("Data not found."))

        if current_user and hasattr(current_user, 'id'):
            # Fetch User Details.
            user = User.query.filter_by(id=current_user.id).first()
            if user is None:
                return unauthorized(gettext("Unauthorized request."))
        else:
            return unauthorized(gettext("Unauthorized request."))

        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8'
        ) if request.data else {}

        password = None
        passfile = None
        tunnel_password = None
        save_password = False
        save_tunnel_password = False
        prompt_password = False
        prompt_tunnel_password = False

        # Connect the Data
        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
        conn = manager.connection()

        # Get enc key
        crypt_key_present, crypt_key = get_crypt_key()
        if not crypt_key_present:
            raise CryptKeyMissing

        # If datasource using SSH Tunnel
        if datasource.use_ssh_tunnel:
            if 'tunnel_password' not in data:
                if datasource.tunnel_password is None:
                    prompt_tunnel_password = True
                else:
                    tunnel_password = datasource.tunnel_password
            else:
                tunnel_password = data['tunnel_password'] \
                    if 'tunnel_password'in data else ''
                save_tunnel_password = data['save_tunnel_password'] \
                    if tunnel_password and 'save_tunnel_password' in data \
                    else False
                # Encrypt the password before saving with user's login
                # password key.
                try:
                    tunnel_password = encrypt(tunnel_password, crypt_key) \
                        if tunnel_password is not None else \
                        datasource.tunnel_password
                except Exception as e:
                    current_app.logger.exception(e)
                    return internal_datasource_error(errormsg=str(e))

        if 'password' not in data:
            conn_passwd = getattr(conn, 'password', None)
            if conn_passwd is None and datasource.password is None and \
                    datasource.passfile is None and datasource.service is None:
                prompt_password = True
            elif datasource.passfile and datasource.passfile != '':
                passfile = datasource.passfile
            else:
                password = conn_passwd or datasource.password
        else:
            password = data['password'] if 'password' in data else None
            save_password = data['save_password']\
                if password and 'save_password' in data else False

            # Encrypt the password before saving with user's login
            # password key.
            try:
                password = encrypt(password, crypt_key) \
                    if password is not None else datasource.password
            except Exception as e:
                current_app.logger.exception(e)
                return internal_datasource_error(errormsg=str(e))

        # Check do we need to prompt for the database datasource or ssh tunnel
        # password or both. Return the password template in case password is
        # not provided, or password has not been saved earlier.
        if prompt_password or prompt_tunnel_password:
            return self.get_response_for_password(datasource, 428, prompt_password,
                                                  prompt_tunnel_password)

        status = True
        try:
            status, errmsg = conn.connect(
                password=password,
                passfile=passfile,
                tunnel_password=tunnel_password,
                datasource_types=DataSourceType.types()
            )
        except OperationalError as e:
            return internal_datasource_error(errormsg=str(e))
        except Exception as e:
            current_app.logger.exception(e)
            return self.get_response_for_password(
                datasource, 401, True, True, getattr(e, 'message', str(e)))

        if not status:
            if hasattr(str, 'decode'):
                errmsg = errmsg.decode('utf-8')

            current_app.logger.error(
                "Could not connect to datasource(#{0}) - '{1}'.\nError: {2}"
                .format(datasource.id, datasource.name, errmsg)
            )
            return self.get_response_for_password(datasource, 401, True,
                                                  True, errmsg)
        else:
            if save_password and config.ALLOW_SAVE_PASSWORD:
                try:
                    # Save the encrypted password using the user's login
                    # password key.
                    setattr(datasource, 'password', password)
                    db.session.commit()
                except Exception as e:
                    # Release Connection
                    current_app.logger.exception(e)
                    manager.release(database=datasource.maintenance_db)
                    conn = None

                    return internal_datasource_error(errormsg=e.message)

            if save_tunnel_password and config.ALLOW_SAVE_TUNNEL_PASSWORD:
                try:
                    # Save the encrypted tunnel password.
                    setattr(datasource, 'tunnel_password', tunnel_password)
                    db.session.commit()
                except Exception as e:
                    # Release Connection
                    current_app.logger.exception(e)
                    manager.release(database=datasource.maintenance_db)
                    conn = None

                    return internal_datasource_error(errormsg=e.message)

            current_app.logger.info('Connection Established for datasource: \
                %s - %s' % (datasource.id, datasource.name))
            # Update the recovery and wal pause option for the datasource
            # if connected successfully
            _, _, in_recovery, wal_paused =\
                recovery_state(conn, manager.version)

            return make_json_response(
                success=1,
                info=gettext("Data connected."),
                data={
                    'icon': datasource_icon_and_background(True, manager, datasource),
                    'connected': True,
                    'datasource_type': manager.datasource_type,
                    'type': manager.datasource_type,
                    'version': manager.version,
                    'db': manager.db,
                    'user': manager.user_info,
                    'in_recovery': in_recovery,
                    'wal_pause': wal_paused,
                    'is_password_saved': True if datasource.password is not None
                    else False,
                    'is_tunnel_password_saved': True
                    if datasource.tunnel_password is not None else False,
                }
            )

    def disconnect(self, gid, sid):
        """Disconnect the Data."""

        datasource = DataSource.query.filter_by(id=sid).first()
        if datasource is None:
            return bad_request(gettext("Data not found."))

        # Release Connection
        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)

        status = manager.release()

        if not status:
            return unauthorized(gettext("Data could not be disconnected."))
        else:
            return make_json_response(
                success=1,
                info=gettext("Data disconnected."),
                data={
                    'icon': datasource_icon_and_background(False, manager, datasource),
                    'connected': False
                }
            )

    def reload_configuration(self, gid, sid):
        """Reload the datasource configuration"""

        # Reload the datasource configurations
        manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
        conn = manager.connection()

        if conn.connected():
            # Execute the command for reload configuration for the datasource
            status, rid = conn.execute_scalar("SELECT pg_reload_conf();")

            if not status:
                return internal_datasource_error(
                    gettext("Could not reload the datasource configuration.")
                )
            else:
                return make_json_response(data={
                    'status': True,
                    'result': gettext('Data configuration reloaded.')
                })

        else:
            return make_json_response(data={
                'status': False,
                'result': gettext(
                    'Not connected to the datasource or the connection to the'
                    ' datasource has been closed.')})

    def create_restore_point(self, gid, sid):
        """
        This method will creates named restore point

        Args:
            gid: Data group ID
            sid: Data ID

        Returns:
            None
        """
        try:
            data = request.form
            restore_point_name = data['value'] if data else None
            manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
            conn = manager.connection()

            # Execute SQL to create named restore point
            if conn.connected():
                if restore_point_name:
                    status, res = conn.execute_scalar(
                        "SELECT pg_create_restore_point('{0}');".format(
                            restore_point_name
                        )
                    )
                if not status:
                    return internal_datasource_error(
                        errormsg=str(res)
                    )

                return make_json_response(
                    data={
                        'status': 1,
                        'result': gettext(
                            'Named restore point created: {0}'.format(
                                restore_point_name))
                    })

        except Exception as e:
            current_app.logger.error(
                'Named restore point creation failed ({0})'.format(str(e))
            )
            return internal_datasource_error(errormsg=str(e))

    def change_password(self, gid, sid):
        """
        This function is used to change the password of the
        Database Data.

        Args:
            gid: Group id
            sid: Data id
        """
        try:
            data = json.loads(request.form['data'], encoding='utf-8')
            crypt_key = get_crypt_key()[1]

            # Fetch Data Details
            datasource = DataSource.query.filter_by(id=sid).first()
            if datasource is None:
                return bad_request(gettext("Data not found."))

            # Fetch User Details.
            user = User.query.filter_by(id=current_user.id).first()
            if user is None:
                return unauthorized(gettext("Unauthorized request."))

            manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
            conn = manager.connection()
            is_passfile = False

            # If there is no password found for the datasource
            # then check for pgpass file
            if not datasource.password and not manager.password:
                if datasource.passfile and \
                        manager.passfile and \
                        datasource.passfile == manager.passfile:
                    is_passfile = True

            # Check for password only if there is no pgpass file used
            if not is_passfile:
                if data and ('password' not in data or data['password'] == ''):
                    return make_json_response(
                        status=400,
                        success=0,
                        errormsg=gettext(
                            "Could not find the required parameter(s)."
                        )
                    )

            if data and ('newPassword' not in data or
                         data['newPassword'] == '' or
                         'confirmPassword' not in data or
                         data['confirmPassword'] == ''):
                return make_json_response(
                    status=400,
                    success=0,
                    errormsg=gettext(
                        "Could not find the required parameter(s)."
                    )
                )

            if data['newPassword'] != data['confirmPassword']:
                return make_json_response(
                    status=200,
                    success=0,
                    errormsg=gettext(
                        "Passwords do not match."
                    )
                )

            # Check against old password only if no pgpass file
            if not is_passfile:
                decrypted_password = decrypt(manager.password, crypt_key)

                if isinstance(decrypted_password, bytes):
                    decrypted_password = decrypted_password.decode()

                password = data['password']

                # Validate old password before setting new.
                if password != decrypted_password:
                    return unauthorized(gettext("Incorrect password."))

            # Hash new password before saving it.
            if manager.sversion >= 100000:
                password = conn.pq_encrypt_password_conn(data['newPassword'],
                                                         manager.user)
                if password is None:
                    # Unable to encrypt the password so used the
                    # old method of encryption
                    password = pqencryptpassword(data['newPassword'],
                                                 manager.user)
            else:
                password = pqencryptpassword(data['newPassword'], manager.user)

            SQL = render_template(
                "/datasources/sql/#{0}#/change_password.sql".format(
                    manager.version),
                conn=conn, _=gettext,
                user=manager.user, encrypted_password=password)

            status, res = conn.execute_scalar(SQL)

            if not status:
                return internal_datasource_error(errormsg=res)

            # Store password in sqlite only if no pgpass file
            if not is_passfile:
                password = encrypt(data['newPassword'], crypt_key)
                # Check if old password was stored in pgadmin4 sqlite database.
                # If yes then update that password.
                if datasource.password is not None and config.ALLOW_SAVE_PASSWORD:
                    setattr(datasource, 'password', password)
                    db.session.commit()
                # Also update password in connection manager.
                manager.password = password
                manager.update_session()

            return make_json_response(
                status=200,
                success=1,
                info=gettext(
                    "Password changed successfully."
                )
            )

        except Exception as e:
            return internal_datasource_error(errormsg=str(e))

    def wal_replay(self, sid, pause=True):
        """
        Utility function for wal_replay for resume/pause.
        """
        datasource = DataSource.query.filter_by(
            user_id=current_user.id, id=sid
        ).first()

        if datasource is None:
            return make_json_response(
                success=0,
                errormsg=gettext("Could not find the required datasource.")
            )

        try:
            manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
            conn = manager.connection()

            # Execute SQL to pause or resume WAL replay
            if conn.connected():
                if pause:
                    sql = "SELECT pg_xlog_replay_pause();"
                    if manager.version >= 100000:
                        sql = "SELECT pg_wal_replay_pause();"

                    status, res = conn.execute_scalar(sql)
                    if not status:
                        return internal_datasource_error(
                            errormsg=str(res)
                        )
                else:
                    sql = "SELECT pg_xlog_replay_resume();"
                    if manager.version >= 100000:
                        sql = "SELECT pg_wal_replay_resume();"

                    status, res = conn.execute_scalar(sql)
                    if not status:
                        return internal_datasource_error(
                            errormsg=str(res)
                        )
                return make_json_response(
                    success=1,
                    info=gettext('WAL replay paused'),
                    data={'in_recovery': True, 'wal_pause': pause}
                )
            return gone(errormsg=_('Please connect the datasource.'))
        except Exception as e:
            current_app.logger.error(
                'WAL replay pause/resume failed'
            )
            return internal_datasource_error(errormsg=str(e))

    def resume_wal_replay(self, gid, sid):
        """
        This method will resume WAL replay

        Args:
            gid: Data group ID
            sid: Data ID

        Returns:
            None
        """
        return self.wal_replay(sid, False)

    def pause_wal_replay(self, gid, sid):
        """
        This method will pause WAL replay

        Args:
            gid: Data group ID
            sid: Data ID

        Returns:
            None
        """
        return self.wal_replay(sid, True)

    def check_pgpass(self, gid, sid):
        """
        This function is used to check whether datasource is connected
        using pgpass file or not

        Args:
            gid: Group id
            sid: Data id
        """
        is_pgpass = False
        datasource = DataSource.query.filter_by(
            user_id=current_user.id, id=sid
        ).first()

        if datasource is None:
            return make_json_response(
                success=0,
                errormsg=gettext("Could not find the required datasource.")
            )

        try:
            manager = get_driver(PG_DEFAULT_DRIVER).connection_manager(sid)
            conn = manager.connection()
            if not conn.connected():
                return gone(
                    errormsg=_('Please connect the datasource.')
                )

            if not datasource.password or not manager.password:
                if datasource.passfile and \
                        manager.passfile and \
                        datasource.passfile == manager.passfile:
                    is_pgpass = True
            return make_json_response(
                success=1,
                data=dict({'is_pgpass': is_pgpass}),
            )
        except Exception as e:
            current_app.logger.error(
                'Cannot able to fetch pgpass status'
            )
            return internal_datasource_error(errormsg=str(e))

    def get_response_for_password(self, datasource, status, prompt_password=False,
                                  prompt_tunnel_password=False, errmsg=None):

        if datasource.use_ssh_tunnel:
            return make_json_response(
                success=0,
                status=status,
                result=render_template(
                    'datasources/tunnel_password.html',
                    datasource_label=datasource.name,
                    username=datasource.username,
                    tunnel_username=datasource.tunnel_username,
                    tunnel_host=datasource.tunnel_host,
                    tunnel_identity_file=datasource.tunnel_identity_file,
                    errmsg=errmsg,
                    _=gettext,
                    prompt_tunnel_password=prompt_tunnel_password,
                    prompt_password=prompt_password
                )
            )
        else:
            return make_json_response(
                success=0,
                status=status,
                result=render_template(
                    'datasources/password.html',
                    datasource_label=datasource.name,
                    username=datasource.username,
                    errmsg=errmsg,
                    _=gettext,
                )
            )

    def clear_saved_password(self, gid, sid):
        """
        This function is used to remove database datasource password stored into
        the pgAdmin's db file.

        :param gid:
        :param sid:
        :return:
        """
        try:
            datasource = DataSource.query.filter_by(
                user_id=current_user.id, id=sid
            ).first()

            if datasource is None:
                return make_json_response(
                    success=0,
                    info=gettext("Could not find the required datasource.")
                )

            setattr(datasource, 'password', None)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(
                "Unable to clear saved password.\nError: {0}".format(str(e))
            )

            return internal_datasource_error(errormsg=str(e))

        return make_json_response(
            success=1,
            info=gettext("The saved password cleared successfully."),
            data={'is_password_saved': False}
        )

    def clear_sshtunnel_password(self, gid, sid):
        """
        This function is used to remove sshtunnel password stored into
        the pgAdmin's db file.

        :param gid:
        :param sid:
        :return:
        """
        try:
            datasource = DataSource.query.filter_by(
                user_id=current_user.id, id=sid
            ).first()

            if datasource is None:
                return make_json_response(
                    success=0,
                    info=gettext("Could not find the required datasource.")
                )

            setattr(datasource, 'tunnel_password', None)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(
                "Unable to clear ssh tunnel password."
                "\nError: {0}".format(str(e))
            )

            return internal_datasource_error(errormsg=str(e))

        return make_json_response(
            success=1,
            info=gettext("The saved password cleared successfully."),
            data={'is_tunnel_password_saved': False}
        )


SchemaDiffRegistry(blueprint.node_type, DataNode)
DataNode.register_node_view(blueprint)
