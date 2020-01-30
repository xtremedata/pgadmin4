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

import pgadmin.browser.data_groups.datasources as datasource
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
    COLLECTION_LABEL = _("Bucket")

    def __init__(self, *args, **kwargs):
        self.min_ver = None
        self.max_ver = None
        super().__init__(*args, **kwargs)
        self.inode = False


    def get_browser_node(self, gid, sid, bucket):
        """ Simplifies browser node generation.
        """

        return self.generate_browser_node(
                bucket['Name'],
                sid,
                bucket['Name'],
                "icon-bucket")


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
    })



    def list_buckets(self, gid, sid):
        try:
            response = client('s3').list_buckets()
        except Exception as e:
            raise 
        else:
            return response['Buckets']



    def list(self, gid, sid):
        try:
            buckets = self.list_buckets(gid, sid)
        except Exception as e:
            return internal_server_error(errormsg=e)
        else:
            return ajax_response(
                    response=buckets,
                    status=200)



    def get_nodes(self, gid, sid):
        try:
            buckets = self.list_buckets(gid, sid)
        except Exception as e:
            return internal_server_error(errormsg=e)
        else:
            return [self.blueprint.get_browser_node(gid, sid, b) for b in buckets]



    def nodes(self, gid, sid):
        res = self.get_nodes(gid, sid)

        return make_json_response(
            data=res,
            status=200)



    def node(self, gid, sid, did):
        try:
            buckets = self.list_buckets(gid, sid)
        except Exception as e:
            return internal_server_error(errormsg=e)
        else:
            for b in buckets:
                if b['Name'] == did:
                    return make_json_response(
                            data=self.blueprint.get_browser_node(gid, sid, b),
                            status=200)

            return gone(errormsg=_("Could not find the bucket."))



    def properties(self, gid, sid, did):
        try:
            bucket_acl = client('s3').get_bucket_acl(Bucket=did)
        except Exception as e:
            return internal_server_error(errormsg=e)
        else:
            return ajax_response(
                    response=convert_bucket_acl_to_props(did, bucket_acl),
                    status=200)


BucketView.register_node_view(blueprint)
