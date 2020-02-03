##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################


from os import path

from .types import DirObjType




"""Object helper utilities"""



def _dirobj_type(dirobj):
    """ Returns dir/obj type.
    """
    def_type = None
    for ot in DirObjType.types():
        if ot.priority < 0:
            def_type = ot
        elif ot.instanceOf(dirobj):
            return ot

    return def_type



def convert_dirobj_acl_to_props(dirobj_id, dirobj_acl):
    """ Converts S3 bucket object acl (see s3 documentation) to pgadmin properties.
    """

    try:
        dirobj_props = {
            'object': dirobj_id
        }

        dirobj_props.update(dirobj_acl)

    except KeyError as e:
        raise

    else:
        return dirobj_props



def dirobj_icon_and_background(dirobj, do_type=None):
    """

    Args:
        is_connected: Flag to check if dirobj is connected
        dirobj: Sever object

    Returns:
        DataSource Icon CSS class
    """

    return 'icon-{0}'.format(do_type if do_type else _dirobj_type(dirobj).dirobj_type)





def get_dirobj_props(dirobj):
    """ Returns basic S3 object's properties.
        Properties:
        - id
        - name (key)
        - type
        - icon name
        - size
        - is leaf
    """

    key = dirobj['Key']
    do_type = _dirobj_type(dirobj).dirobj_type
    icon = dirobj_icon_and_background(dirobj, do_type=do_type)
    size = dirobj['Size']
    is_leaf = not key.endswith(path.sep)
    return (key, key, do_type, icon, size, is_leaf)
