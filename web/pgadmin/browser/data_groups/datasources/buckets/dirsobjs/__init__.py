##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

from boto3 import client, resource as boto3_resource
from botocore.exceptions import HTTPClientError, ClientError

from flask import render_template, request, make_response, jsonify, \
    current_app, url_for
from flask_babelex import gettext
from flask_security import current_user, login_required
from pgadmin.browser.utils import NodeView
from pgadmin.utils.ajax import make_json_response, bad_request, forbidden, \
    make_response as ajax_response, internal_server_error, unauthorized, gone
import pgadmin.browser.data_groups.datasources.buckets as buckets

from .types import DirObjType
from .utils import convert_dirobj_to_dict, convert_s3dirobj_to_dirobj, is_child


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



    def _get_dict_node(self, obj):
        return convert_dirobj_to_dict(obj)



    def get_browser_node(self, gid, sid, bid, obj, **kwargs):
        obj_dict = self._get_dict_node(obj)
        is_root = obj_dict['is_root']
        is_leaf = obj_dict['is_leaf']
        parent_id = obj_dict['parent_id']
        return self.generate_browser_node(
                "%s" % obj_dict['id'],
                parent_id,
                obj_dict['name'],
                obj_dict['icon'],
                False if is_leaf else True,
                self.node_type,
                is_leaf=is_leaf,
                is_root=is_root,
                do_type=obj_dict['do_type'],
                size=obj_dict['size'],
                **kwargs)



    def _get_node(self, gid, sid, bid, oid):
        try:
            s3 = boto3_resource('s3')
            o = s3.Object(bid, oid)
            o.load()
            return o
        except (HTTPClientError, ClientError) as e:
            try:
                if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
                    raise KeyError(oid)
            except:
                raise e
            else:
                raise



    def _get_nodes(self, gid, sid, bid, oid=None):
        """
        """
        errmsg = None
        if oid is None:
            oid = ''

        s3 = client('s3')
        #pg = s3.get_paginator('list_objects_v2')
        res = s3.list_objects_v2(Bucket=bid, Prefix=oid)
        if res['ResponseMetadata']['HTTPStatusCode'] == 200:
            return [o for o in res['Contents'] if is_child(o, gid, sid, bid, oid)]
        else:
            raise KeyError(bid)



    @login_required
    def get_dict_node(self, gid, sid, bid, oid):
        """
        """
        return self._get_dict_node(convert_s3dirobj_to_dirobj(self._get_node(gid, sid, bid, oid)))



    @login_required
    def get_node(self, gid, sid, bid, oid):
        """
        """
        n = self._get_node(gid, sid, bid, oid)
        n1 = convert_s3dirobj_to_dirobj(n)
        return self.get_browser_node(gid, sid, bid,
                convert_s3dirobj_to_dirobj(self._get_node(gid, sid, bid, oid)))




    @login_required
    def get_dict_nodes(self, gid, sid, bid, oid=None):
        """
        """
        return [self._get_dict_node(obj) for obj in self._get_nodes(gid, sid, bid, oid)]



    @login_required
    def get_nodes(self, gid, sid, bid, oid=None):
        """
        Return a JSON document listing the data sources for the user
        """
        errmsg = None
        for o in self._get_nodes(gid, sid, bid, oid):
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
        {'type': 'path', 'id': 'oid'}
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



    def get_children_nodes(self, gid, sid, bid, oid, **kwargs):
        """ Returns dependent S3 bucket objects.
        """
        return [o for o in self.blueprint.get_nodes(gid, sid, bid, oid, **kwargs)]




    def list(self, gid, sid, bid, oid=None):
        try:
            dirsobjs = self.blueprint.get_dict_nodes(gid, sid, bid, oid)
        except Exception as e:
            return internal_server_error(errormsg=str(e))
        else:
            return ajax_response(response=dirsobjs, status=200)



    def get_nodes(self, gid, sid, bid, oid=None):
        return [o for o in self.blueprint.get_nodes(gid, sid, bid, oid)]



    def nodes(self, gid, sid, bid, oid=None):
        try:
            dirsobjs = self.get_nodes(gid, sid, bid, oid)
        except Exception as e:
            current_app.logger.exception(e)
            return internal_server_error(errormsg=str(e))
        else:
            return make_json_response(data=dirsobjs, status=200)



    def node(self, gid, sid, bid, oid):
        try:
            dirobj = self.blueprint.get_node(gid, sid, bid, oid)
        except KeyError:
            return gone(errormsg=gettext("Could not find the object."))
        except Exception as e:
            current_app.logger.exception(e)
            return internal_server_error(errormsg=str(e))
        else:
            return make_json_response(data=dirobj, status=200)




    @login_required
    def properties(self, gid, sid, bid, oid):
        try:
            dirobj = self.blueprint.get_dict_node(gid, sid, bid, oid)
        except Exception as e:
            current_app.logger.exception(e)
            return internal_server_error(errormsg=str(e))
        else:
            return ajax_response(response=dirobj, status=200)



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
                do_types=DirObjType.types()
            ),
            200, {'Content-Type': 'application/javascript'}
        )


DirObjNode.register_node_view(blueprint)
