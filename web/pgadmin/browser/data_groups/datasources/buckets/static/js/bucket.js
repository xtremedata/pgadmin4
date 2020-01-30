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
  'pgadmin.alertifyjs', 'pgadmin.backform', 'pgadmin.browser.collection',
], function(gettext, url_for, $, _, pgadminUtils, pgAdmin, pgBrowser, Alertify, Backform) {

  if (!pgBrowser.Nodes['coll-bucket']) {
    pgBrowser.Nodes['coll-bucket'] =
      pgBrowser.Collection.extend({
        node: 'bucket',
        label: gettext('Buckets'),
        type: 'coll-bucket',
        columns: ['name', 'datowner', 'comments'],
        hasStatistics: false,
        canDrop: false,
        canDropCascade: false,
      });
  }

  if (!pgBrowser.Nodes['bucket']) {
    pgBrowser.Nodes['bucket'] = pgBrowser.Node.extend({
      parent_type: 'datasource',
      type: 'bucket',
      sqlAlterHelp: 'sql-alterbucket.html',
      sqlCreateHelp: 'sql-createbucket.html',
      dialogHelp: url_for('help.static', {'filename': 'bucket_dialog.html'}),
      hasSQL: false,
      hasDepends: false,
      hasStatistics: false,
      canDrop: function(node) {
        return node.canDrop;
      },
      label: gettext('Bucket'),
      node_image: function() {
        return 'icon-bucket';
      },
      Init: function() {
        /* Avoid mulitple registration of menus */
        if (this.initialized)
          return;

        this.initialized = true;
      },
      can_create_bucket: false,
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
        idAttribute: 'did',
        defaults: {
          name: undefined,
          owner: undefined,
          comment: undefined,
          encoding: 'UTF8',
        },

        // Default values!
        initialize: function(attrs, args) {
          var isNew = (_.size(attrs) === 0);

          if (isNew) {
            var userInfo = pgBrowser.datasourceInfo[args.node_info.datasource._id].user;
            this.set({'datowner': userInfo.name}, {silent: true});
          }
          pgBrowser.Node.Model.prototype.initialize.apply(this, arguments);
        },

        schema: [{
          id: 'name', label: gettext('Bucket'), cell: 'string',
          editable: false, type: 'text',
        },{
          id: 'datowner', label: gettext('Owner'),
          editable: false, type: 'text', node: 'role',
          control: Backform.NodeListByNameControl, select2: { allowClear: false },
        },{
          id: 'acl', label: gettext('Privileges'), type: 'text',
          group: gettext('Security'), mode: ['properties'], disabled: true,
        },{
          id: 'comments', label: gettext('Comment'),
          editable: false, type: 'multiline',
        },{
          id: 'encoding', label: gettext('Encoding'),
          editable: false, type: 'text', group: gettext('Definition'),
          disabled: function(m) { return !m.isNew(); }, url: 'get_encodings',
          control: 'node-ajax-options', cache_level: 'datasource',
        }],
        validate: function() {
          var name = this.get('name');
          if (_.isUndefined(name) || _.isNull(name) ||
            String(name).replace(/^\s+|\s+$/g, '') == '') {
            var msg = gettext('Name cannot be empty.');
            this.errorModel.set('name', msg);
            return msg;
          } else {
            this.errorModel.unset('name');
          }
          return null;
        },
      }),
    });

    pgBrowser.SecurityGroupSchema = {
      id: 'security', label: gettext('Security'), type: 'group',
      // Show/Hide security group for nodes under the catalog
      visible: function(args) {
        if (args && 'node_info' in args) {
          // If node_info is not present in current object then it might in its
          // parent in case if we used sub node control
          var node_info = args.node_info || args.handler.node_info;
          return 'catalog' in node_info ? false : true;
        }
        return true;
      },
    };
  }

  return pgBrowser.Nodes['coll-bucket'];
});
