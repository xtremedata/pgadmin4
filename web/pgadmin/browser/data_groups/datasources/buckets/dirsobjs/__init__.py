##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

from fnmatch import fnmatch

from botocore.exceptions import HTTPClientError, ClientError

from flask import render_template, request, make_response, jsonify, \
    current_app, url_for
from flask_babelex import gettext
from flask_security import current_user, login_required
from pgadmin.browser.utils import NodeView
from pgadmin.utils.s3 import S3
from pgadmin.utils.ajax import \
        make_json_response, \
        bad_request, \
        forbidden, \
        make_response as ajax_response, \
        internal_server_error, \
        unauthorized, \
        gone
from pgadmin.model import DataSource
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



    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._s3 = None



    @property
    def s3(self):
        if not self._s3:
            self._s3 = S3()
        return self._s3



    def _reload(self, gid, sid, ds=None):
        try:
            if ds is None:
                ds = DataSource.query.filter_by(
                    user_id=current_user.id,
                    datagroup_id=gid,
                    id=sid).first()
            self.s3.authenticate(gid, sid, ds=ds)
        except Exception as e:
            current_app.logger.exception(e)
            raise
        else:
            if not ds:
                raise KeyError(gettext('Not found datasource:%d') % sid)



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



    def _filter(self, bid, oid, ds):
        return (not ds.pattern or fnmatch(bid, ds.pattern)) \
                and (not ds.pfx or oid['Key'].startswith(ds.pfx))



    def _get_node(self, gid, sid, bid, oid):
        try:
            o = self.s3.resource.Object(bid, oid)
            o.load()
            return o
        except (HTTPClientError, ClientError) as e:
            current_app.logger.exception(e)
            if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
                raise KeyError(gettext('Not found object:%s') % oid[:50])
            else:
                raise
        except Exception as e:
            current_app.logger.exception(e)
            raise



    def _get_nodes(self, gid, sid, bid, oid=None):
        """
        """
        errmsg = None
        ds = DataSource.query.filter_by(
            user_id=current_user.id,
            datagroup_id=gid,
            id=sid).first()
        if not oid:
            oid = ds.pfx

        if oid is None:
            oid = ''

        self._reload(gid, sid, ds)

        #pg = s3.get_paginator('list_objects_v2')
        try:
            res = self.s3.client.list_objects_v2(Bucket=bid, Prefix=oid)
        except (HTTPClientError, ClientError) as e:
            current_app.logger.exception(e)
            if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
                raise KeyError(gettext('Not found bucket:%s') % bid[:50])
            else:
                raise
        except Exception as e:
            current_app.logger.exception(e)
            raise
        else:
            if res['ResponseMetadata']['HTTPStatusCode'] != 200:
                raise KeyError(gettext('Not found bucket:%s') % bid[:50])
            else:
                try:
                    return [o for o in res['Contents'] if self._filter(bid, o, ds) and is_child(o, gid, sid, bid, oid)]
                except KeyError:
                    return []



    @login_required
    def get_dict_node(self, gid, sid, bid, oid):
        """
        """
        return self._get_dict_node( \
                convert_s3dirobj_to_dirobj(self._get_node(gid, sid, bid, oid)))



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
        try:
            return [o for o in self.blueprint.get_nodes(gid, sid, bid, oid, **kwargs)]
        except KeyError as e:
            return bad_request(errormsg=str(e))
        except Exception as e:
            return internal_server_error(errormsg=str(e))




    def list(self, gid, sid, bid, oid=None):
        try:
            dirsobjs = self.blueprint.get_dict_nodes(gid, sid, bid, oid)
        except KeyError as e:
            return bad_request(errormsg=str(e))
        except Exception as e:
            return internal_server_error(errormsg=str(e))
        else:
            return ajax_response(response=dirsobjs, status=200)



    def get_nodes(self, gid, sid, bid, oid=None):
        return [o for o in self.blueprint.get_nodes(gid, sid, bid, oid)]



    def nodes(self, gid, sid, bid, oid=None):
        try:
            dirsobjs = self.get_nodes(gid, sid, bid, oid)
        except KeyError as e:
            return bad_request(errormsg=str(e))
        except Exception as e:
            return internal_server_error(errormsg=str(e))
        else:
            return make_json_response(data=dirsobjs, status=200)



    def node(self, gid, sid, bid, oid):
        try:
            dirobj = self.blueprint.get_node(gid, sid, bid, oid)
        except KeyError as e:
            return gone(errormsg=str(e))
        except Exception as e:
            return internal_server_error(errormsg=str(e))
        else:
            return make_json_response(data=dirobj, status=200)




    @login_required
    def properties(self, gid, sid, bid, oid):
        try:
            dirobj = self.blueprint.get_dict_node(gid, sid, bid, oid)
        except KeyError as e:
            return bad_request(errormsg=str(e))
        except Exception as e:
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
