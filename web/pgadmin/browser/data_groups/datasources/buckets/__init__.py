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
from abc import ABCMeta, abstractmethod

import six
import simplejson as json

from flask import render_template, current_app, request, jsonify
from flask_babelex import gettext as _
from flask_security import current_user, login_required

import pgadmin.browser.data_groups.datasources as datasource
from pgadmin.browser import BrowserPluginModule
from pgadmin.browser.collection import CollectionNodeModule
from pgadmin.browser.utils import NodeView
from pgadmin.utils.ajax import \
         make_json_response, \
         make_response as ajax_response, \
         internal_server_error, \
         unauthorized, \
         gone
from pgadmin.model import DataSource

from .utils import convert_bucket_acl_to_props


class BucketModule(CollectionNodeModule):
    NODE_TYPE = 'bucket'
    COLLECTION_LABEL = _("Buckets")

    def __init__(self, *args, **kwargs):
        self.min_ver = None
        self.max_ver = None
        super().__init__(*args, **kwargs)
        self.inode = False


    def get_dict_node(self, gid, sid, bucket, owner):
        return {
                'id': bucket['Name'],
                'name' : bucket['Name'],
                'creationdate': bucket['CreationDate'],
                'dataowner': owner,
                'parent_id': sid }


    def get_browser_dict_node(self, gid, sid, bucket_dict):
        """ Simplifies browser node generation.
        """
        return self.generate_browser_node(
                bucket_dict['id'],
                bucket_dict['parent_id'],
                bucket_dict['name'],
                "icon-bucket",
                creationdate=bucket_dict['creationdate'],
                dataowner=bucket_dict['dataowner'])


    def get_browser_node(self, gid, sid, bucket, owner):
        """ Simplifies browser node generation.
        """
        return self.get_browser_dict_node(gid, sid, 
                self.get_dict_node(gid, sid, bucket, owner))


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
                node_type=self.node_type),
            render_template(
                "css/bucket.css")
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



@six.add_metaclass(ABCMeta)
class BucketPluginModule(BrowserPluginModule):
    """
    Base class for data group plugins.
    """

    @abstractmethod
    def get_browser_node(self, obj, **kwargs):
        pass

    @abstractmethod
    def get_nodes(self, *arg, **kwargs):
        pass



blueprint = BucketModule(__name__)



class BucketView(NodeView):
    node_type = blueprint.node_type

    parent_ids = [
        {'type': 'int', 'id': 'gid'},
        {'type': 'int', 'id': 'sid'}
    ]
    ids = [
        {'type': 'string', 'id': 'bid'}
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
        'get_bucket_acl': [
            {'get': 'get_bucket_acl'}
        ],
    })



    def _list_buckets(self, gid, sid):
        try:
            response = client('s3').list_buckets()
        except Exception as e:
            raise 
        else:
            return (response['Buckets'], response['Owner']['DisplayName'])


    def _get_bucket(self, gid, sid, bid):
        try:
            buckets, owner = self._list_buckets(gid, sid)
        except Exception as e:
            return internal_server_error(errormsg=str(e))
        else:
            for b in buckets:
                if b['Name'] == bid:
                    return self.blueprint.get_dict_node(gid, sid, b, owner)

            raise KeyError(bid)



    def _get_bucket_acl(self, gid, sid, bid):
        try:
            response = client('s3').get_bucket_acl(Bucket=bid)
        except Exception as e:
            current_app.logger.exception(e)
            raise 
        else:
            return convert_bucket_acl_to_props(bid, response)



    def list(self, gid, sid):
        try:
            buckets, owner = self._list_buckets(gid, sid)
        except Exception as e:
            return internal_server_error(errormsg=str(e))
        else:
            return ajax_response(
                    response=[self.blueprint.get_dict_node(gid, sid, b, owner) for b in buckets],
                    status=200)



    def get_nodes(self, gid, sid):
        buckets, owner = self._list_buckets(gid, sid)
        return [self.blueprint.get_browser_node(gid, sid, b, owner) for b in buckets]



    def nodes(self, gid, sid):
        try:
            res = self.get_nodes(gid, sid)
        except Exception as e:
            current_app.logger.exception(e)
            return internal_server_error(errormsg=str(e))
        else:
            return make_json_response(data=res, status=200)



    def node(self, gid, sid, bid):
        try:
            bucket = self._get_bucket(gid, sid, bid)
        except KeyError:
            return gone(errormsg=_("Could not find the bucket."))
        except Exception as e:
            current_app.logger.exception(e)
            return internal_server_error(errormsg=str(e))
        else:
            return make_json_response(
                    data=self.blueprint.get_browser_dict_node(gid, sid, bucket),
                    status=200)



    def get_bucket_acl(self, gid, sid, bid):
        try:
            bucket_acl = self._get_bucket_acl(gid, sid, bid)
        except Exception as e:
            current_app.logger.exception(e)
            return internal_server_error(errormsg=str(e))
        else:
            return ajax_response(response=bucket_acl, status=200)



    @login_required
    def properties(self, gid, sid, bid):
        try:
            bucket = self._get_bucket(gid, sid, bid)
            bucket_acl = self._get_bucket_acl(gid, sid, bid)
            bucket_acl.update(bucket)
        except Exception as e:
            current_app.logger.exception(e)
            return internal_server_error(errormsg=str(e))
        else:
            return ajax_response(response=bucket_acl, status=200)



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


BucketView.register_node_view(blueprint)
