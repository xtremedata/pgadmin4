/////////////////////////////////////////////////////////////
//
// pgAdmin 4 - PostgreSQL Tools
//
// Copyright (C) 2013 - 2020, The pgAdmin Development Team
// This software is released under the PostgreSQL Licence
//
//////////////////////////////////////////////////////////////

define('pgadmin.node.dirobj', [
  'sources/gettext', 'sources/url_for', 'jquery', 'underscore', 'backbone',
  'sources/pgadmin',
  'pgadmin.alertifyjs',
  'pgadmin.browser',
  'pgadmin.dirobj.supported_dirsobjs',
], function(
  gettext, url_for, $, _, Backbone, pgAdmin,
  Alertify, pgBrowser,
  supported_dirsobjs,
) {

  if (!pgBrowser.Nodes['dirobj']) {

    pgAdmin.Browser.Nodes['dirobj'] = pgAdmin.Browser.Node.extend({
      parent_type: 'bucket',
      type: 'dirobj',
      dialogHelp: url_for('help.static', {'filename': 'dirobj_dialog.html'}),
      label: gettext('Object'),
      canDrop: false,
      dropAsRemove: false,
      dropPriority: 5,
      hasStatistics: false,
      hasCollectiveStatistics: false,
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
        defaults: {
          name: '',
          do_type: undefined,
        },
        // Default values!
        initialize: function(attrs, args) {
          var isNew = (_.size(attrs) === 0);

          if (isNew) {
            this.set({'gid': args.node_info['data_group']._id});
          }
          pgAdmin.Browser.Node.Model.prototype.initialize.apply(this, arguments);
        },
        schema: [{
          id: 'name', label: gettext('Name'), type: 'text',
          mode: ['properties', 'edit', 'create'],
          group: null,
        },{
          id: 'do_type', label: gettext('Type'), type: 'options',
          mode: ['properties'], select2: {allowClear: false},
          'options': supported_dirsobjs,
          group: null,
        }],

        validate: function() {
          return true;
        },
      }),
    });
  }

  return pgBrowser.Nodes['dirobj'];
});
