/////////////////////////////////////////////////////////////
//
// pgAdmin 4 - PostgreSQL Tools
//
// Copyright (C) 2013 - 2020, The pgAdmin Development Team
// This software is released under the PostgreSQL Licence
//
//////////////////////////////////////////////////////////////

define('pgadmin.node.dirobj', [
  'sources/gettext',
  'sources/url_for',
  'jquery',
  'underscore',
  'backbone',
  'sources/pgadmin',
  'pgadmin.browser',
  'pgadmin.dirobj.supported_dirsobjs',
], function(
  gettext, url_for, $, _,
  Backbone,
  pgAdmin,
  pgBrowser,
  supported_dirsobjs) {

  if (!pgBrowser.Nodes['dirobj']) {

    pgAdmin.Browser.Nodes['dirobj'] = pgAdmin.Browser.Node.extend({
      parent_type: 'bucket',
      type: 'dirobj',
      label: gettext('Object'),
      dialogHelp: url_for('help.static', {'filename': 'dirobj_dialog.html'}),
      hasSQL: false,
      hasDepends: false,
      hasStatistics: false,
      hasCollectiveStatistics: false,
      canDrop: false,
      canEdit: false,
      can_create_bucket: false,
      can_expand: true,
      Init: function() {

        /* Avoid multiple registration of same menus */
        if (this.initialized)
          return;

        this.initialized = true;
      },
      callbacks: {
        beforeopen: function() {
          return true;
        },
        added: function(item, data) {

          pgBrowser.dirobjInfo = pgBrowser.dirobjInfo || {};
          pgBrowser.dirobjInfo[data._id] = _.extend({}, data);

          // Call added method of node.js
          pgAdmin.Browser.Node.callbacks.added.apply(this, arguments);
          return true;
        },
      },

      model: pgAdmin.Browser.Node.Model.extend({
        idAttribute: 'oid',
        defaults: {
          name: '',
          do_type: undefined,
          size: undefined,
          mtime: undefined,
        },
        // Default values!
        initialize: function(attrs, args) {
          var isNew = (_.size(attrs) === 0);

          if (isNew) {
            this.set({'bid': args.node_info['bucket']._id});
          }
          pgAdmin.Browser.Node.Model.prototype.initialize.apply(this, arguments);
        },
        schema: [{
          id: 'name', label: gettext('Name'), type: 'text',
          mode: ['properties', 'edit', 'create'], editable: false,
          group: null,
        },{
          id: 'do_type', label: gettext('Type'), type: 'options',
          mode: ['properties'], select2: {allowClear: false},
          'options': supported_dirsobjs, editable: false,
          group: null,
        },{
          id: 'size', label: gettext('Size'), type: 'int',
          mode: ['properties'], editable: false,
          group: null,
        },{
          id: 'mtime', label: gettext('Modification Time'),
          editable: false, type: 'datetime', cell: 'datetime',
          mode: ['properties'],
          group: null,
        }],
      }),
    });
  }

  return pgBrowser.Nodes['dirobj'];
});
