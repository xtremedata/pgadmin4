/////////////////////////////////////////////////////////////
//
// pgAdmin 4 - PostgreSQL Tools
//
// Copyright (C) 2013 - 2020, The pgAdmin Development Team
// This software is released under the PostgreSQL Licence
//
//////////////////////////////////////////////////////////////

define(
  'pgadmin.datasource.supported_objtypes',
  ['sources/gettext'],
  function(gettext) {
    return [
      {% for k, v in obj_types.items() %}

      {label: '{{ k }}', value: '{{ v }}'},{% endfor %}
    ];
  }
);
