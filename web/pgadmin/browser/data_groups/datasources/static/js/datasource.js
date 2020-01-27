/////////////////////////////////////////////////////////////
//
// pgAdmin 4 - PostgreSQL Tools
//
// Copyright (C) 2013 - 2020, The pgAdmin Development Team
// This software is released under the PostgreSQL Licence
//
//////////////////////////////////////////////////////////////

define('pgadmin.node.datasource', [
  'sources/gettext', 'sources/url_for', 'jquery', 'underscore', 'backbone',
  'sources/pgadmin', 'pgadmin.browser',
  'pgadmin.datasource.supported_datasources', 'pgadmin.user_management.current_user',
  'pgadmin.alertifyjs', 'pgadmin.backform',
], function(
  gettext, url_for, $, _, Backbone, pgAdmin, pgBrowser,
  supported_datasources, current_user, Alertify, Backform
) {

  if (!pgBrowser.Nodes['datasource']) {

    pgBrowser.SecLabelModel = pgBrowser.Node.Model.extend({
      defaults: {
        provider: undefined,
        label: undefined,
      },
      schema: [{
        id: 'provider', label: gettext('Provider'),
        type: 'text', editable: true,
        cellHeaderClasses:'width_percent_50',
      },{
        id: 'label', label: gettext('Security label'),
        type: 'text', editable: true,
        cellHeaderClasses:'override_label_class_font_size',
      }],
      validate: function() {
        this.errorModel.clear();

        if (_.isUndefined(this.get('label')) ||
          _.isNull(this.get('label')) ||
            String(this.get('label')).replace(/^\s+|\s+$/g, '') == '') {
          var errmsg = gettext('Security label must be specified.');
          this.errorModel.set('label', errmsg);
          return errmsg;
        }

        return null;
      }
    });

    pgAdmin.Browser.Nodes['datasource'] = pgAdmin.Browser.Node.extend({
      parent_type: 'data_group',
      type: 'datasource',
      dialogHelp: url_for('help.static', {'filename': 'datasource_dialog.html'}),
      label: gettext('DataSource'),
      canDrop: true,
      dropAsRemove: true,
      dropPriority: 5,
      hasStatistics: true,
      hasCollectiveStatistics: true,
      can_expand: true,
      Init: function() {

        /* Avoid multiple registration of same menus */
        if (this.initialized)
          return;

        this.initialized = true;

        pgBrowser.add_menus([{
          name: 'create_datasource_on_dg', node: 'data_group', module: this,
          applies: ['object', 'context'], callback: 'show_obj_properties',
          category: 'create', priority: 1, label: gettext('DataSource...'),
          data: {action: 'create'}, icon: 'wcTabIcon icon-datasource',
        },{
          name: 'create_datasource', node: 'datasource', module: this,
          applies: ['object', 'context'], callback: 'show_obj_properties',
          category: 'create', priority: 3, label: gettext('DataSource...'),
          data: {action: 'create'}, icon: 'wcTabIcon icon-datasource',
        }]);
      },
      callbacks: {
        added: function(item, data) {

          pgBrowser.datasourceInfo = pgBrowser.datasourceInfo || {};
          pgBrowser.datasourceInfo[data._id] = _.extend({}, data);

          // Call added method of node.js
          pgAdmin.Browser.Node.callbacks.added.apply(this, arguments);
          return true;
        }
      },
      model: pgAdmin.Browser.Node.Model.extend({
        defaults: {
          gid: undefined,
          id: undefined,
          name: '',
          datasource_type: '',
          key_name: undefined,
          key_secret: undefined
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
          id: 'id', label: gettext('ID'), type: 'int', mode: ['properties'],
        },{
          id: 'name', label: gettext('Name'), type: 'text',
          mode: ['properties', 'edit', 'create'],
        },{
          id: 'gid', label: gettext('Data group'), type: 'int',
          control: 'node-list-by-id', node: 'data_group',
          mode: ['create', 'edit'], select2: {allowClear: false},
        },{
          datasource_type: 'datasource_type', label: gettext('Data source type'), type: 'text',
          mode: ['properties', 'edit', 'create'],
        },{
          id: 'bgcolor', label: gettext('Background'), type: 'color',
          group: null, mode: ['edit', 'create'], disabled: 'isfgColorSet',
          deps: ['fgcolor'],
        },{
          id: 'fgcolor', label: gettext('Foreground'), type: 'color',
          group: null, mode: ['edit', 'create'], disabled: 'isConnected',
        }],
        validate: function() {
          return true;
        },
        isfgColorSet: function(model) {
          var bgcolor = model.get('bgcolor'),
            fgcolor = model.get('fgcolor');

          if(model.get('connected')) {
            return true;
          }
          // If fgcolor is set and bgcolor is not set then force bgcolor
          // to set as white
          if(_.isUndefined(bgcolor) || _.isNull(bgcolor) || !bgcolor) {
            if(fgcolor) {
              model.set('bgcolor', '#ffffff');
            }
          }

          return false;
        }
      }),
    });
  }

  return pgBrowser.Nodes['datasource'];
});
