/////////////////////////////////////////////////////////////
//
// pgAdmin 4 - PostgreSQL Tools
//
// Copyright (C) 2013 - 2020, The pgAdmin Development Team
// This software is released under the PostgreSQL Licence
//
//////////////////////////////////////////////////////////////

define('pgadmin.node.folder', [
  'sources/gettext', 'sources/url_for', 'jquery', 'underscore', 'backbone',
  'sources/pgadmin',
  'pgadmin.alertifyjs',
  'pgadmin.browser',
  'pgadmin.user_management.current_user',
], function(
  gettext, url_for, $, _, Backbone, pgAdmin,
  Alertify, pgBrowser,
  current_user,
) {

  if (!pgBrowser.Nodes['folder']) {

    pgAdmin.Browser.Nodes['folder'] = pgAdmin.Browser.Node.extend({
      parent_type: 'bucket',
      type: 'folder',
      dialogHelp: url_for('help.static', {'filename': 'folder_dialog.html'}),
      label: gettext('Folder'),
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

          pgBrowser.folderInfo = pgBrowser.folderInfo || {};
          pgBrowser.folderInfo[data._id] = _.extend({}, data);

          // Call added method of node.js
          pgAdmin.Browser.Node.callbacks.added.apply(this, arguments);
          return true;
        },
      },

      model: pgAdmin.Browser.Node.Model.extend({
        defaults: {
          name: '',
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
        }],

        validate: function() {
          return true;
        },
      }),
    });
  }

  return pgBrowser.Nodes['folder'];
});
