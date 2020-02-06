/////////////////////////////////////////////////////////////
//
// pgAdmin 4 - PostgreSQL Tools
//
// Copyright (C) 2013 - 2020, The pgAdmin Development Team
// This software is released under the PostgreSQL Licence
//
//////////////////////////////////////////////////////////////

define('pgadmin.node.bucket', [
  'sources/gettext', 'sources/url_for', 'jquery', 'underscore',
  'sources/utils', 'sources/pgadmin', 'pgadmin.browser.utils',
  'pgadmin.browser.collection',
], function(gettext, url_for, $, _, pgadminUtils, pgAdmin, pgBrowser) {

  if (!pgBrowser.Nodes['coll-bucket']) {
    pgBrowser.Nodes['coll-bucket'] =
      pgBrowser.Collection.extend({
        node: 'bucket',
        label: gettext('Buckets'),
        type: 'coll-bucket',
        columns: ['name', 'creationdate', 'dataowner'],
        hasStatistics: false,
        canDrop: false,
        canDropCascade: false,
      });
  }

  if (!pgBrowser.Nodes['bucket']) {
    pgBrowser.Nodes['bucket'] = pgBrowser.Node.extend({
      parent_type: 'datasource',
      type: 'bucket',
      label: gettext('Bucket'),
      dialogHelp: url_for('help.static', {'filename': 'bucket_dialog.html'}),
      hasSQL: false,
      hasDepends: false,
      hasStatistics: false,
      hasCollectiveStatistics: false,
      canDrop: false,
      canEdit: false,
      can_create_bucket: false,
      can_expand: true,
      node_image: function() {
        return 'icon-bucket';
      },
      Init: function() {
        /* Avoid mulitple registration of menus */
        if (this.initialized)
          return;

        this.initialized = true;
      },
      callbacks: {

        /* Connect the bucket (if not connected), before opening this node */
        beforeopen: function(item, data) {
          if(!data || data._type != 'bucket' || data.label == 'template0') {
            return false;
          }
          pgBrowser.tree.addIcon(item, {icon: data.icon});
          return true;
        },

        selected: function(item, data) {
          if(!data || data._type != 'bucket') {
            return false;
          }
          pgBrowser.tree.addIcon(item, {icon: data.icon});
          return pgBrowser.Node.callbacks.selected.apply(this, arguments);
        },
      },
      model: pgBrowser.Node.Model.extend({
        idAttribute: 'bid',
        defaults: {
          name: undefined,
          creationdate: undefined,
          dataowner: undefined,
        },

        // Default values!
        initialize: function() {
          pgBrowser.Node.Model.prototype.initialize.apply(this, arguments);
        },

        schema: [{
          id: 'name', label: gettext('Bucket'), cell: 'string',
          editable: false, type: 'text',
          mode: ['properties'], disabled: true,
        },{
          id: 'creationdate', label: gettext('Creation Date'),
          editable: false, type: 'datetime', cell: 'datetime',
          mode: ['properties'], disabled: true,
        },{
          id: 'dataowner', label: gettext('Owner'), cell: 'string',
          editable: false, type: 'text',
          mode: ['properties'], disabled: true,
        },{
          id: 'access', label: gettext('Privileges'), 
          editable: false, type: 'text',
          control: 'node-ajax-options', url: 'get_bucket_acl', cache_level: 'server',
          group: gettext('Security'), mode: ['properties'], disabled: true,
        }],
      }),
    });
  }

  return pgBrowser.Nodes['coll-bucket'];
});
