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
from flask import request, jsonify, current_app
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
    LABEL = gettext("Data Groups")


    def get_dict_node(self, group):
        return {'id': group.id, 'name': group.name}


    def get_browser_node(self, group, **kwargs):
        return self.generate_browser_node(
                "%d" % (group.id),
                None,
                group.name,
                "icon-%s" % self.node_type,
                True,
                self.node_type,
                can_delete=group.can_delete,
                **kwargs)


    def _get_nodes(self, gid, **kwargs):
        """Return a JSON document listing the data groups for the user"""
        if gid:
            groups = DataGroup.query.filter_by(user_id=current_user.id, id=gid).first()
        else:
            groups = DataGroup.query.filter_by(user_id=current_user.id).order_by("id")

        if groups:
            for group in groups:
                yield group


    def get_nodes(self, gid=None, **kwargs):
        """Return a JSON document listing the data groups for the user"""

        for group in self._get_nodes(gid, **kwargs):
            yield self.get_browser_node(group)


    def get_dict_nodes(self, gid=None, **kwargs):
        """ Returns a list of dictionaries with properties of matching nodes.
        """
        for group in self._get_nodes(gid, **kwargs):
            yield self.get_dict_node(group)


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
    def get_browser_node(self, obj, **kwargs):
        pass

    @abstractmethod
    def get_nodes(self, *arg, **kwargs):
        pass



blueprint = DataGroupModule(__name__)





class DataGroupView(NodeView):
    node_type = DataGroupModule.NODE_TYPE

    parent_ids = []
    ids = [{'type': 'int', 'id': 'gid'}]

    @login_required
    def nodes(self, gid=None):
        """Return a JSON document listing the data groups for the user"""
        nodes = None
        groups = [g for g in self.blueprint.get_nodes(gid)]

        if gid is None:
            nodes = groups
        elif groups:
            nodes = groups[0]

        try:
            return make_json_response(data=nodes)
        except IndexError:
            return gone(errormsg=gettext(
                        "Could not find the data group {0}."
                        ).format(gid))

    def node(self, gid):
        return self.nodes(gid)

    @login_required
    def list(self):
        groups = [g for g in self.blueprint.get_dict_nodes()]
        groups.sort_by('name')
        return ajax_response(response=groups, status=200)

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
                    status=410, success=0, errormsg=e
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
                    status=410, success=0, errormsg=e
                )

        return jsonify(node=self.blueprint.get_browser_node(datagroup))

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
                    name=data[u'name'],
                    can_delete=True)
                db.session.add(dg)
                db.session.commit()

                data[u'id'] = dg.id
                data[u'name'] = dg.name

                return jsonify(node=self.blueprint.get_browser_node(dg))
            except exc.IntegrityError as e:
                db.session.rollback()
                current_app.logger.exception(e)
                return bad_request(gettext(
                    "The specified data group already exists."
                ))

            except Exception as e:
                db.session.rollback()
                return make_json_response(
                    status=410,
                    success=0,
                    errormsg=e)

        else:
            return make_json_response(
                status=417,
                success=0,
                errormsg=gettext(
                    'No data group name was specified'
                ))

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


DataGroupView.register_node_view(blueprint)
