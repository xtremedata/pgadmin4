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
import pgadmin.browser.data_groups as dg
from flask import render_template, request, make_response, jsonify, \
    current_app, url_for
from flask_babelex import gettext
from flask_security import current_user, login_required
from pgadmin.browser.data_groups.datasources.types import DataSourceType
from pgadmin.browser.utils import NodeView
from pgadmin.utils.ajax import make_json_response, bad_request, forbidden, \
    make_response as ajax_response, internal_server_error, unauthorized, gone
from pgadmin.utils.crypto import encrypt, decrypt, pqencryptpassword
from pgadmin.utils.menu import MenuItem
from pgadmin.utils.master_password import get_crypt_key
from pgadmin.utils.exception import CryptKeyMissing

from pgadmin.model import db, DataSource, DataGroup



def datasource_icon_and_background(datasource):
    """

    Args:
        is_connected: Flag to check if datasource is connected
        datasource: Sever object

    Returns:
        DataSource Icon CSS class
    """
    datasource_background_color = ''
    if datasource and datasource.bgcolor:
        datasource_background_color = ' {0}'.format(
            datasource.bgcolor)
        # If user has set font color also
        if datasource.fgcolor:
            datasource_background_color = '{0} {1}'.format(
                datasource_background_color,
                datasource.fgcolor)

    return 'icon-{0}{1}'.format(
        datasource.ds_type, datasource_background_color)


class DataSourceModule(dg.DataGroupPluginModule):
    NODE_TYPE = "datasource"
    LABEL = gettext("Data Sources")

    @property
    def node_type(self):
        return self.NODE_TYPE

    @property
    def script_load(self):
        """
        Load the module script for datasource, when any of the data-group node is
        initialized.
        """
        return dg.DataGroupModule.NODE_TYPE

    def get_dict_node(self, obj, parent):
        return {
            'id': obj.id, 
            'name': obj.name,
            'group-id': parent.id,
            'group-name': parent.name,
            'datasource_type': obj.ds_type }

    def get_browser_node(self, obj, **kwargs):
        return self.generate_browser_node(
                "%d" % (obj.id),
                None,
                obj.name,
                datasource_icon_and_background(obj),
                True,
                self.node_type,
                **kwargs)

    @login_required
    def get_nodes(self, gid):
        """
        Return a JSON document listing the data sources for the user
        """
        datasources = DataSource.query.filter_by(user_id=current_user.id,
                                         datagroup_id=gid)

        for datasource in datasources:
            errmsg = None
            yield self.get_browser_node(datasource, errmsg=errmsg)

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
            'name': 'pgadmin.datasource.supported_datasources',
            'path': url_for('browser.index') + 'datasource/supported_datasources',
            'is_template': True,
            'when': self.node_type
        }])
        scripts.extend(super().get_own_javascripts())

        return scripts


    # We do not have any preferences for datasource node.
    def register_preferences(self):
        """
        register_preferences
        Override it so that - it does not register the show_node preference for
        datasource type.
        """
        pass




class DataSourceMenuItem(MenuItem):
    def __init__(self, **kwargs):
        kwargs.setdefault("type", DataSourceModule.NODE_TYPE)
        super(DataSourceMenuItem, self).__init__(**kwargs)


blueprint = DataSourceModule(__name__)




