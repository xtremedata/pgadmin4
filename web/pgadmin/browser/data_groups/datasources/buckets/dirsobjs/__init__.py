##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

from boto3 import client

from flask import render_template, request, make_response, jsonify, \
    current_app, url_for
from flask_babelex import gettext
from flask_security import current_user, login_required
from pgadmin.browser.utils import NodeView
from pgadmin.utils.ajax import make_json_response, bad_request, forbidden, \
    make_response as ajax_response, internal_server_error, unauthorized, gone
import pgadmin.browser.data_groups.datasources.buckets as buckets

from .types import DirObjType
from .utils import get_dirobj_props, convert_dirobj_acl_to_props


class DirObjModule(buckets.BucketPluginModule):
    NODE_TYPE = "dirobj"
    LABEL = gettext("Objects")



    @property
    def node_type(self):
        return self.NODE_TYPE

    @property
    def script_load(self):
        """
        Load the module script for dirobj, when any of the data-group node is
        initialized.
        """
        return buckets.BucketModule.NODE_TYPE

    @property
    def jssnippets(self):
        return []

    @property
    def csssnippets(self):
        """
        Returns a snippet of css to include in the page
        """
        snippets = [render_template("css/dirsobjs.css")]

        for submodule in self.submodules:
            snippets.extend(submodule.csssnippets)

        for st in DirObjType.types():
            snippets.extend(st.csssnippets)

        return snippets


    def get_dict_node(self, obj, parent):
        do_id, name, do_type, icon, size, is_leaf = get_dirobj_props(obj)
        return {
            'id': do_id,
            'name': name,
            'type': do_type,
            'size': size,
            'leaf': is_leaf
        }

    def get_browser_node(self, gid, sid, bid, obj, **kwargs):
        do_id, name, do_type, icon, size, is_leaf = get_dirobj_props(obj)
        return self.generate_browser_node(
                "%s" % (do_id),
                None,
                name,
                icon,
                True,
                self.node_type,
                do_type=do_type,
                size=size,
                is_leaf=is_leaf,
                **kwargs)


    @login_required
    def get_nodes(self, gid, sid, bid, oid=None):
        """
        Return a JSON document listing the data sources for the user
        """

        s3 = client('s3')
        pg = s3.get_paginator('list_objects')

        for res in pg.paginate(Bucket=bid, Prefix=oid):
            errmsg = None
            if res['ResponseMetadata']['HTTPStatusCode'] == 200:
                for o in res['Contents']: 
                    yield self.get_browser_node(gid, sid, bid, o, errmsg=errmsg)



    def get_own_javascripts(self):
        scripts = []

        scripts.extend([{
            'name': 'pgadmin.dirobj.supported_dirsobjs',
            'path': url_for('browser.index') + 'dirobj/supported_dirsobjs',
            'is_template': True,
            'when': self.node_type
        }])
        scripts.extend(super().get_own_javascripts())

        return scripts


    # We do not have any preferences for dirobj node.
    def register_preferences(self):
        """
        register_preferences
        Override it so that - it does not register the show_node preference for
        dirobj type.
        """
        pass



blueprint = DirObjModule(__name__)




class DirObjNode(NodeView):
    node_type = DirObjModule.NODE_TYPE

    parent_ids = [
        {'type': 'int', 'id': 'gid'},
        {'type': 'int', 'id': 'sid'},
        {'type': 'string', 'id': 'bid'}
    ]
    ids = [
        {'type': 'string', 'id': 'oid'}
    ]

    operations = dict({
        'obj': [
            {'get': 'properties'},
            {'get': 'list'}
        ],
        'nodes': [
            {'get': 'node'},
            {'get': 'nodes'}
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
        'supported_dirsobjs.js': [
            {}, {}, {'get': 'supported_dirsobjs'}
        ],
    })


    def list_dirsobjs(self, gid, sid, bid, oid=None):
        try:
            response = client('s3').list_objects(Bucket=bid, Prefix=oid)
        except Exception as e:
            raise 
        else:
            return response['Contents']



    def get_children_nodes(self, gid, sid, bid, oid, **kwargs):
        """ Returns dependent S3 bucket objects.
        """

        res = self.list_dirsobjs(gid, sid, bid, oid)
        return [self.blueprint.get_nodes(gid, sid, bid, oid, **kwargs) for o in res]




    def list(self, gid, sid, bid):
        try:
            dirsobjs = self.list_dirsobjs(gid, sid, bid)
        except Exception as e:
            return internal_server_error(errormsg=e)
        else:
            return ajax_response(
                    response=dirsobjs,
                    status=200)



    def get_nodes(self, gid, sid, bid):
        try:
            dirsobjs = self.list_dirsobjs(gid, sid, bid)
        except Exception as e:
            return internal_server_error(errormsg=e)
        else:
            return [self.blueprint.get_browser_node(gid, sid, bid, o) for o in dirsobjs]



    def nodes(self, gid, sid, bid):
        res = self.get_nodes(gid, sid, bid)

        return make_json_response(
            data=res,
            status=200)



    def node(self, gid, sid, bid, oid):
        try:
            dirsobjs = self.list_dirsobjs(gid, sid, bid)
        except Exception as e:
            return internal_server_error(errormsg=e)
        else:
            for o in dirsobjs:
                if o['Key'] == oid:
                    return make_json_response(
                            data=self.blueprint.get_browser_node(gid, sid, bid, o),
                            status=200)

            return gone(errormsg=gettext("Could not find the object."))



    def properties(self, gid, sid, bid, oid):
        try:
            dirobj_acl = client('s3').get_object_acl(Bucket=bid, Key=oid)
        except Exception as e:
            return internal_server_error(errormsg=e)
        else:
            return ajax_response(
                    response=convert_dirobj_acl_to_props(bid, dirobj_acl),
                    status=200)

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

    def supported_dirsobjs(self, **kwargs):
        """
        This property defines (if javascript) exists for this node.
        Override this property for your own logic.
        """

        return make_response(
            render_template(
                "dirsobjs/supported_dirsobjs.js",
                dirobj_types=DirObjType.types()
            ),
            200, {'Content-Type': 'application/javascript'}
        )


DirObjNode.register_node_view(blueprint)
