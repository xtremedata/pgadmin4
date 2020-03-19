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
  'pgadmin.backform',
  'pgadmin.browser',
  'pgadmin.user_management.current_user',
  'pgadmin.datasource.supported_datasources',
  //'pgadmin.dirobj.supported_dirsobjs',
], function(
  gettext, url_for, $, _, Backbone, pgAdmin,
  Alertify, Backform, pgBrowser,
  current_user,
  supported_datasources,
  // supported_dirsobjs,
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
      hasProfiling: false,
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
          name: 'change_authentication', node: 'datasource', module: this,
          applies: ['object', 'context'], callback: 'change_authentication',
          label: gettext('Change authentication...'), icon: 'fa fa-lock',
          priority: 3,
        },{
          name: 'clear_saved_authentication', node: 'datasource', module: this,
          applies: ['object', 'context'], callback: 'clear_saved_authentication',
          label: gettext('Clear Saved Authentication'), icon: 'fa fa-eraser',
          priority: 4,
          enable: function(node) {
            return node && node._type === 'datasource' && node.has_secret;
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

        /* Change data source authentication */
        change_authentication: function(args) {
          var input = args || {},
            obj = this,
            t = pgBrowser.tree,
            i = input.item || t.selected(),
            d = i && i.length == 1 ? t.itemData(i) : undefined,
            url = obj.generate_url(i, 'change_authentication', d, true);

          if (!d)
            return false;

          if(!Alertify.changeDatasourceAuthentication) {
            var newAuthenticationModel = Backbone.Model.extend({
                defaults: {
                  ds_type: undefined,
                  key_name: undefined,
                  key_secret: undefined,
                  new_key_name: undefined,
                  new_key_secret: undefined,
                  confirm_new_key_secret: undefined,
                },
                validate: function() {
                  return null;
                },
              }),
              authChangeFields = [{
                name: 'ds_type', label: gettext('Datasource Type'),
                type: 'text', disabled: true, control: 'input',
              },{
                name: 'new_key_name', label: gettext('Key Name'),
                type: 'text', disabled: false, control: 'input',
                required: true,
              },{
                name: 'new_key_secret', label: gettext('Key Secret'),
                type: 'password', disabled: false, control: 'input',
                required: true,
              }];


            Alertify.dialog('changeDatasourceAuthentication' ,function factory() {
              return {
                main: function(params) {
                  var title = gettext('Change Authentication');
                  this.set('title', title);
                  this.ds_type = params.datasource_type;
                  this.key_name = params.key_name;
                },
                setup:function() {
                  return {
                    buttons: [{
                      text: gettext('Cancel'), key: 27,
                      className: 'btn btn-secondary fa fa-times pg-alertify-button', attrs: {name: 'cancel'},
                    },{
                      text: gettext('OK'), key: 13, className: 'btn btn-primary fa fa-check pg-alertify-button',
                      attrs: {name:'submit'},
                    }],
                    // Set options for dialog
                    options: {
                      padding : !1,
                      overflow: !1,
                      modal:false,
                      resizable: true,
                      maximizable: true,
                      pinnable: false,
                      closableByDimmer: false,
                    },
                  };
                },
                hooks: {
                  // triggered when the dialog is closed
                  onclose: function() {
                    if (this.view) {
                      this.view.remove({data: true, internal: true, silent: true});
                    }
                  },
                },
                prepare: function() {
                  var self = this;
                  // Disable Ok button until user provides input
                  this.__internal.buttons[1].element.disabled = true;

                  var $container = $('<div class=\'change_authentication\'></div>'),
                    newAuthModel = new newAuthenticationModel(
                      { 'ds_type': self.ds_type, 
                        'new_key_name': self.key_name,
                      }
                    ),
                    view = this.view = new Backform.Form({
                      el: $container,
                      model: newAuthModel,
                      fields: authChangeFields,
                    });

                  view.render();

                  this.elements.content.appendChild($container.get(0));

                  // Listen to model & if filename is provided then enable Backup button
                  this.view.model.on('change', function() {
                    var new_key_name = this.get('new_key_name'),
                      new_key_secret = this.get('new_key_secret');

                    // Only check password field if pgpass file is not available
                    self.__internal.buttons[1].element.disabled = _.isUndefined(new_key_name)
                      || _.isNull(new_key_name)
                      || new_key_name == ''
                      || _.isUndefined(new_key_secret)
                      || _.isNull(new_key_secret)
                      || new_key_secret == '';
                  });
                },
                // Callback functions when click on the buttons of the Alertify dialogs
                callback: function(e) {
                  if (e.button.element.name == 'submit') {
                    var self = this,
                      model = this.view.model,
                      args = null;
                      
                    // No need for fancy checking in this case
                    //model.set('key_name', model.get('new_key_name'));
                    //model.set('key_secret', model.get('new_key_secret'));
                    model.set('confirm_new_key_secret', model.get('new_key_secret'));
                    args =  this.view.model.toJSON();

                    e.cancel = true;

                    $.ajax({
                      url: url,
                      method:'POST',
                      data:{'data': JSON.stringify(args)},
                    }).done(function(res) {
                      if (res.success) {
                        Alertify.success(res.info);
                        self.close();
                      } else {
                        Alertify.error(res.errormsg);
                      }
                    }).fail(function(xhr, status, error) {
                      Alertify.pgRespErrorNotify(xhr, error);
                    });
                  }
                },
              };
            });
          }

          Alertify.changeDatasourceAuthentication(d).resizeTo('40%','52%');
        },

        /* Clear saved data source authentication */
        clear_saved_authentication: function(args) {
          var input = args || {},
            obj = this,
            t = pgBrowser.tree,
            i = input.item || t.selected(),
            d = i && i.length == 1 ? t.itemData(i) : undefined;

          if (!d)
            return false;

          Alertify.confirm(
            gettext('Clear saved authentication'),
            gettext('Are you sure you want to clear the saved authentication for %s?', d.label),
            function() {
              $.ajax({
                url: obj.generate_url(i, 'clear_saved_authentication', d, true),
                method:'PUT',
              })
                .done(function(res) {
                  if (res.success == 1) {
                    Alertify.success(res.info);
                    t.itemData(i).has_secret=res.data.has_secret;
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
        idAttribute: 'sid',
        defaults: {
          gid: undefined,
          id: undefined,
          name: '',
          username: current_user.name,
          datasource_type: '',
          pattern: undefined,
          pfx: undefined,
          obj_type: undefined,
          key_name: undefined,
          key_secret: undefined,
          has_secret: undefined,
          save_secret: false,
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
          mode: ['create', 'edit'], select2: {allowClear: false, first_empty: false},
          group: null,
        },{
          id: 'datasource_type', label: gettext('Data source type'), type: 'options',
          mode: ['properties', 'edit', 'create'], select2: {allowClear: false},
          'options': supported_datasources,
          group: null,
          disabled: 'isNotNew',
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
          id: 'pattern', label: gettext('Bucket Pattern'), type: 'text',
          mode: ['properties', 'edit', 'create'],
          group: gettext('Filter'),
          visible: 'isAWS',
        },{
          id: 'pfx', label: gettext('Object Prefix'), type: 'text',
          mode: ['properties', 'edit', 'create'],
          group: gettext('Filter'),
          visible: 'isAWS',
        },{
          id: 'obj_type', label: gettext('Object Type'),
          mode: ['properties', 'edit', 'create'],
          control: 'node-ajax-options',
          url: 'supported_objtypes',
          url_with_id: true,
          node: 'datasource',
          group: gettext('Filter'),
          visible: 'isAWS',
          select2: {allowClear: true, first_empty: true},
        },{
          id: 'key_name', 
          label: gettext('AWS key name'), 
          type: 'text',
          mode: ['properties', 'edit', 'create'],
          deps: ['datasource_type'],
          group: gettext('Auhentication'),
          visible: 'isAWS', 
          disabled: 'isNotNew',
        },{
          id: 'key_secret', 
          label: gettext('AWS key secret'), 
          type: 'password',
          control: 'input',
          mode: ['create'],
          deps: ['datasource_type'],
          group: gettext('Auhentication'),
          visible: 'isAWSNew',
        },{
          id: 'save_secret', 
          controlLabel: gettext('Save secret?'), 
          type: 'checkbox',
          mode: ['create'],
          deps: ['datasource_type'],
          group: gettext('Auhentication'),
          visible: 'isAWSNew',
          disabled: function() {
            return !current_user.allow_save_password;
          },
        }],

        validate: function() {
          return true;
        },

        isConnected: function() {
          return true;
        },

        isAWS: function(model) {
          var ds_type = model.get('datasource_type');
          return ds_type == 'S3';
        },

        isAWSNew: function(model) {
          return model.isAWS.apply(this, arguments) && model.isNew();
        },

        isNotNew: function(model) {
          return !model.isNew();
        },

        isfgColorSet: function() {
          return true;
        },
      }),
    });
  }

  return pgBrowser.Nodes['datasource'];
});
