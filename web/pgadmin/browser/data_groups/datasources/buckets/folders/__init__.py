##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

from flask import render_template, request, make_response, jsonify, \
    current_app, url_for
from flask_babelex import gettext
from flask_security import current_user, login_required
from pgadmin.browser.utils import PGChildNodeView, PGChildNodeModule
from pgadmin.utils.ajax import make_json_response, bad_request, forbidden, \
    make_response as ajax_response, internal_server_error, unauthorized, gone
import pgadmin.browser.data_groups.folders.buckets as buckets


class FolderModule(PGChildNodeModule):
    NODE_TYPE = "folder"
    LABEL = gettext("Data Sources")

    @property
    def node_type(self):
        return self.NODE_TYPE

    @property
    def script_load(self):
        """
        Load the module script for folder, when any of the data-group node is
        initialized.
        """
        return buckets.BucketModule.NODE_TYPE

    def get_dict_node(self, obj, parent):
        return {
            'name': obj.name
        }

    def get_browser_node(self, obj, **kwargs):
        return self.generate_browser_node(
                "%d" % (obj['Name']),
                None,
                obj.name,
                folder_icon_and_background(obj),
                True,
                self.node_type,
                **kwargs)

    @login_required
    def get_nodes(self, gid):
        """
        Return a JSON document listing the data sources for the user
        """
        folders = Folder.query.filter_by(user_id=current_user.id,
                                         datagroup_id=gid)

        for folder in folders:
            connected = False
            manager = None
            errmsg = None
            try:
                manager = FolderType.type(folder.ds_type).get_manager() # !!! temp
            except Exception as e:
                # !!!
                current_app.logger.exception(e)
                errmsg = str(e)

            yield self.get_browser_node(folder, errmsg=errmsg)

    @property
    def jssnippets(self):
        return []

    @property
    def csssnippets(self):
        """
        Returns a snippet of css to include in the page
        """
        snippets = [render_template("css/folders.css")]

        for submodule in self.submodules:
            snippets.extend(submodule.csssnippets)

        for st in FolderType.types():
            snippets.extend(st.csssnippets)

        return snippets

    def get_own_javascripts(self):
        scripts = []

        scripts.extend([{
            'name': 'pgadmin.folder.supported_folders',
            'path': url_for('browser.index') + 'folder/supported_folders',
            'is_template': True,
            'when': self.node_type
        }])
        scripts.extend(dg.DataGroupPluginModule.get_own_javascripts(self))

        return scripts


    # We do not have any preferences for folder node.
    def register_preferences(self):
        """
        register_preferences
        Override it so that - it does not register the show_node preference for
        folder type.
        """
        pass



blueprint = FolderModule(__name__)




