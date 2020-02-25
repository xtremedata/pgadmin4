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

from flask import current_app

import config
from . import Filemanager
from .utils import sizeof_fmt




class S3Manager(Filemanager):

    TYPE = 'S3'


    @classmethod
    def fix_pgadmin_path(cls, path):
        return path if not path else path[1:]


    @classmethod
    def fail_response(cls, errmsg):
        cls.resume_windows_warning()
        err_msg = u"Error: {0}".format(errmsg)
        return {
                'Code': 0,
                'Error': err_msg
                }


    @classmethod
    def is_dir(cls, s3key):
        return s3key.endswith(path.sep)


    @classmethod
    def s3obj_to_filedesc(cls, s3obj):
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
                FileType = u'Dir'
                Path, Filename = path.split(obj_name[:-1])
            else:
                _, FileType = path.splitext(obj_name)
                Path, Filename = path.split(obj_name)

            return (Filename, {
                "Filename": Filename,
                "Path": Path,
                "file_type": FileType,
                "Protected": Protected,
                "Properties": {
                    "Date Created": '',
                    "Date Modified": obj_mtime,
                    "Size": sizeof_fmt(obj_size)
                    }
                })



    def getfolder(self, path=None, file_type="", name=None, req=None,
                  show_hidden=False):
        trans_data = self.get_trasaction_selection(self.trans_id)
        if not config.SERVER_MODE:
            return True

        self.suspend_windows_warning()

        path = self.fix_pgadmin_path(path)

        s3 = client('s3')
        res = s3.list_objects_v2(Bucket='oleg-test', Prefix=path)
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
                name, desc = self.s3obj_to_filedesc(o)
                if name is None:
                    return desc
                else:
                    objects[name] = desc

        current_app.logger.info("####### path:%s, st:%i, res:%s, obj:%s" % (path,res_status, str(res), str(objects)))
        self.resume_windows_warning()
        return objects



Filemanager.register(S3Manager.TYPE, S3Manager)
