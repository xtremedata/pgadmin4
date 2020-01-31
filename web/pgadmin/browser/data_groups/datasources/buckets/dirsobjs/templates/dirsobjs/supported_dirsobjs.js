/////////////////////////////////////////////////////////////
//
// pgAdmin 4 - PostgreSQL Tools
//
// Copyright (C) 2013 - 2020, The pgAdmin Development Team
// This software is released under the PostgreSQL Licence
//
//////////////////////////////////////////////////////////////

define(
  'pgadmin.dirobj.supported_dirsobjs',
  ['sources/gettext'],
  function(gettext) {
    return [
      {% for dst in dirobj_types %}

      {label: '{{ dst.description }}', value: '{{ dst.dirobj_type }}'},{% endfor %}

      {label: gettext('Unknown'), value: ''}
    ];
  }
);
