##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################


from flask import render_template, current_app
from flask_babelex import gettext


class DirObjType(object):
    """
    DirObj Type

    Create an instance of this class to define new type of the S3 bucket object
    to support.

    In order to define new type of instance, you may want to override this
    class with overriden function - instanceOf for type checking for
    identification based on the version.
    """
    registry = dict()

    def __init__(self, dirobj_type, description, priority):
        self.do_type = dirobj_type
        self.desc = description
        self._priority = priority

        assert (dirobj_type not in DirObjType.registry)
        DirObjType.registry[dirobj_type] = self

    @property
    def icon(self):
        return "%s.svg" % self.do_type.lower()

    @property
    def dirobj_type(self):
        return self.do_type

    @property
    def description(self):
        return self.desc

    @property
    def priority(self):
        return self._priority

    @property
    def required(self):
        return [u'name', u'do_type']

    def __str__(self):
        return "Type: {0}, Description:{1}, Priority: {2}".format(
            self.do_type, self.desc, self._priority
        )

    def instanceOf(self, obj):
        return True

    @property
    def csssnippets(self):
        """
        Returns a snippet of css to include in the page
        """
        return [
            render_template(
                "css/dirobj_type.css",
                dirobj_type=self.do_type,
                icon=self.icon
            )
        ]

    @classmethod
    def types(cls):
        return sorted(
            DirObjType.registry.values(),
            key=lambda x: x.priority,
            reverse=True
        )

    @classmethod
    def type(cls, dirobj_type):
        try:
            return cls.registry[dirobj_type]
        except KeyError as e:
            current_app.logger.exception("Not implemented data source type:", e)


    def get_manager(self):
        return None





class FolderType(DirObjType):
    
    def instanceOf(self, obj):
        try:
            return str(obj['Key']).endswith('/') and obj['Size'] == 0
        except KeyError:
            return False
        except Exception as e:
            current_app.logger.exception("Failed to test S3 object for folder type:", e)
            return False





class FileType(DirObjType):
    
    def instanceOf(self, obj):
        try:
            return not str(obj['Key']).endswith('/') and obj['Size'] > 0
        except KeyError:
            return False
        except Exception as e:
            current_app.logger.exception("Failed to test S3 object for file type:", e)
            return False





class CSVType(FileType):
    
    def instanceOf(self, obj):
        try:
            return super().instanceOf(obj) and str(obj['Key']).lower().endswith('.csv')
        except KeyError:
            return False
        except Exception as e:
            current_app.logger.exception("Failed to test S3 object for CSV type:", e)
            return False





class ParquetType(FileType):
    
    def instanceOf(self, obj):
        try:
            return super().instanceOf(obj) and str(obj['Key']).lower().endswith('.par')
        except KeyError:
            return False
        except Exception as e:
            current_app.logger.exception("Failed to test S3 object for parquet type:", e)
            return False





# Default DirObj Type
DirObjType('dirobj', gettext("Object"), -1)
FolderType('folder', gettext("Folder"), 0)
FileType('file', gettext("File"), 1)
CSVType('csv', gettext("CSV"), 2)
ParquetType('parquet', gettext("Parquet"), 3)
