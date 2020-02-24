##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

from . import Filemanager




class S3Manager(Filemanager):


    def getfolder(self, path=None, file_type="", name=None, req=None,
                  show_hidden=False):
        pass




Filemanager.register('s3', S3Manager)