class FolderNode(PGChildNodeView):
    node_type = FolderModule.NODE_TYPE

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
        'supported_folders.js': [{}, {}, {'get': 'supported_folders'}],
        'clear_saved_password': [{'put': 'clear_saved_password'}],
    })


    @login_required
    def nodes(self, gid):
        """
        Return a JSON document listing the folders under this data group
        for the user.
        """
        folders = Folder.query.filter_by(user_id=current_user.id,
                                         datagroup_id=gid)
        res = [self.blueprint.get_browser_node(obj) for obj in folders]

        if not len(res):
            return gone(errormsg=gettext(
                'The specified data group with id# {0} could not be found.').format(gid))

        return make_json_response(result=res)



    @login_required
    def node(self, gid, sid):
        """Return a JSON document listing the folder groups for the user"""
        folder = Folder.query.filter_by(user_id=current_user.id,
                                        datagroup_id=gid,
                                        id=sid).first()

        if folder is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext(
                    gettext(
                        "Could not find the folder with id# {0}."
                    ).format(sid)
                )
            )

        return make_json_response(result=self.blueprint.get_browser_node(folder))

    @login_required
    def delete(self, gid, sid):
        """Delete a folder node in the settings database."""
        folders = Folder.query.filter_by(user_id=current_user.id, id=sid)

        # TODO:: A folder, which is connected, cannot be deleted
        if folders is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext(
                    'The specified data source could not be found.\n'
                    'Does the user have permission to access the '
                    'folder?'
                )
            )
        else:
            try:
                for s in folders:
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
        """Update the folder settings"""
        folder = Folder.query.filter_by(
            user_id=current_user.id, id=sid).first()

        if folder is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext("Could not find the required folder.")
            )

        # Not all parameters can be modified, while the folder is connected
        config_param_map = {
            'name': 'name',
            'folder_type': 'ds_type',
            'key_name': 'key_name',
            'key_secret': 'key_secret',
            'bgcolor': 'bgcolor',
            'fgcolor': 'fgcolor'
        }

        disp_lbl = {
            'name': gettext('name'),
            'folder_type': gettext('Type'),
            'key_name': gettext('Key Name'),
            'key_secret': gettext('Key Secret'),
        }

        idx = 0
        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8')

        for arg in config_param_map:
            if arg in data:
                value = data[arg]
                setattr(folder, config_param_map[arg], value)
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

        return jsonify(node=self.blueprint.get_browser_node(folder))

    @login_required
    def list(self, gid):
        """
        Return list of attributes of all folders.
        """
        folders = Folder.query.filter_by(
            user_id=current_user.id,
            datagroup_id=gid).order_by(Folder.name)
        dg = DataGroup.query.filter_by(
            user_id=current_user.id,
            id=gid
        ).first()

        res = [self.blueprint.get_dict_node(d, dg) for d in folders]
        return ajax_response(response=res)

    @login_required
    def properties(self, gid, sid):
        """Return list of attributes of a folder"""
        folder = Folder.query.filter_by(
            user_id=current_user.id,
            id=sid).first()

        if folder is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext("Could not find the required folder.")
            )

        dg = DataGroup.query.filter_by(
            user_id=current_user.id,
            id=folder.datagroup_id
        ).first()

        return ajax_response(response=self.blueprint.get_dict_node(folder, dg))

    @login_required
    def create(self, gid):
        """Add a folder node to the settings database"""
        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8'
        )

        # Get enc key
        crypt_key_present, crypt_key = get_crypt_key()
        if not crypt_key_present:
            raise CryptKeyMissing

        # Generic required fields
        required_args = FolderType.types().first().required()
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
        required_args = FolderType.type(data.get('ds_type'))
        for arg in required_args:
            if arg not in data:
                return make_json_response(
                    status=410,
                    success=0,
                    errormsg=gettext(
                        "Could not find the required parameter (%s)." % arg
                    )
                )

        folder = None

        try:
            folder = Folder(
                user_id=current_user.id,
                datagroup_id=data.get('gid', gid),
                name=data.get('name'),
                ds_type=data.get('folder_type'),
                key_name=data.get('key_name'),
                key_secret=data.get('key_secret'),
                bgcolor=data.get('bgcolor', None),
                fgcolor=data.get('fgcolor', None),
                service=data.get('service', None))
            db.session.add(folder)
            db.session.commit()

            return jsonify(node=self.blueprint.get_browser_node(folder))

        except Exception as e:
            if folder:
                db.session.delete(folder)
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

    def supported_folders(self, **kwargs):
        """
        This property defines (if javascript) exists for this node.
        Override this property for your own logic.
        """

        return make_response(
            render_template(
                "folders/supported_folders.js",
                folder_types=FolderType.types()
            ),
            200, {'Content-Type': 'application/javascript'}
        )

    def clear_saved_password(self, gid, sid):
        """
        This function is used to remove database folder password stored into
        the pgAdmin's db file.

        :param gid:
        :param sid:
        :return:
        """
        try:
            folder = Folder.query.filter_by(
                user_id=current_user.id, id=sid
            ).first()

            if folder is None:
                return make_json_response(
                    success=0,
                    info=gettext("Could not find the required folder.")
                )

            folder.key_secret = None
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


FolderNode.register_node_view(blueprint)
