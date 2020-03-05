##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################


from os import path
from boto3 import client, resource
from botocore.exceptions import HTTPClientError, ClientError
from urllib.parse import unquote, urlunparse, ParseResult



class S3(object):
    """
    """

    NAME = 's3'
    PFX = 'https'
    AWS_S3 = 's3.amazonaws.com'
    PG_PFX = '/'


    @classmethod
    def create_url(cls, bucket, obj_path):
        return urlunparse(ParseResult( \
                scheme=cls.PFX, \
                netloc=("%s.%s" % (bucket, cls.AWS_S3)), \
                path=obj_path, \
                params=None, \
                query=None, \
                fragment=None))


    @classmethod
    def fix_pgadmin_path(cls, path):
        """ Normalizes pgadmin path for s3 path.
        """
        spath = None
        if path:
            spath = unquote(path).encode('utf-8').decode('utf-8')
            if spath.startswith(cls.PG_PFX):
                spath = spath[len(cls.PG_PFX):]
        return spath


    @classmethod
    def is_dir(cls, s3key):
        """ Returns true if path is a directory.
        """
        return s3key.endswith(path.sep)


    @classmethod
    def is_child(cls, o1, o2_path):
        """ Returns True if o1 is child of o2.
        """
        key = o1['Key'] if isinstance(o1, dict) \
                else o1 if isinstance(o1, str) \
                else o1.key if o1 \
                else ''
        return key.startswith(o2_path) and len(key) != len(o2_path) if key and o2_path \
                else (key.find(path.sep) == -1 or key[-1] == path.sep) if not o2_path \
                else False


    @classmethod
    def s3obj_to_s3dict(cls, s3obj):
        """ Converts boto3 object to dictionary.
        """
        return {\
                'Key': s3obj.key, \
                'LastModified': s3obj.last_modified, \
                'Size': s3obj.content_length}



    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._client = None
        self._resource = None



    @property
    def client(self):
        if not self._client:
            self._client = client('s3')
        return self._client

    @property
    def resource(self):
        if not self._resource:
            self._resource = resource('s3')
        return self._resource


    def exists(self, bucket, obj):
        try:
            o = self.resource.Object(bucket, obj)
            o.load()

        except (HTTPClientError, ClientError) as e:
            if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
                return False
            else:
                raise

        else:
            return True
