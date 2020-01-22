##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

"""Defines views for management of data groups"""

import simplejson as json
from abc import ABCMeta, abstractmethod

import six
from flask import request, jsonify
from flask_babelex import gettext
from flask_security import current_user, login_required
from pgadmin.browser import BrowserPluginModule
from pgadmin.browser.utils import NodeView
from pgadmin.utils.ajax import make_json_response, gone, \
    make_response as ajax_response, bad_request
from pgadmin.utils.menu import MenuItem
from sqlalchemy import exc
from pgadmin.model import db, DataGroup


class DataGroupModule(BrowserPluginModule):
    NODE_TYPE = "data_group"

    def get_nodes(self, *arg, **kwargs):
        """Return a JSON document listing the data groups for the user"""
        groups = DataGroup.query.filter_by(
            user_id=current_user.id
        ).order_by("id")
        for idx, group in enumerate(groups):
            yield self.generate_browser_node(
                "%d" % (group.id), None,
                group.name,
                "icon-%s" % self.node_type,
                False,
                self.node_type,
                can_delete=True if idx > 0 else False
            )

    @property
    def node_type(self):
        """
        node_type
        Node type for Data Group is data-group. It is defined by NODE_TYPE
        static attribute of the class.
        """
        return self.NODE_TYPE

    @property
    def script_load(self):
        """
        script_load
        Load the data-group javascript module on loading of browser module.
        """
        return None

    def register_preferences(self):
        """
        register_preferences
        Overrides the register_preferences PgAdminModule, because - we will not
        register any preference for data-group (specially the show_node
        preference.)
        """
        pass


class DataGroupMenuItem(MenuItem):
    def __init__(self, **kwargs):
        kwargs.setdefault("type", DataGroupModule.NODE_TYPE)
        super(DataGroupMenuItem, self).__init__(**kwargs)


@six.add_metaclass(ABCMeta)
class DataGroupPluginModule(BrowserPluginModule):
    """
    Base class for data group plugins.
    """

    @abstractmethod
    def get_nodes(self, *arg, **kwargs):
        pass


blueprint = DataGroupModule(__name__)


class DataGroupView(NodeView):
    node_type = DataGroupModule.NODE_TYPE
    parent_ids = []
    ids = [{'type': 'int', 'id': 'gid'}]

    @login_required
    def list(self):
        res = []

        for dg in DataGroup.query.filter_by(
                user_id=current_user.id
        ).order_by('name'):
            res.append({
                'id': dg.id,
                'name': dg.name
            })

        return ajax_response(response=res, status=200)

    @login_required
    def delete(self, gid):
        """Delete a data group node in the settings database"""

        groups = DataGroup.query.filter_by(
            user_id=current_user.id
        ).order_by("id")

        # if data group id is 1 we won't delete it.
        dg = groups.first()

        if dg.id == gid:
            return make_json_response(
                status=417,
                success=0,
                errormsg=gettext(
                    'The specified data group cannot be deleted.'
                )
            )

        # There can be only one record at most
        dg = groups.filter_by(id=gid).first()

        if dg is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext(
                    'The specified data group could not be found.'
                )
            )
        else:
            try:
                db.session.delete(dg)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                return make_json_response(
                    status=410, success=0, errormsg=e.message
                )

        return make_json_response(result=request.form)

    @login_required
    def update(self, gid):
        """Update the data-group properties"""

        # There can be only one record at most
        datagroup = DataGroup.query.filter_by(
            user_id=current_user.id,
            id=gid).first()

        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8'
        )

        if datagroup is None:
            return make_json_response(
                status=417,
                success=0,
                errormsg=gettext(
                    'The specified data group could not be found.'
                )
            )
        else:
            try:
                if u'name' in data:
                    datagroup.name = data[u'name']
                db.session.commit()
            except exc.IntegrityError:
                db.session.rollback()
                return bad_request(gettext(
                    "The specified data group already exists."
                ))
            except Exception as e:
                db.session.rollback()
                return make_json_response(
                    status=410, success=0, errormsg=e.message
                )

        return jsonify(
            node=self.blueprint.generate_browser_node(
                gid,
                None,
                datagroup.name,
                "icon-%s" % self.node_type,
                True,
                self.node_type,
                can_delete=True  # This is user created hence can deleted
            )
        )

    @login_required
    def properties(self, gid):
        """Update the data-group properties"""

        # There can be only one record at most
        dg = DataGroup.query.filter_by(
            user_id=current_user.id,
            id=gid).first()

        if dg is None:
            return make_json_response(
                status=410,
                success=0,
                errormsg=gettext(
                    'The specified data group could not be found.'
                )
            )
        else:
            return ajax_response(
                response={'id': dg.id, 'name': dg.name},
                status=200
            )

    @login_required
    def create(self):
        """Creates new data-group """
        data = request.form if request.form else json.loads(
            request.data, encoding='utf-8'
        )
        if data[u'name'] != '':
            try:
                dg = DataGroup(
                    user_id=current_user.id,
                    name=data[u'name'])
                db.session.add(dg)
                db.session.commit()

                data[u'id'] = dg.id
                data[u'name'] = dg.name

                return jsonify(
                    node=self.blueprint.generate_browser_node(
                        "%d" % dg.id,
                        None,
                        dg.name,
                        "icon-%s" % self.node_type,
                        True,
                        self.node_type,
                        # This is user created hence can deleted
                        can_delete=True
                    )
                )
            except exc.IntegrityError:
                db.session.rollback()
                return bad_request(gettext(
                    "The specified data group already exists."
                ))

            except Exception as e:
                db.session.rollback()
                return make_json_response(
                    status=410,
                    success=0,
                    errormsg=e.message)

        else:
            return make_json_response(
                status=417,
                success=0,
                errormsg=gettext('No data group name was specified'))

    @login_required
    def sql(self, gid):
        return make_json_response(status=422)

    @login_required
    def modified_sql(self, gid):
        return make_json_response(status=422)

    @login_required
    def statistics(self, gid):
        return make_json_response(status=422)

    @login_required
    def dependencies(self, gid):
        return make_json_response(status=422)

    @login_required
    def dependents(self, gid):
        return make_json_response(status=422)

    @login_required
    def nodes(self, gid=None):
        """Return a JSON document listing the data groups for the user"""
        nodes = []

        if gid is None:
            groups = DataGroup.query.filter_by(user_id=current_user.id)

            for group in groups:
                nodes.append(
                    self.blueprint.generate_browser_node(
                        "%d" % group.id,
                        None,
                        group.name,
                        "icon-%s" % self.node_type,
                        True,
                        self.node_type
                    )
                )
        else:
            group = DataGroup.query.filter_by(user_id=current_user.id,
                                                id=gid).first()
            if not group:
                return gone(
                    errormsg=gettext("Could not find the data group.")
                )

            nodes = self.blueprint.generate_browser_node(
                "%d" % (group.id), None,
                group.name,
                "icon-%s" % self.node_type,
                True,
                self.node_type
            )

        return make_json_response(data=nodes)

    def node(self, gid):
        return self.nodes(gid)


DataGroupView.register_node_view(blueprint)