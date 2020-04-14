SELECT
    likely_type AS {{ conn|qtIdent(_('Likely type')) }},
    rows_tot AS {{ conn|qtIdent(_('Rows Total')) }},
    rows_null AS {{ conn|qtIdent(_('Rows Null')) }},
    rows_blank AS {{ conn|qtIdent(_('Rows blank')) }},
    rows_zero AS {{ conn|qtIdent(_('Rows zero')) }},
    width_min AS {{ conn|qtIdent(_('Width min')) }},
    width_max AS {{ conn|qtIdent(_('Width max')) }},
    width_avg AS {{ conn|qtIdent(_('Width avg')) }},
    uniq_cnt AS {{ conn|qtIdent(_('Uniq count')) }},
    uniq_hll AS {{ conn|qtIdent(_('Uniq estimate')) }},
    val_min AS {{ conn|qtIdent(_('Val min')) }},
    val_max AS {{ conn|qtIdent(_('Val max')) }},
    val_mode AS {{ conn|qtIdent(_('Most freq value')) }},
    type_min AS {{ conn|qtIdent(_('Type min')) }},
    type_max AS {{ conn|qtIdent(_('Type max')) }},
    type_mode AS {{ conn|qtIdent(_('Type most freq value')) }},
    val_amean AS {{ conn|qtIdent(_('Val aritmethic mean')) }},
    val_gmean AS {{ conn|qtIdent(_('Val geometric mean')) }},
    val_stddev AS {{ conn|qtIdent(_('Val stddev')) }},
    cnt_rank AS {{ conn|qtIdent(_('Count min/max in "rank"')) }},
    cnt_topn AS {{ conn|qtIdent(_('Count most common in "topn"')) }},
    cnt_histo AS {{ conn|qtIdent(_('Number of histogram samples')) }},
    cnt_pattern AS {{ conn|qtIdent(_('Number of distinct patterns')) }},
    skew_est AS {{ conn|qtIdent(_('Skew estimate')) }},
    type_note AS {{ conn|qtIdent(_('Type note')) }}
FROM
    dbx_profile.{{prof_table_name}}_profile
WHERE
    colname = '{{col_name}}';
