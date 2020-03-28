SELECT
    freq_val AS {{ conn|qtIdent(_('Top N value')) }},
    freq_count AS {{ conn|qtIdent(_('Occurance count')) }},
    freq_ratio AS {{ conn|qtIdent(_('Occurance ratio to total')) }}
FROM
    dbx_profile.{{prof_table_name}}_topn
WHERE
    colname = '{{col_name}}';

