##########################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2013 - 2020, The pgAdmin Development Team
# This software is released under the PostgreSQL Licence
#
##########################################################################

"""Object helper utilities"""



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



def dirobj_icon_and_background(dirobj):
    """

    Args:
        is_connected: Flag to check if dirobj is connected
        dirobj: Sever object

    Returns:
        DataSource Icon CSS class
    """
    dirobj_background_color = ''
    if dirobj and dirobj.bgcolor:
        dirobj_background_color = ' {0}'.format(
            dirobj.bgcolor)
        # If user has set font color also
        if dirobj.fgcolor:
            dirobj_background_color = '{0} {1}'.format(
                dirobj_background_color,
                dirobj.fgcolor)

    return 'icon-{0}{1}'.format(
        dirobj.do_type, dirobj_background_color)
