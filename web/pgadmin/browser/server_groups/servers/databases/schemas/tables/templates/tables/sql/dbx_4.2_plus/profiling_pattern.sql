SELECT
    pattern AS {{ conn|qtIdent(_('Pattern')) }},
    freq_count AS {{ conn|qtIdent(_('Occurance')) }},
    freq_ratio AS {{ conn|qtIdent(_('Ratio')) }}
FROM
    dbx_profile.{{prof_table_name}}_pattern;
