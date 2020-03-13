##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################


from os import path
from boto3 import client, resource, Session
from botocore.exceptions import HTTPClientError, ClientError
from urllib.parse import unquote, urlunparse, ParseResult

from flask import current_app
from flask_security import current_user

from pgadmin.model import DataSource

from .crypto import encrypt, decrypt, pqencryptpassword
from .master_password import get_crypt_key
from .exception import CryptKeyMissing




def check_session(f):
    def wrapped(self, *args, **kw):
        if self.current_user != current_user.id:
            self.reset()
        return self.f(*args, **kw)
    return wrapped




class S3(object):
    """
    """

    NAME = 's3'
    PFX = 'https'
    AWS_S3 = 's3.amazonaws.com'
    PG_PFX = '/'



    @classmethod
    def create_https_url(cls, bucket, obj_path):
        return urlunparse(ParseResult( \
                scheme=cls.PFX, \
                netloc=("%s.%s" % (bucket, cls.AWS_S3)), \
                path=obj_path, \
                params=None, \
                query=None, \
                fragment=None))

    
    @classmethod
    def create_s3_url(cls, bucket, obj_path):
        return urlunparse(ParseResult( \
                scheme=cls.NAME, \
                netloc=bucket, \
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
        self._session = None
        self._resource = None
        self._key_name = None
        self._key_secret = None
        self._current_user = current_user.id



    @property
    def key_name(self):
        return self._key_name
    
    @property
    def key_secret(self):
        return self._key_secret

    @property
    def client(self):
        if not self._client:
            self._client = client('s3') if not self.has_authentication() \
                    else client('s3', \
                    aws_access_key_id=self.key_name, \
                    aws_secret_access_key=self.key_secret)
        return self._client

    @property
    def session(self):
        if not self._session:
            self._session = Session() if not self.has_authentication() \
                    else Session(\
                    aws_access_key_id=self.key_name, \
                    aws_secret_access_key=self.key_secret)
        return self._session

    @property
    def resource(self):
        if not self._resource:
            self._resource = self.session.resource('s3')
        return self._resource


    def reset(self):
        """ Resets all access on not authorized session request.
        """
        current_app.logger.info("Reset s3 authentication due to changed user from:%s to %s" \
                % (self._current_user, current_user.id))
        self.reload()
        self._key_name = None
        self._key_secret = None
        self._current_user = current_user.id


    def reload(self):
        """ Reloads all S3 sessions.
        """
        self._client = None
        self._session = None
        self._resource = None


    def has_authentication(self):
        return self.key_name and self.key_secret


    def authenticate(self, gid, sid, ds=None):
        """ Updates S3 authentication from provided datasource Id.
        """
        crypt_key_present, crypt_key = get_crypt_key()
        if not crypt_key_present:
            raise CryptKeyMissing

        if ds is None:
            ds = DataSource.query.filter_by( \
                    user_id=current_user.id, \
                    datagroup_id=gid, \
                    id=sid).first()

        if ds.key_name and ds.key_secret:
            decrypted_key_secret = decrypt(ds.key_secret, crypt_key)
            if isinstance(decrypted_key_secret, bytes):
                decrypted_key_secret = decrypted_key_secret.decode()
            self._key_name = ds.key_name
            self._key_secret = decrypted_key_secret
            self.reload()


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
