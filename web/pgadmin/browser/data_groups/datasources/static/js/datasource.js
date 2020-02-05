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
  'sources/pgadmin',
  'pgadmin.alertifyjs',
  'pgadmin.browser',
  'pgadmin.user_management.current_user',
  'pgadmin.datasource.supported_datasources',
], function(
  gettext, url_for, $, _, Backbone, pgAdmin,
  Alertify, pgBrowser,
  current_user, supported_datasources,
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
      },
    });

    pgAdmin.Browser.Nodes['datasource'] = pgAdmin.Browser.Node.extend({
      parent_type: 'data_group',
      type: 'datasource',
      dialogHelp: url_for('help.static', {'filename': 'datasource_dialog.html'}),
      label: gettext('Data Source'),
      canDrop: true,
      dropAsRemove: true,
      dropPriority: 5,
      hasStatistics: false,
      hasCollectiveStatistics: false,
      can_expand: true,
      Init: function() {

        /* Avoid multiple registration of same menus */
        if (this.initialized)
          return;

        this.initialized = true;

        pgBrowser.add_menus([{
          name: 'create_datasource_on_dg', node: 'data_group', module: this,
          applies: ['object', 'context'], callback: 'show_obj_properties',
          category: 'create', priority: 1, label: gettext('Data Source...'),
          data: {action: 'create'}, icon: 'wcTabIcon icon-datasource',
        },{
          name: 'create_datasource', node: 'datasource', module: this,
          applies: ['object', 'context'], callback: 'show_obj_properties',
          category: 'create', priority: 2, label: gettext('Data Source...'),
          data: {action: 'create'}, icon: 'wcTabIcon icon-datasource',
        },{
          name: 'clear_saved_authentication', node: 'datasource', module: this,
          applies: ['object', 'context'], callback: 'clear_saved_authentication',
          label: gettext('Clear Saved Authentication'), icon: 'fa fa-eraser',
          priority: 3,
          enable: function(node) {
            if (node && node._type === 'datasource' &&
              node.is_auth_saved) {
              return true;
            }
            return false;
          },
        }]);
      },
      callbacks: {
        beforeopen: function() {
          return true;
        },
        added: function(item, data) {

          pgBrowser.datasourceInfo = pgBrowser.datasourceInfo || {};
          pgBrowser.datasourceInfo[data._id] = _.extend({}, data);

          // Call added method of node.js
          pgAdmin.Browser.Node.callbacks.added.apply(this, arguments);
          return true;
        },

        /* Cleat saved data source authentication */
        clear_saved_authentication: function(args){
          var input = args || {},
            obj = this,
            t = pgBrowser.tree,
            i = input.item || t.selected(),
            d = i && i.length == 1 ? t.itemData(i) : undefined;

          if (!d)
            return false;

          Alertify.confirm(
            gettext('Clear saved password'),
            gettext('Are you sure you want to clear the saved password for server %s?', d.label),
            function() {
              $.ajax({
                url: obj.generate_url(i, 'clear_saved_authentication', d, true),
                method:'PUT',
              })
                .done(function(res) {
                  if (res.success == 1) {
                    Alertify.success(res.info);
                    t.itemData(i).is_auth_saved=res.data.is_auth_saved;
                  }
                  else {
                    Alertify.error(res.info);
                  }
                })
                .fail(function(xhr, status, error) {
                  Alertify.pgRespErrorNotify(xhr, error);
                });
            },
            function() { return true; }
          );

          return false;
        },
      },

      model: pgAdmin.Browser.Node.Model.extend({
        defaults: {
          gid: undefined,
          id: undefined,
          name: '',
          datasource_type: '',
          pfx: undefined,
          key_name: undefined,
          key_secret: undefined,
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
          group: null,
        },{
          id: 'name', label: gettext('Name'), type: 'text',
          mode: ['properties', 'edit', 'create'],
          group: null,
        },{
          id: 'gid', label: gettext('Data group'), type: 'int',
          control: 'node-list-by-id', node: 'data_group',
          mode: ['create', 'edit'], select2: {allowClear: false},
          group: null,
        },{
          id: 'datasource_type', label: gettext('Data source type'), type: 'options',
          mode: ['properties', 'edit', 'create'], select2: {allowClear: false},
          'options': supported_datasources,
          group: null,
        },{
          id: 'bgcolor', label: gettext('Background'), type: 'color',
          mode: ['edit', 'create'], disabled: 'isfgColorSet',
          deps: ['fgcolor'],
          group: null,
        },{
          id: 'fgcolor', label: gettext('Foreground'), type: 'color',
          mode: ['edit', 'create'], disabled: 'isConnected',
          group: null,
        },{
          id: 'pfx', label: gettext('Object Prefix'), type: 'text',
          mode: ['properties', 'edit', 'create'],
          visible: 'isAWS', group: gettext('Filter'),
        },{
          id: 'key_name', label: gettext('AWS key name'), type: 'text',
          mode: ['properties', 'edit', 'create'],
          visible: 'isAWS', group: gettext('Auhentication'),
        },{
          id: 'key_secret', label: gettext('AWS key secret'), type: 'password',
          control: 'input',
          mode: ['properties', 'edit', 'create'],
          visible: 'isAWS',
          group: gettext('Auhentication'),
        },{
          id: 'save_secret', controlLabel: gettext('Save secret?'), type: 'checkbox',
          mode: ['create'],
          group: gettext('Auhentication'),
          visible: function(model) {
            return model.get('datasource_type') == 'S3' && model.isNew();
          },
          disabled: function() {
            if (!current_user.allow_save_password)
              return true;
            return false;
          },
        }],

        validate: function() {
          return true;
        },

        isConnected: function() {
          return true;
        },

        isAws: function(model) {
          var ds_type = model.get('datasource_type');
          return ds_type == 'S3';
        },

        isfgColorSet: function() {
          return true;
        },

      }),
    });
  }

  return pgBrowser.Nodes['datasource'];
});
