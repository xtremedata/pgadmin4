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
        hasStatistics: true,
        canDrop: true,
        canDropCascade: false,
        statsPrettifyFields: [gettext('Size'), gettext('Size of temporary files')],
      });
  }

  if (!pgBrowser.Nodes['bucket']) {
    pgBrowser.Nodes['bucket'] = pgBrowser.Node.extend({
      parent_type: 'datasource',
      type: 'bucket',
      sqlAlterHelp: 'sql-alterbucket.html',
      sqlCreateHelp: 'sql-createbucket.html',
      dialogHelp: url_for('help.static', {'filename': 'bucket_dialog.html'}),
      hasSQL: true,
      hasDepends: true,
      hasStatistics: true,
      statsPrettifyFields: [gettext('Size'), gettext('Size of temporary files')],
      canDrop: function(node) {
        return node.canDrop;
      },
      label: gettext('Bucket'),
      node_image: function() {
        return 'pg-icon-bucket';
      },
      Init: function() {
        /* Avoid mulitple registration of menus */
        if (this.initialized)
          return;

        this.initialized = true;

        pgBrowser.add_menus([{
          name: 'create_bucket_on_datasource', node: 'datasource', module: this,
          applies: ['object', 'context'], callback: 'show_obj_properties',
          category: 'create', priority: 4, label: gettext('Bucket...'),
          icon: 'wcTabIcon pg-icon-bucket', data: {action: 'create'},
          enable: 'can_create_bucket',
        },{
          name: 'create_bucket_on_coll', node: 'coll-bucket', module: this,
          applies: ['object', 'context'], callback: 'show_obj_properties',
          category: 'create', priority: 4, label: gettext('Bucket...'),
          icon: 'wcTabIcon pg-icon-bucket', data: {action: 'create'},
          enable: 'can_create_bucket',
        },{
          name: 'create_bucket', node: 'bucket', module: this,
          applies: ['object', 'context'], callback: 'show_obj_properties',
          category: 'create', priority: 4, label: gettext('Bucket...'),
          icon: 'wcTabIcon pg-icon-bucket', data: {action: 'create'},
          enable: 'can_create_bucket',
        },{
          name: 'connect_bucket', node: 'bucket', module: this,
          applies: ['object', 'context'], callback: 'connect_bucket',
          category: 'connect', priority: 4, label: gettext('Connect Bucket...'),
          icon: 'fa fa-link', enable : 'is_not_connected',
        },{
          name: 'disconnect_bucket', node: 'bucket', module: this,
          applies: ['object', 'context'], callback: 'disconnect_bucket',
          category: 'drop', priority: 5, label: gettext('Disconnect Bucket...'),
          icon: 'fa fa-chain-broken', enable : 'is_connected',
        }]);

        _.bindAll(this, 'connection_lost');
        pgBrowser.Events.on(
          'pgadmin:bucket:connection:lost', this.connection_lost
        );
      },
      can_create_bucket: function(node, item) {
        var treeData = this.getTreeNodeHierarchy(item),
          datasource = treeData['datasource'];

        return datasource.connected && datasource.user.can_create_db;
      },
      is_not_connected: function(node) {
        return (node && node.connected != true && node.allowConn == true);
      },
      is_connected: function(node) {
        return (node && node.connected == true && node.canDisconn == true);
      },
      is_conn_allow: function(node) {
        return (node && node.allowConn == true);
      },
      connection_lost: function(i, resp, datasource_connected) {
        if (pgBrowser.tree) {
          var t = pgBrowser.tree,
            d = i && t.itemData(i),
            self = this;

          while (d && d._type != 'bucket') {
            i = t.parent(i);
            d = i && t.itemData(i);
          }

          if (i && d) {
            if (!d.allowConn) return false;
            if (_.isUndefined(d.is_connecting) || !d.is_connecting) {
              d.is_connecting = true;

              var disconnect = function(_i, _d) {
                if (_d._id == this._id) {
                  d.is_connecting = false;
                  pgBrowser.Events.off(
                    'pgadmin:bucket:connect:cancelled', disconnect
                  );
                  _i = _i && t.parent(_i);
                  _d = _i && t.itemData(_i);
                  if (_i && _d) {
                    pgBrowser.Events.trigger(
                      'pgadmin:datasource:disconnect',
                      {item: _i, data: _d}, false
                    );
                  }
                }
              };

              pgBrowser.Events.on(
                'pgadmin:bucket:connect:cancelled', disconnect
              );
              if (datasource_connected) {
                connect(self, d, t, i, true);
                return;
              }
              Alertify.confirm(
                gettext('Connection lost'),
                gettext('Would you like to reconnect to the bucket?'),
                function() {
                  connect(self, d, t, i, true);
                },
                function() {
                  d.is_connecting = false;
                  t.unload(i);
                  t.setInode(i);
                  t.addIcon(i, {icon: 'icon-bucket-not-connected'});
                  pgBrowser.Events.trigger(
                    'pgadmin:bucket:connect:cancelled', i, d, self
                  );
                });
            }
          }
        }
      },
      callbacks: {
        /* Connect the bucket */
        connect_bucket: function(args){
          var input = args || {},
            obj = this,
            t = pgBrowser.tree,
            i = input.item || t.selected(),
            d = i && i.length == 1 ? t.itemData(i) : undefined;

          if (!d || d.label == 'template0')
            return false;

          connect_to_bucket(obj, d, t, i, true);
          return false;
        },
        /* Disconnect the bucket */
        disconnect_bucket: function(args) {
          var input = args || {},
            obj = this,
            t = pgBrowser.tree,
            i = input.item || t.selected(),
            d = i && i.length == 1 ? t.itemData(i) : undefined;

          if (!d)
            return false;

          Alertify.confirm(
            gettext('Disconnect the bucket'),
            pgadminUtils.sprintf(gettext('Are you sure you want to disconnect the bucket - %s?'), d.label),
            function() {
              var data = d;
              $.ajax({
                url: obj.generate_url(i, 'connect', d, true),
                type:'DELETE',
              })
                .done(function(res) {
                  if (res.success == 1) {
                    var prv_i = t.parent(i);
                    if(res.data.info_prefix) {
                      res.info = `${_.escape(res.data.info_prefix)} - ${res.info}`;
                    }
                    Alertify.success(res.info);
                    t.removeIcon(i);
                    data.connected = false;
                    data.icon = 'icon-bucket-not-connected';
                    t.addIcon(i, {icon: data.icon});
                    t.unload(i);
                    t.setInode(i);
                    setTimeout(function() {
                      t.select(prv_i);
                    }, 10);

                  } else {
                    try {
                      Alertify.error(res.errormsg);
                    } catch (e) {
                      console.warn(e.stack || e);
                    }
                    t.unload(i);
                  }
                })
                .fail(function(xhr, status, error) {
                  Alertify.pgRespErrorNotify(xhr, error);
                  t.unload(i);
                });
            },
            function() { return true; });

          return false;
        },

        /* Connect the bucket (if not connected), before opening this node */
        beforeopen: function(item, data) {
          if(!data || data._type != 'bucket' || data.label == 'template0') {
            return false;
          }

          pgBrowser.tree.addIcon(item, {icon: data.icon});
          if (!data.connected && data.allowConn) {
            connect_to_bucket(this, data, pgBrowser.tree, item, true);
            return false;
          }
          return true;
        },

        selected: function(item, data) {
          if(!data || data._type != 'bucket') {
            return false;
          }

          pgBrowser.tree.addIcon(item, {icon: data.icon});
          if (!data.connected && data.allowConn) {
            connect_to_bucket(this, data, pgBrowser.tree, item, false);
            return false;
          }

          return pgBrowser.Node.callbacks.selected.apply(this, arguments);
        },

        refresh: function(cmd, i) {
          var t = pgBrowser.tree,
            item = i || t.selected(),
            d = t.itemData(item);

          if (!d.allowConn) return;
          pgBrowser.Node.callbacks.refresh.apply(this, arguments);
        },
      },
      model: pgBrowser.Node.Model.extend({
        idAttribute: 'did',
        defaults: {
          name: undefined,
          owner: undefined,
          comment: undefined,
          encoding: 'UTF8',
          template: undefined,
          tablespace: undefined,
          collation: undefined,
          char_type: undefined,
          datconnlimit: -1,
          datallowconn: undefined,
          variables: [],
          privileges: [],
          securities: [],
          datacl: [],
          deftblacl: [],
          deffuncacl: [],
          defseqacl: [],
          is_template: false,
          deftypeacl: [],
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
          id: 'did', label: gettext('OID'), cell: 'string', mode: ['properties'],
          editable: false, type: 'text',
        },{
          id: 'datowner', label: gettext('Owner'),
          editable: false, type: 'text', node: 'role',
          control: Backform.NodeListByNameControl, select2: { allowClear: false },
        },{
          id: 'acl', label: gettext('Privileges'), type: 'text',
          group: gettext('Security'), mode: ['properties'], disabled: true,
        },{
          id: 'tblacl', label: gettext('Default TABLE privileges'), type: 'text',
          group: gettext('Security'), mode: ['properties'], disabled: true,
        },{
          id: 'seqacl', label: gettext('Default SEQUENCE privileges'), type: 'text',
          group: gettext('Security'), mode: ['properties'], disabled: true,
        },{
          id: 'funcacl', label: gettext('Default FUNCTION privileges'), type: 'text',
          group: gettext('Security'), mode: ['properties'], disabled: true,
        },{
          id: 'typeacl', label: gettext('Default TYPE privileges'), type: 'text',
          group: gettext('Security'), mode: ['properties'], disabled: true, min_version: 90200,
        },{
          id: 'comments', label: gettext('Comment'),
          editable: false, type: 'multiline',
        },{
          id: 'encoding', label: gettext('Encoding'),
          editable: false, type: 'text', group: gettext('Definition'),
          disabled: function(m) { return !m.isNew(); }, url: 'get_encodings',
          control: 'node-ajax-options', cache_level: 'datasource',
        },{
          id: 'template', label: gettext('Template'),
          editable: false, type: 'text', group: gettext('Definition'),
          disabled: function(m) { return !m.isNew(); },
          control: 'node-list-by-name', url: 'get_buckets', cache_level: 'datasource',
          select2: { allowClear: false }, mode: ['create'],
          transform: function(data, cell) {
            var res = [],
              control = cell || this,
              label = control.model.get('name');

            if (!control.model.isNew()) {
              res.push({label: label, value: label});
            }
            else {
              if (data && _.isArray(data)) {
                _.each(data, function(d) {
                  res.push({label: d, value: d,
                    image: 'pg-icon-bucket'});
                });
              }
            }
            return res;
          },
        },{
          id: 'spcname', label: gettext('Tablespace'),
          editable: false, type: 'text', group: gettext('Definition'),
          control: 'node-list-by-name', node: 'tablespace',
          select2: { allowClear: false },
          filter: function(m) {
            if (m.label == 'pg_global') return false;
            else return true;
          },
        },{
          id: 'datcollate', label: gettext('Collation'),
          editable: false, type: 'text', group: gettext('Definition'),
          disabled: function(m) { return !m.isNew(); }, url: 'get_ctypes',
          control: 'node-ajax-options', cache_level: 'datasource',
        },{
          id: 'datctype', label: gettext('Character type'),
          editable: false, type: 'text', group: gettext('Definition'),
          disabled: function(m) { return !m.isNew(); }, url: 'get_ctypes',
          control: 'node-ajax-options', cache_level: 'datasource',
        },{
          id: 'datconnlimit', label: gettext('Connection limit'),
          editable: false, type: 'int', group: gettext('Definition'), min: -1,
        },{
          id: 'is_template', label: gettext('Template?'),
          editable: false, type: 'switch', group: gettext('Definition'),
          disabled: true,  mode: ['properties', 'edit'],
        },{
          id: 'datallowconn', label: gettext('Allow connections?'),
          editable: false, type: 'switch', group: gettext('Definition'),
          mode: ['properties'], disabled: true,
        },{
          id: 'datacl', label: gettext('Privileges'), type: 'collection',
          model: pgBrowser.Node.PrivilegeRoleModel.extend({
            privileges: ['C', 'T', 'c'],
          }), uniqueCol : ['grantee', 'grantor'], editable: false,
          group: gettext('Security'), mode: ['edit', 'create'],
          canAdd: true, canDelete: true, control: 'unique-col-collection',
        },{
          id: 'variables', label: '', type: 'collection',
          model: pgBrowser.Node.VariableModel.extend({keys:['name', 'role']}), editable: false,
          group: gettext('Parameters'), mode: ['edit', 'create'],
          canAdd: true, canEdit: false, canDelete: true, hasRole: true,
          control: Backform.VariableCollectionControl, node: 'role',
        },{
          id: 'seclabels', label: gettext('Security labels'),
          model: pgBrowser.SecLabelModel,
          editable: false, type: 'collection', canEdit: false,
          group: gettext('Security'), canDelete: true,
          mode: ['edit', 'create'], canAdd: true,
          control: 'unique-col-collection', uniqueCol : ['provider'],
          min_version: 90200,
        },{
          type: 'nested', control: 'tab', group: gettext('Default Privileges'),
          mode: ['edit'],
          schema:[{
            id: 'deftblacl', model: pgBrowser.Node.PrivilegeRoleModel.extend(
              {privileges: ['a', 'r', 'w', 'd', 'D', 'x', 't']}), label: '',
            editable: false, type: 'collection', group: gettext('Tables'),
            mode: ['edit', 'create'], control: 'unique-col-collection',
            canAdd: true, canDelete: true, uniqueCol : ['grantee', 'grantor'],
          },{
            id: 'defseqacl', model: pgBrowser.Node.PrivilegeRoleModel.extend(
              {privileges: ['r', 'w', 'U']}), label: '',
            editable: false, type: 'collection', group: gettext('Sequences'),
            mode: ['edit', 'create'], control: 'unique-col-collection',
            canAdd: true, canDelete: true, uniqueCol : ['grantee', 'grantor'],
          },{
            id: 'deffuncacl', model: pgBrowser.Node.PrivilegeRoleModel.extend(
              {privileges: ['X']}), label: '',
            editable: false, type: 'collection', group: gettext('Functions'),
            mode: ['edit', 'create'], control: 'unique-col-collection',
            canAdd: true, canDelete: true, uniqueCol : ['grantee', 'grantor'],
          },{
            id: 'deftypeacl', model: pgBrowser.Node.PrivilegeRoleModel.extend(
              {privileges: ['U']}),  label: '',
            editable: false, type: 'collection', group: 'deftypesacl_group',
            mode: ['edit', 'create'], control: 'unique-col-collection',
            canAdd: true, canDelete: true, uniqueCol : ['grantee', 'grantor'],
            min_version: 90200,
          },{
            id: 'deftypesacl_group', type: 'group', label: gettext('Types'),
            mode: ['edit', 'create'], min_version: 90200,
          },
          ],
        },
        ],
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

    var connect_to_bucket = function(obj, data, tree, item) {
        connect(obj, data, tree, item);
      },
      connect = function (obj, data, tree, item, _wasConnected) {
        var wasConnected = _wasConnected || data.connected,
          onFailure = function(
            xhr, status, error, _model, _data, _tree, _item, _status
          ) {
            if (!_status) {
              tree.setInode(_item);
              tree.addIcon(_item, {icon: 'icon-bucket-not-connected'});
            }

            Alertify.pgNotifier('error', xhr, error, function(msg) {
              setTimeout(function() {
                if (msg == 'CRYPTKEY_SET') {
                  connect_to_bucket(_model, _data, _tree, _item, _wasConnected);
                } else {
                  Alertify.dlgServerPass(
                    gettext('Connect to bucket'),
                    msg, _model, _data, _tree, _item, _status,
                    onSuccess, onFailure, onCancel
                  ).resizeTo();
                }
              }, 100);
            });
          },
          onSuccess = function(
            res, model, data, tree, item, connected
          ) {
            data.is_connecting = false;
            if (!connected) {
              tree.deselect(item);
              tree.setInode(item);
            }

            if (res && res.data) {
              if(typeof res.data.connected == 'boolean') {
                data.connected = res.data.connected;
              }
              if (typeof res.data.icon == 'string') {
                tree.removeIcon(item);
                data.icon = res.data.icon;
                tree.addIcon(item, {icon: data.icon});
              }
              if(res.data.info_prefix) {
                res.info = `${_.escape(res.data.info_prefix)} - ${res.info}`;
              }

              Alertify.success(res.info);
              obj.trigger('connected', obj, item, data);
              pgBrowser.Events.trigger(
                'pgadmin:bucket:connected', item, data
              );

              if (!connected) {
                setTimeout(function() {
                  tree.select(item);
                  tree.open(item);
                }, 10);
              }
            }
          },
          onCancel = function(_tree, _item, _data) {
            _data.is_connecting = false;
            var datasource = _tree.parent(_item);
            _tree.unload(_item);
            _tree.setInode(_item);
            _tree.removeIcon(_item);
            _tree.addIcon(_item, {icon: 'icon-bucket-not-connected'});
            obj.trigger('connect:cancelled', obj, _item, _data);
            pgBrowser.Events.trigger(
              'pgadmin:bucket:connect:cancelled', _item, _data, obj
            );
            _tree.select(datasource);
          };

        $.post(
          obj.generate_url(item, 'connect', data, true)
        ).done(function(res) {
          if (res.success == 1) {
            return onSuccess(res, obj, data, tree, item, wasConnected);
          }
        }).fail(function(xhr, status, error) {
          return onFailure(
            xhr, status, error, obj, data, tree, item, wasConnected
          );
        });
      };
  }

  return pgBrowser.Nodes['coll-bucket'];
});
