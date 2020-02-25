##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################


from os import path
from boto3 import client, resource as boto3_resource
from botocore.exceptions import HTTPClientError, ClientError

from flask import current_app
from flask_babelex import gettext
from flask_security import current_user, login_required
from pgadmin.model import db, DataSource, DataGroup

import config
from . import Filemanager
from .utils import sizeof_fmt

# import unquote from urlib for python2.x and python3.x
try:
    from urllib import unquote
except Exception as e:
    from urllib.parse import unquote



class S3Manager(Filemanager):

    TYPE = 'S3'


    @classmethod
    def fix_pgadmin_path(cls, path):
        return path if not path \
                else unquote(path).encode('utf-8').decode('utf-8')[1:]


    @classmethod
    def fail_response(cls, errmsg):
        cls.resume_windows_warning()
        err_msg = u"Error: {0}".format(errmsg)
        return {
                'Code': 0,
                'Error': err_msg
                }


    @classmethod
    def denied_response(cls):
        cls.resume_windows_warning()
        err_msg = gettext("Permission denied")
        return {
                'Code': 0,
                'Error': err_msg
                }


    @classmethod
    def not_found_response(cls, path, resume=False):
        if resume:
            cls.resume_windows_warning()
        err_msg = (u"'%s'" % path[:100]) + gettext("file not found.")
        return {
                'Code': 0,
                'Error': err_msg
                }


    @classmethod
    def is_dir(cls, s3key):
        return s3key.endswith(path.sep)


    @classmethod
    def s3obj_to_s3dict(cls, s3obj):
        return {
                'Key': s3obj.key,
                'LastModified': s3obj.last_modified,
                'Size': s3obj.content_length }


    @classmethod
    def s3dict_to_filedesc(cls, s3obj):
        """ Converts S3 object into filemanger dictionary.
            @returns (object name, object description or (None, error description)
        """
        if s3obj is None:
            return None

        try:
            obj_name = s3obj['Key']
            obj_mtime = s3obj['LastModified']
            obj_size = s3obj['Size']
        except KeyError as e:
            return (None, cls.fail_response('Invalid S3 data: %s' % str(e)[:100]))

        else:
            if not obj_name:
                return (None, cls.fail_response('Received S3 object with no name'))

            Filename = ''
            Path = ''
            Protected = 1
            FileType = u''
            if cls.is_dir(obj_name):
                FileType = u'dir'
                Path, Filename = path.split(obj_name[:-1])
            else:
                _, FileType = path.splitext(obj_name)
                Path, Filename = path.split(obj_name)

            Path = path.join(path.sep, Path)
            return (Filename, {
                "Error": '',
                "Code": 1,
                "Filename": Filename,
                "Path": Path,
                "FileType": FileType,
                "file_type": FileType,
                "Protected": Protected,
                "Properties": {
                    "Date Created": '',
                    "Date Modified": obj_mtime,
                    "Size": sizeof_fmt(obj_size)
                    }
                })



    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.ds = None
        if self.ds_info:
            try:
                self.ds = DataSource.query.filter_by(
                        user_id=current_user.id,
                        id=ds_info['ds_id']).first()
            except:
                pass



    def getfolder(self, path=None, file_type="", name=None, req=None,
                  show_hidden=False):
        trans_data = self.get_trasaction_selection(self.trans_id)
        if not config.SERVER_MODE:
            return True

        self.suspend_windows_warning()

        path = self.fix_pgadmin_path(path)
        bucket = self.ds_info['ds_bucket']

        s3 = client('s3')
        res = s3.list_objects_v2(Bucket=bucket, Prefix=path)
        res_status = res['ResponseMetadata']['HTTPStatusCode']
        contents = []
        objects = {}

        if res_status != 200:
            return self.fail_response('Error accessing S3 storage:%i' % res_status)

        try:
            contents = res['Contents']
        except KeyError:
            objects = {}
        else:
            for o in contents:
                name, desc = self.s3dict_to_filedesc(o)
                if name is None:
                    return desc
                else:
                    objects[name] = desc

        current_app.logger.info("####### path:%s, st:%i, res:%s, obj:%s" % (path,res_status, str(res), str(objects)))
        self.resume_windows_warning()
        return objects


    def getinfo(self, path=None, getsize=True, name=None, req=None):
        """ Returns a JSON object containing information
            about the given file.
        """
        path = self.fix_pgadmin_path(path)

        try:
            s3 = boto3_resource('s3')
            s3obj = s3.Object(self.ds_info['ds_bucket'], path)
            s3obj.load()
        except (HTTPClientError, ClientError) as e:
            try:
                if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
                    return self.not_found_response(path)

            except Exception as e2:
                return self.fail_response(str(e2))


        return self.s3dict_to_filedesc(self.s3obj_to_s3dict(s3obj))



Filemanager.register(S3Manager.TYPE, S3Manager)
