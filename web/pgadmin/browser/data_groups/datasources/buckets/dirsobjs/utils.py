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




def convert_s3dirobj_to_dirobj(s3dirobj):
    """ Converts S3 bucket object acl (see s3 documentation) to pgadmin properties.
    """

    if s3dirobj is None:
        return None
    else:
        return {
            'Key': s3dirobj.key,
            'Size': s3dirobj.content_length,
            'Bucket': s3dirobj.bucket_name,
            'MTime': s3dirobj.last_modified
        }




def convert_dirobj_to_dict(dirobj):
    """ Converts S3 bucket object acl (see s3 documentation) to pgadmin properties.
    """

    if dirobj is None:
        return None

    key = dirobj['Key']
    do_type = _dirobj_type(dirobj).dirobj_type
    icon = dirobj_icon_and_background(dirobj, do_type=do_type)
    is_leaf = not key.endswith(path.sep)
    name = path.basename(key) if is_leaf else path.basename(key[:-1]),
    size = dirobj['Size']
    try:
        bucket = dirobj['Bucket']
    except KeyError:
        bucket = None
    try:
        mtime = dirobj['MTime']
    except KeyError:
        mtime = None

    return {
        'id': key,
        'name': name,
        'icon': icon,
        'size': size,
        'do_type': do_type,
        'is_leaf': is_leaf,
        'bucket': bucket,
        'mtime': mtime
    }




def dirobj_icon_and_background(dirobj, do_type=None):
    """

    Args:
        is_connected: Flag to check if dirobj is connected
        dirobj: Sever object

    Returns:
        DataSource Icon CSS class
    """

    return 'icon-{0}'.format(do_type if do_type else _dirobj_type(dirobj).dirobj_type)





def is_root(dirobj, key=None):
    """
    """
    try:
        if key is None:
            key = dirobj['Key']
        return key.index(path.sep) == len(key) - 1
    except ValueError:
        return False
    except KeyError:
        return False




def is_child(dirobj, gid, sid, bid, oid):
    """ Returns true if the object is child for referenced DirObj.
    """

    try:
        key = dirobj['Key']
        return is_root(dirobj, key) if not oid \
            else len(key) > len(oid) and key.startswith(oid)
    except KeyError:
        return False


