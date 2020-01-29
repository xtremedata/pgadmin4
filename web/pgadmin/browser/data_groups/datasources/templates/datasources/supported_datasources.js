/////////////////////////////////////////////////////////////
//
// pgAdmin 4 - PostgreSQL Tools
//
// Copyright (C) 2013 - 2020, The pgAdmin Development Team
// This software is released under the PostgreSQL Licence
//
//////////////////////////////////////////////////////////////

define(
  'pgadmin.datasource.supported_datasources',
  ['sources/gettext'],
  function(gettext) {
    return [
      {% for dst in datasource_types %}

      {label: '{{ dst.description }}', value: '{{ dst.datasource_type }}'},{% endfor %}

      {label: gettext('Unknown'), value: ''}
    ];
  }
);
