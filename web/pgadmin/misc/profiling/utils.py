################################################################################
#
# pgAdmin 4 - PostgreSQL Tools
#
# Copyright (C) 2020, Xtremedata Inc
#
################################################################################


class XdProfiling(object):
    """ dbX Profiling.
    """

    COLUMNT_SFXS = ('pattern', 'histo', 'rank', 'topn')
    TABLES_SFXS = ('profile',) + COLUMNT_SFXS

    
