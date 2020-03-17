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
from pgadmin.utils.s3 import S3

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
    def s3dict_to_filedesc(cls, s3obj):
        """ Converts S3 object into filemanger dictionary.
            @returns (is_dir_flag, object name, object description or (None, None, error description)
        """
        if s3obj is None:
            return None

        try:
            obj_name = s3obj['Key']
            obj_mtime = s3obj['LastModified']
            obj_size = s3obj['Size']
        except KeyError as e:
            return (None, None, cls.fail_response('Invalid S3 data: %s' % str(e)[:100]))

        else:
            if not obj_name:
                return (None, None, cls.fail_response('Received S3 object with no name'))

            Filename = ''
            Path = ''
            Protected = 0
            FileType = u''
            IsDir = S3.is_dir(obj_name)
            if IsDir:
                FileType = u'dir'
                Path, Filename = path.split(obj_name[:-1])
            else:
                _, FileType = path.splitext(obj_name)
                Path, Filename = path.split(obj_name)

            Path = path.join(path.sep, obj_name)
            FileType = FileType.lstrip('.')
            return (IsDir, Filename, {
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
        self.s3 = S3()
        if self.ds_info:
            try:
                self.ds = DataSource.query.filter_by(
                        user_id=current_user.id,
                        id=self.ds_info['ds_id']).first()
            except Exception as e:
                current_app.logger.debug("No authenticatation, exception:%s" % str(e))
                pass

            else:
                self.s3.authenticate(self.ds.datagroup_id, self.ds.id)
                current_app.logger.debug("Authenticated %s with datasource %s credentials" \
                        % (self.TYPE, self.ds.id))



    def getfolder(self, path=None, file_type="", name=None, req=None,
                  show_hidden=False):
        trans_data = self.get_trasaction_selection(self.trans_id)
        if not config.SERVER_MODE:
            return True

        self.suspend_windows_warning()

        path = self.s3.fix_pgadmin_path(path)
        bucket = self.ds_info['ds_bucket']

        res = self.s3.client.list_objects_v2(Bucket=bucket, Prefix=path)
        res_status = res['ResponseMetadata']['HTTPStatusCode']
        contents = []
        objects = {}

        if res_status != 200:
            return self.fail_response('Error accessing S3 storage:%i' % res_status)

        folders_only = trans_data['folders_only'] \
            if 'folders_only' in trans_data else ''
        files_only = trans_data['files_only'] \
            if 'files_only' in trans_data else ''
        supported_types = trans_data['supported_types'] \
            if 'supported_types' in trans_data else []

        supp_filter = lambda obj: True if not supported_types or '*' in supported_types \
                else obj['FileType'] in supported_types
        sel_filter = lambda obj: True if not file_type or file_type == '*' \
                else obj['FileType'] == file_type

        try:
            contents = res['Contents']
        except KeyError:
            objects = {}
        else:
            for o in contents:
                if self.s3.is_child(o, path):
                    is_dir, name, desc = self.s3dict_to_filedesc(o)
                    if name is None:
                        return desc
                    # below cannot be used based on how 'folders_only' and 'files_only' are set
                    # elif is_dir and files_only:
                    #    continue
                    elif not is_dir and folders_only:
                        continue
                    elif is_dir or sel_filter(desc) and supp_filter(desc):
                        objects[name] = desc

        self.resume_windows_warning()
        return objects


    def getinfo(self, path=None, getsize=True, name=None, req=None):
        """ Returns a JSON object containing information
            about the given file.
        """
        path = self.s3.fix_pgadmin_path(path)

        try:
            s3obj = self.s3.resource.Object(self.ds_info['ds_bucket'], path)
            s3obj.load()
        except (HTTPClientError, ClientError) as e:
            try:
                if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
                    return self.not_found_response(path)
                
                else:
                    return self.fail_response(str(e))

            except Exception as e2:
                return self.fail_response(str(e2))


        _, _, desc = self.s3dict_to_filedesc(self.s3.s3obj_to_s3dict(s3obj))
        return desc



Filemanager.register(S3Manager.TYPE, S3Manager)
