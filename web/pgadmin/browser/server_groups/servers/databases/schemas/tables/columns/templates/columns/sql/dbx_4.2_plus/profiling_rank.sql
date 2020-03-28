SELECT
    rank AS {{ conn|qtIdent(_('Rank')) }},
    val_min AS {{ conn|qtIdent(_('Value min')) }},
    val_max AS {{ conn|qtIdent(_('Value max')) }},
    type_min AS {{ conn|qtIdent(_('Type based min')) }},
    type_max AS {{ conn|qtIdent(_('Type based max')) }}
FROM
    dbx_profile.{{prof_table_name}}_rank
WHERE
    colname = '{{col_name}}';