class DataSourceNode(NodeView):
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
        'clear_saved_password': [{'put': 'clear_saved_password'}],
    })


    @login_required
    def nodes(self, gid):
        """
        Return a JSON document listing the datasources under this data group
        for the user.
        """
        datasources = DataSource.query.filter_by(user_id=current_user.id,
                                         datagroup_id=gid)
        res = [self.blueprint.get_browser_node(obj) for obj in datasources]

        if not len(res):
            return gone(errormsg=gettext(
                'The specified data group with id# {0} could not be found.').format(gid))

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

        return make_json_response(result=self.blueprint.get_browser_node(datasource))

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
                    'The specified data source could not be found.\n'
                    'Does the user have permission to access the '
                    'datasource?'
                )
            )
        else:
            try:
                for s in datasources:
                    db.session.delete(s)
                db.session.commit()

            except Exception as e:
                current_app.logger.exception(e)
                return make_json_response(
                    success=0,
                    errormsg=e)

        return make_json_response(success=1,
                                  info=gettext("Data source deleted"))

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
            'datasource_type': 'ds_type',
            'key_name': 'key_name',
            'key_secret': 'key_secret',
            'bgcolor': 'bgcolor',
            'fgcolor': 'fgcolor'
        }

        disp_lbl = {
            'name': gettext('name'),
            'datasource_type': gettext('Type'),
            'key_name': gettext('Key Name'),
            'key_secret': gettext('Key Secret'),
        }

        idx = 0
        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8')

        for arg in config_param_map:
            if arg in data:
                value = data[arg]
                setattr(datasource, config_param_map[arg], value)
                idx += 1

        if idx == 0:
            return make_json_response(
                success=0,
                errormsg=gettext('No parameters were changed.'))

        try:
            db.session.commit()
        except Exception as e:
            current_app.logger.exception(e)
            return make_json_response(
                success=0,
                errormsg=e)

        return jsonify(node=self.blueprint.get_browser_node(datasource))

    @login_required
    def list(self, gid):
        """
        Return list of attributes of all datasources.
        """
        datasources = DataSource.query.filter_by(
            user_id=current_user.id,
            datagroup_id=gid).order_by(DataSource.name)
        dg = DataGroup.query.filter_by(
            user_id=current_user.id,
            id=gid
        ).first()

        res = [self.blueprint.get_dict_node(d, dg) for d in datasources]
        return ajax_response(response=res)

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

        dg = DataGroup.query.filter_by(
            user_id=current_user.id,
            id=datasource.datagroup_id
        ).first()

        return ajax_response(response=self.blueprint.get_dict_node(datasource, dg))

    @login_required
    def create(self, gid):
        """Add a datasource node to the settings database"""
        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8'
        )

        # Get enc key
        crypt_key_present, crypt_key = get_crypt_key()
        if not crypt_key_present:
            raise CryptKeyMissing

        # Generic required fields
        required_args = DataSourceType.types()[0].required
        if required_args:
            for arg in required_args:
                if arg not in data:
                    return make_json_response(
                        status=410,
                        success=0,
                        errormsg=gettext(
                            "Could not find the required parameter (%s)." % arg
                        )
                    )

        # Specific required fields
        required_args = DataSourceType.type(data.get('ds_type')).required
        if required_args:
            for arg in required_args:
                if arg not in data:
                    return make_json_response(
                        status=410,
                        success=0,
                        errormsg=gettext(
                            "Could not find the required parameter (%s)." % arg
                        )
                    )

        datasource = None

        try:
            datasource = DataSource(
                user_id=current_user.id,
                datagroup_id=data.get('gid', gid),
                name=data.get('name'),
                ds_type=data.get('datasource_type'),
                key_name=data.get('key_name'),
                key_secret=data.get('key_secret'),
                bgcolor=data.get('bgcolor', None),
                fgcolor=data.get('fgcolor', None))
            db.session.add(datasource)
            db.session.commit()

            return jsonify(node=self.blueprint.get_browser_node(datasource))

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
        return make_json_response(status=422)

    @login_required
    def modified_sql(self, gid, sid):
        return make_json_response(status=422)

    @login_required
    def statistics(self, gid, sid):
        return make_json_response(status=422)

    @login_required
    def dependencies(self, gid, sid):
        return make_json_response(status=422)

    @login_required
    def dependents(self, gid, sid):
        return make_json_response(status=422)

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

            datasource.key_secret = None
            db.session.commit()
        except Exception as e:
            current_app.logger.error(
                "Unable to clear saved password.\nError: {0}".format(str(e))
            )

            return internal_server_error(errormsg=str(e))

        return make_json_response(
            success=1,
            info=gettext("The saved password cleared successfully."),
            data={'is_password_saved': False}
        )


DataSourceNode.register_node_view(blueprint)
