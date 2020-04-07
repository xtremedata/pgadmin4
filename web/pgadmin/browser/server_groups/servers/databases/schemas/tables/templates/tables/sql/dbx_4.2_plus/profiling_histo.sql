SELECT
    val_histo AS {{ conn|qtIdent(_('Histogram value')) }}
FROM
    dbx_profile.{{prof_table_name}}_histo;
