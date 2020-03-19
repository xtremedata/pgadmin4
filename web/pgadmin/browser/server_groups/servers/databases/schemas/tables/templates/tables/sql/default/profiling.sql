SELECT
    prfrelid AS {{ conn|qtIdent(_('Profiling 1')) }},
    prfresid AS {{ conn|qtIdent(_('Profiling 2')) }},
    prfauxtopn AS {{ conn|qtIdent(_('Profiling 3')) }},
    prfauxhist AS {{ conn|qtIdent(_('Profiling 3')) }}
FROM
    dbx_profileinfo
