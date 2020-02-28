/////////////////////////////////////////////////////////////
//
// pgAdmin 4 - PostgreSQL Tools
//
// Copyright (C) 2013 - 2020, The pgAdmin Development Team
// This software is released under the PostgreSQL Licence
//
//////////////////////////////////////////////////////////////

define([
  'sources/gettext', 'sources/url_for', 'jquery', 'underscore', 'pgadmin.alertifyjs',
  'sources/pgadmin', 'pgadmin.browser', 'backbone', 'backgrid', 'backform',
  'sources/utils',
  'sources/nodes/supported_database_node',
  'pgadmin.backform', 'pgadmin.backgrid', 'pgadmin.browser.node.ui',
], function(
  gettext, url_for, $, _, Alertify, pgAdmin, pgBrowser, Backbone, Backgrid,
  Backform, commonUtils, supportedNodes
) {

  pgAdmin = pgAdmin || window.pgAdmin || {};

  var pgTools = pgAdmin.Tools = pgAdmin.Tools || {};

  // Return back, this has been called more than once
  if (pgAdmin.Tools.import_utility)
    return pgAdmin.Tools.import_utility;


  // Import Export Node List Control with preserving node ID
  var ImExNodeListByNameControl = Backform.NodeListByNameControl.extend({
    defaults: _.extend(Backform.NodeListByNameControl.prototype.defaults, {
      url: 'nodes',

      transform: function(rows) {
        var self = this,
          node = this.field.get('schema_node'),
          model = this.model.top || this.model,
          res = [],
          map = {},
          sel_value = null,
          filter = this.field.get('filter') || function() {
            return true;
          };

        filter = filter.bind(self);
        sel_value = model && model.get(node.type) || null;

        _.each(rows, function(r) {
          if (filter(r)) {
            var l = (_.isFunction(node['node_label']) ?
                (node['node_label']).apply(node, [r, self.model, self]) :
                r.label),
              image = (_.isFunction(node['node_image']) ?
                (node['node_image']).apply(
                  node, [r, self.model, self]
                ) :
                (node['node_image'] || ('icon-' + node.type)));

            map[r.label] = r;
            res.push({
              'value': r.label,
              'image': image,
              'label': l,
              'selected': (sel_value ? r.label == sel_value : false),
            });
          }
        });

        self.model.attributes.nodes_info_map[self.field.attributes.name] = map;
        return res;
      },

      /**
       * Checks if it's OK to cache fetched options.
       * Objects with dependencies in general should not cache - there is no use.
       */
      can_cache: function() {
        var schema_node = this.schema_node || null;
        return !schema_node || !schema_node.parent_type;
      },

      /**
       * Checks if it's OK to fetch options, i.e. all dependent objects are initialized.
       * e.g. 'datasource' depend on 'data_group' being selected
       */
      can_fetch: function(model) {
        var schema_node = this.get('schema_node') || null;
        // by default fetch is allowed if no 'has_parent' function available 
        // - a different model
        var has_parent = _.isFunction(model.has_parent) 
          ? model.has_parent(schema_node.parent_type) : true;
        return schema_node && schema_node.type 
              && !(schema_node.parent_type && !has_parent);
      },

      /**
       * Automatically checks if disabled.
       * Parent object has to be selected for being active.
       */
      disabled: function(model) {
        var is_sel_disabled = model.is_sel_disabled || null;
        if (_.isFunction(is_sel_disabled))
          is_sel_disabled = is_sel_disabled.apply(this, arguments);
        return is_sel_disabled;
      },
    }),

    /**
     * Finds selected parent node model by type.
     * In case of arrays - the first found parent with value.
     */
    find_parent_node: function(this_type, parent_type, model) {
      var nodes_info_map = model.get('nodes_info_map') || null,
        parent_name = undefined;

      if (nodes_info_map) {
        parent_name = model.get_parent(parent_type) || null;
        if (parent_name) {
          try {
            return nodes_info_map[parent_type][parent_name];
          } catch (err) {
            model.errorModel.set(this_type, gettext('Error or invalid data group selected:'));
            return null;
          }
        }
      }
      return null;
    },

    /**
     * Returns selected parent node model.
     */
    fetch_dep: function(model) {
      var schema_node = this.field.get('schema_node') || null;

      return schema_node && schema_node.parent_type ?
        this.find_parent_node(schema_node.type, schema_node.parent_type, model) : null;
    },

    /**
     * Checks if it's OK to fetch options, i.e. all dependent objects are initialized.
     * e.g. 'datasource' depend on 'data_group' being selected
     */
    get_check_fetch: function(model, def_val) {
      var schema_node = this.field.get('schema_node') || null;
      return schema_node && schema_node.parent_type ? this.fetch_dep(model) : def_val;
    },

    /**
     * Rebuilds nodes datas based on selected items.
     */
    rebuild_node_info: function(parent_node, model) {
      var node_tree = {},
        i = 10,
        o = null,
        schema_node=null;

      // something to do only for nodes with parent ID
      if (!_.isBoolean(parent_node)) {
        o = parent_node;
        while (o) {
          o.priority = i--;
          node_tree[o._type] = o;
          schema_node = pgBrowser.Nodes[o._type] || null;
          if (schema_node && schema_node.parent_type) {
            o = this.find_parent_node(o._type, schema_node.parent_type, model);
          } else {
            o = null;
            break;
          }
        }
      }

      this.field.set('node_data', null);
      this.field.set('node_info', node_tree);
    },

    /**
     * Depenent changes might require data fetch.
     */
    render: function() {
      var schema_node = this.field.get('schema_node') || null,
        model = this.model.top || this.model,
        value = this.field.get('value') || null,
        selected_node = null;

      /**
       * Default value.
       */
      if (!value && schema_node && schema_node.type) {
        try {
          selected_node = model.get('selected_info')[schema_node.type] || null;
          if (selected_node) {
            var select2 = this.field.get('select2') || null;
            if (select2) {
              select2.first_empty = false;
              // this did not work with preselction - solved with: options[].selected 
              //select2.emptyOptions = true;
              //select2.tags = true;
              select2.allowClear = false;
              select2.openOnEnter = false;
            }
            //this.field.set('value', model.get(schema_node.type));
            this.field.set('disabled', true);
            // this triggeres 'render'
            //model.set(schema_node.type, selected_node.label);
          }
        } catch (ignore) {
          // no selected node for this type - ignoring
        }
      }

      /*
       * Data fetch here only for dependent nodes with known parent, as they might need reload.
       */
      if (!selected_node) {
        var get_fetch_parent = this.get_check_fetch(model, false);
        if (get_fetch_parent) {
          this.rebuild_node_info(get_fetch_parent, model);
          this.fetch_data();
        }
      }

      /**
       * Our disabled.
       */
      if (!selected_node && _.isBoolean(this.field.get('disabled'))) {
        this.field.set('disabled', this.defaults.disabled);
      }

      return Backform.NodeListByNameControl.prototype.render.apply(this, arguments);
    },

    initialize: function() {
      /*
       * Initialization from the original control.
       */
      Backform.NodeListByNameControl.prototype.initialize.apply(this, arguments);
    },
    
  });

  // Main model for Import/Export functionality
  var ImportExportModel = Backbone.Model.extend({
    defaults: {
      is_import: false,
      is_def_ds: true,
      /* false for Export */
      filename: undefined,
      format: 'csv',
      encoding: undefined,
      oid: undefined,
      header: undefined,
      delimiter: '',
      quote: '\"',
      escape: '\'',
      null_string: undefined,
      columns: null,
      icolumns: [],
      server_group: undefined,
      server: undefined,
      database: undefined,
      schema: undefined,
      table: undefined,
      data_group: undefined,
      datasource: undefined,
      bucket: undefined,
      dirobj: undefined,
      nodes_info_map: {},
    },
    schema: [{ /* master import/export options */
      type: 'nested',
      control: 'fieldset',
      label: gettext('Master Options'),
      group: gettext('Source/Destination'),
      contentClass: 'row',
      schema: [{ /* import / export switch */
        id: 'is_import',
        label: gettext('Import/Export'),
        cell: 'switch',
        type: 'switch',
        group: gettext('Master Options'),
        options: {
          'onText': gettext('Import'),
          'offText': gettext('Export'),
          width: '65',
        },
      }, { /* default datasource / selected datasource switch */
        id: 'is_def_ds',
        label: gettext('Default/Selected'),
        cell: 'switch',
        type: 'switch',
        group: gettext('Master Options'),
        options: {
          'onText': gettext('Default'),
          'offText': gettext('Selected'),
          width: '65',
        },
      }],
    }, { /* data source/destination selection panel */
      type: 'nested',
      control: 'fieldset',
      label: gettext('Data'),
      group: gettext('Source/Destination'),
      schema: [{ /* data group selection */
        id: 'data_group',
        label: gettext('Data Group'),
        cell: 'string',
        type: 'select2',
        deps: ['is_def_ds'],
        control: ImExNodeListByNameControl,
        node: 'data_group',
        placeholder: gettext('Select data group ...'),
        group: gettext('Data'),
        select2: {
          allowClear: false,
          width: '100%',
        },
        disabled: 'is_dep_ds_disabled',
      }, { /* data source selection */
        id: 'datasource',
        label: gettext('Data'),
        cell: 'string',
        type: 'select2',
        deps: ['is_def_ds', 'data_group'],
        control: ImExNodeListByNameControl,
        node: 'datasource',
        placeholder: gettext('Select data ...'),
        group: gettext('Data'),
        select2: {
          allowClear: false,
          width: '100%',
        },
        disabled: 'is_dep_ds_disabled',
      }, { /* data bucket selection */
        id: 'bucket',
        label: gettext('Bucket'),
        cell: 'string',
        type: 'select2',
        deps: ['is_def_ds', 'datasource'],
        control: ImExNodeListByNameControl,
        node: 'bucket',
        placeholder: gettext('Select bucket ...'),
        group: gettext('Data'),
        select2: {
          allowClear: false,
          width: '100%',
        },
        disabled: 'is_dep_ds_disabled',
      /*}, { /* data object selection 
        id: 'dirobj',
        label: gettext('Object'),
        cell: 'string',
        type: 'select2',
        deps: ['bucket'],
        control: ImExNodeListByNameControl,
        node: 'dirobj',
        placeholder: gettext('Select object ...'),
        group: gettext('Data'),
        select2: {
          allowClear: false,
          width: '100%',
        },*/
      }],
    }, { /* server source/destination selection panel */
      type: 'nested',
      control: 'fieldset',
      label: 'Server',
      group: gettext('Source/Destination'),
      schema: [{ /* server group selection */
        id: 'server_group',
        label: gettext('Server Group'),
        cell: 'string',
        type: 'select2',
        control: ImExNodeListByNameControl,
        node: 'server_group',
        placeholder: gettext('Select server group ...'),
        group: gettext('Server'),
        select2: {
          allowClear: false,
          width: '100%',
        },
      }, { /* server selection */
        id: 'server',
        label: gettext('Server'),
        cell: 'string',
        type: 'select2',
        deps: ['server_group'],
        control: ImExNodeListByNameControl,
        node: 'server',
        placeholder: gettext('Select server ...'),
        group: gettext('Server'),
        select2: {
          allowClear: false,
          width: '100%',
        },
        validate: function() {
          return this.load_server_preferences(this.server);
        },
      }, { /* database selection */
        id: 'database',
        label: gettext('Database'),
        cell: 'string',
        type: 'select2',
        deps: ['server'],
        control: ImExNodeListByNameControl,
        node: 'database',
        placeholder: gettext('Select database ...'),
        group: gettext('Server'),
        select2: {
          allowClear: false,
          width: '100%',
        },
      }, { /* schema selection */
        id: 'schema',
        label: gettext('Schema'),
        cell: 'string',
        type: 'select2',
        deps: ['database'],
        control: ImExNodeListByNameControl,
        node: 'schema',
        placeholder: gettext('Select schema ...'),
        group: gettext('Server'),
        select2: {
          allowClear: false,
          width: '100%',
        },
      }, { /* table selection */
        id: '',
        label: gettext('Table'),
        cell: 'string',
        type: 'select2',
        deps: ['schema'],
        control: ImExNodeListByNameControl,
        node: 'table',
        placeholder: gettext('Select table ...'),
        group: gettext('Server'),
        select2: {
          allowClear: false,
          width: '100%',
        },
      }],
    }, {
      type: 'nested',
      control: 'fieldset',
      label: gettext('File Info'),
      group: gettext('Options'),
      schema: [{ /* select file control for import */
        id: 'filename',
        label: gettext('Filename'),
        deps: ['is_import'],
        type: 'text',
        control: Backform.FileControl,
        group: gettext('File Info'),
        dialog_type: 'select_file',
        supp_types: ['csv', 'txt', 'par', '*'],
        visible: 'importing',
      }, { /* create file control for export */
        id: 'filename',
        label: gettext('Filename'),
        deps: ['is_import'],
        type: 'text',
        control: Backform.FileControl,
        group: gettext('File Info'),
        dialog_type: 'create_file',
        supp_types: ['csv', 'txt', 'par', '*'],
        visible: 'exporting',
      }, {
        id: 'format',
        label: gettext('Format'),
        cell: 'string',
        control: 'select2',
        group: gettext('File Info'),
        options: [{
          'label': 'binary',
          'value': 'binary',
        }, {
          'label': 'csv',
          'value': 'csv',
        }, {
          'label': 'text',
          'value': 'text',
        } ],
        disabled: 'isDisabled',
        select2: {
          allowClear: false,
          width: '100%',
        },
      }, {
        id: 'encoding',
        label: gettext('Encoding'),
        cell: 'string',
        control: 'node-ajax-options',
        node: 'database',
        url: 'get_encodings',
        first_empty: true,
        group: gettext('File Info'),
      }],
    }, {
      id: 'columns',
      label: gettext('Columns to import'),
      cell: 'string',
      deps: ['is_import'],
      type: 'array',
      first_empty: false,
      control: Backform.NodeListByNameControl.extend({
        // By default, all the import columns should be selected
        initialize: function() {
          Backform.NodeListByNameControl.prototype.initialize.apply(this, arguments);
          var self = this,
            options = self.field.get('options'),
            op_vals = [];

          if (_.isFunction(options)) {
            try {
              var all_cols = options.apply(self);
              for (var idx in all_cols) {
                op_vals.push((all_cols[idx])['value']);
              }
            } catch (e) {
              // Do nothing
              options = [];
              console.warn(e.stack || e);
            }
          } else {
            for (idx in options) {
              op_vals.push((options[idx])['value']);
            }
          }

          self.model.set('columns', op_vals);
        },
      }),
      transform: function(rows) {
        var self = this,
          node = self.field.get('schema_node'),
          res = [];

        _.each(rows, function(r) {
          // System columns with id less than 0 should not be added.
          if ('_id' in r && r._id > 0) {
            var l = (_.isFunction(node['node_label']) ?
                (node['node_label']).apply(node, [r, self.model, self]) :
                r.label),
              image = (_.isFunction(node['node_image']) ?
                (node['node_image']).apply(
                  node, [r, self.model, self]
                ) :
                (node['node_image'] || ('icon-' + node.type)));
            res.push({
              'value': r.label,
              'image': image,
              'label': l,
            });
          }
        });

        return res;
      },
      node: 'column',
      url: 'nodes',
      group: gettext('Columns'),
      select2: {
        multiple: true,
        allowClear: false,
        placeholder: gettext('Columns for importing...'),
        first_empty: false,
        preserveSelectionOrder: true,
      },
      visible: 'importing',
      helpMessage: gettext('An optional list of columns to be copied. If no column list is specified, all columns of the table will be copied.'),
    }, {
      id: 'columns',
      label: gettext('Columns to export'),
      cell: 'string',
      deps: ['is_import'],
      type: 'array',
      control: 'node-list-by-name',
      first_empty: false,
      node: 'column',
      url: 'nodes',
      group: gettext('Columns'),
      select2: {
        multiple: true,
        allowClear: true,
        first_empty: false,
        placeholder: gettext('Colums for exporting...'),
        preserveSelectionOrder: true,
      },
      visible: 'exporting',
      transform: function(rows) {
        var self = this,
          node = self.field.get('schema_node'),
          res = [];

        _.each(rows, function(r) {
          var l = (_.isFunction(node['node_label']) ?
              (node['node_label']).apply(node, [r, self.model, self]) :
              r.label),
            image = (_.isFunction(node['node_image']) ?
              (node['node_image']).apply(
                node, [r, self.model, self]
              ) :
              (node['node_image'] || ('icon-' + node.type)));
          res.push({
            'value': r.label,
            'image': image,
            'label': l,
          });
        });

        return res;
      },
      helpMessage: gettext('An optional list of columns to be copied. If no column list is specified, all columns of the table will be copied.'),
    }, {
      id: 'null_string',
      label: gettext('NULL Strings'),
      cell: 'string',
      type: 'text',
      group: gettext('Columns'),
      disabled: 'isDisabled',
      deps: ['format'],
      helpMessage: gettext('Specifies the string that represents a null value. The default is \\N (backslash-N) in text format, and an unquoted empty string in CSV format. You might prefer an empty string even in text format for cases where you don\'t want to distinguish nulls from empty strings. This option is not allowed when using binary format.'),
    }, {
      id: 'icolumns',
      label: gettext('Not null columns'),
      cell: 'string',
      control: 'node-list-by-name',
      node: 'column',
      group: gettext('Columns'),
      deps: ['format', 'is_import'],
      disabled: 'isDisabled',
      type: 'array',
      first_empty: false,
      select2: {
        multiple: true,
        allowClear: true,
        first_empty: false,
        placeholder: gettext('Not null columns...'),
      },
      helpMessage: gettext('Do not match the specified column values against the null string. In the default case where the null string is empty, this means that empty values will be read as zero-length strings rather than nulls, even when they are not quoted. This option is allowed only in import, and only when using CSV format.'),
    }, {
      type: 'nested',
      control: 'fieldset',
      label: gettext('Miscellaneous'),
      group: gettext('Options'),
      schema: [{
        id: 'oid',
        label: gettext('OID'),
        cell: 'string',
        type: 'switch',
        group: gettext('Miscellaneous'),
      }, {
        id: 'header',
        label: gettext('Header'),
        cell: 'string',
        type: 'switch',
        group: gettext('Miscellaneous'),
        deps: ['format'],
        disabled: 'isDisabled',
      }, {
        id: 'delimiter',
        label: gettext('Delimiter'),
        cell: 'string',
        first_empty: true,
        type: 'text',
        control: 'node-ajax-options',
        group: gettext('Miscellaneous'),
        disabled: 'isDisabled',
        deps: ['format'],
        options: [{
          'label': ';',
          'value': ';',
        },
        {
          'label': ',',
          'value': ',',
        },
        {
          'label': '|',
          'value': '|',
        },
        {
          'label': '[tab]',
          'value': '[tab]',
        },
        ],
        select2: {
          tags: true,
          allowClear: false,
          width: '100%',
          placeholder: gettext('Select from list...'),
        },
        helpMessage: gettext('Specifies the character that separates columns within each row (line) of the file. The default is a tab character in text format, a comma in CSV format. This must be a single one-byte character. This option is not allowed when using binary format.'),
      },
      {
        id: 'quote',
        label: gettext('Quote'),
        cell: 'string',
        first_empty: true,
        deps: ['format'],
        type: 'text',
        control: 'node-ajax-options',
        group: gettext('Miscellaneous'),
        disabled: 'isDisabled',
        options: [{
          'label': '\"',
          'value': '\"',
        },
        {
          'label': '\'',
          'value': '\'',
        },
        ],
        select2: {
          tags: true,
          allowClear: false,
          width: '100%',
          placeholder: gettext('Select from list...'),
        },
        helpMessage: gettext('Specifies the quoting character to be used when a data value is quoted. The default is double-quote. This must be a single one-byte character. This option is allowed only when using CSV format.'),
      },
      {
        id: 'escape',
        label: gettext('Escape'),
        cell: 'string',
        first_empty: true,
        deps: ['format'],
        type: 'text',
        control: 'node-ajax-options',
        group: gettext('Miscellaneous'),
        disabled: 'isDisabled',
        options: [{
          'label': '\"',
          'value': '\"',
        },
        {
          'label': '\'',
          'value': '\'',
        },
        ],
        select2: {
          tags: true,
          allowClear: false,
          width: '100%',
          placeholder: gettext('Select from list...'),
        },
        helpMessage: gettext('Specifies the character that should appear before a data character that matches the QUOTE value. The default is the same as the QUOTE value (so that the quoting character is doubled if it appears in the data). This must be a single one-byte character. This option is allowed only when using CSV format.'),
      },
      ],
    } ],

    // Enable/Disable the items based on the user file format selection
    isDisabled: function(m) {
      switch (this.name) {
      case 'quote':
      case 'escape':
      case 'header':
        return (m.get('format') != 'csv');
      case 'icolumns':
        return (m.get('format') != 'csv' || !m.get('is_import'));
      case 'null_string':
      case 'delimiter':
        return (m.get('format') == 'binary');
      default:
        return false;
      }
    },
    importing: function(m) {
      return m.get('is_import');
    },
    exporting: function(m) {
      return !(m.importing.apply(this, arguments));
    },
    def_ds: function(m) {
      return m.get('is_def_ds');
    },
    sel_ds: function(m) {
      return !(m.get('is_def_ds'));
    },
    is_dep_ds_disabled: function(m) {
      return m.def_ds.apply(this, arguments) || m.is_sel_disabled.apply(this, arguments);
    },
    is_sel_disabled: function(m) {
      var schema_node = this.schema_node || null;
      var has_parent = _.isFunction(m.has_parent) 
        ? m.has_parent(schema_node.parent_type) : false;
      return !schema_node || !schema_node.type 
        || schema_node.parent_type && !has_parent;
    },
    has_parent: function(parent) {
      var self = this,
        found_parent=null;
      if (Array.isArray(parent)) {
        found_parent = !parent.every(function(e) {
          return !self.get(e);
        });
      } else {
        found_parent = !!self.get(parent);
      }
      return found_parent;
    },
    get_parent: function(parent) {
      var self = this;
      if (Array.isArray(parent)) {
        for (var e of parent) {
          if(self.get(e))
            return self.get(e);
        }
      } else {
        return self.get(parent);
      }

      return null;
    },
    ds_info: function() {
      var ds_type = 'FS',
        ds_info = {},
        sel_dg = this.get('data_group') || null,
        sel_ds = this.get('datasource') || null,
        sel_bucket = this.get('bucket') || null,
        mapper = this.get('nodes_info_map');
      if (this.sel_ds(this) && sel_dg && sel_ds && sel_bucket && mapper) {
        var ds = mapper['datasource'][sel_ds] || null;
        ds_info = { 
          ds_type: ds.datasource_type,
          ds_id: ds._id,
          ds_name: ds.name,
          ds_bucket: sel_bucket,
        };
      } else {
        ds_info = {
          ds_type: ds_type,
          ds_id: null,
          ds_name: null,
          ds_bucket: null,
        };
      }

      return ds_info;
    },
  });

  pgTools.import_utility = {
    init: function() {
      // We do not want to initialize the module multiple times.
      if (this.initialized)
        return;

      this.initialized = true;

      // Initialize the context menu to display the import options when user
      // open the context menu for table or data source
      var import_nodes = ['table', 'bucket', 'dirobj'];
      pgBrowser.add_menus([{
        name: 'import',
        module: this,
        applies: ['tools'],
        callback: 'callback_import_export',
        category: 'import',
        priority: 10,
        label: gettext('Import/Export...'),
        icon: 'fa fa-shopping-cart',
        enable: supportedNodes.enabled.bind(
          null, pgBrowser.treeMenu, import_nodes
        ),
      }]);
      for (var n_name of import_nodes) {
        pgBrowser.add_menus([{
          name: 'import',
          node: n_name,
          module: this,
          applies: ['context'],
          callback: 'callback_import_export',
          category: 'import',
          priority: 10,
          label: gettext('Import/Export...'),
          icon: 'fa fa-shopping-cart',
          enable: supportedNodes.enabled.bind(
            null, pgBrowser.treeMenu, [n_name]
          ),
        }]);
      }
    },

    /*
     * Loads db server preferences
     */
    load_server_preferences: function(server_data) {
      var module = 'paths',
        preference_name = 'pg_bin_dir',
        msg = gettext('Please configure the PostgreSQL Binary Path in the Preferences dialog.');

      if ((server_data.type && server_data.type == 'ppas') ||
        server_data.server_type == 'ppas') {
        preference_name = 'ppas_bin_dir';
        msg = gettext('Please configure the EDB Advanced Server Binary Path in the Preferences dialog.');
      } else if ((server_data.type && server_data.type == 'dbx') ||
        server_data.server_type == 'dbx') {
        preference_name = 'dbx_bin_dir';
        msg = gettext('Please configure the dbX Binary Path in the Preferences dialog.');
      }

      var preference = pgBrowser.get_preference(module, preference_name);

      if (preference) {
        if (!preference.value) {
          Alertify.alert(gettext('Configuration required'), msg);
          return false;
        }
      } else {
        Alertify.alert(gettext('Failed to load preference %s of module %s', preference_name, module));
        return false;
      }

      return true;
    },

    /*
      Open the dialog for the import functionality
    */
    callback_import_export: function(args, item) {
      var i = item || pgBrowser.tree.selected(),
        source_data = null,
        check_data = null,
        root_nodes = ['server_group', 'data_group'],
        check_nodes = ['server'];

      while (i) {
        var node_data = pgBrowser.tree.itemData(i);
        if (!check_data && check_nodes.includes(node_data._type)) {
          check_data = node_data;
        }
        if (root_nodes.includes(node_data._type)) {
          source_data = node_data;
          break;
        }

        if (pgBrowser.tree.hasParent(i)) {
          i = $(pgBrowser.tree.parent(i));
        } else {
          Alertify.alert(gettext('Please select server/data or child node from tree.'));
          break;
        }
      }

      if (!source_data) {
        return;
      }

      if (check_data && check_data.module == 'pgadmin.node.server') {
        this.load_server_preferences(check_data);
      }

      var t = pgBrowser.tree;
      i = item || t.selected();
      var d = i && i.length == 1 ? t.itemData(i) : undefined,
        node = d && pgBrowser.Nodes[d._type];

      if (!d)
        return;

      var treeInfo = node.getTreeNodeHierarchy.apply(node, [i]);


      if (!Alertify.ImportDialog) {
        Alertify.dialog('ImportDialog', function factory() {

          return {
            /**
             * node: selected data model node (general from pgBrowser)
             * item: selected (or clicked on) tree view element
             * data: data from selected tree view for data model (schema)
             */
            main: function(title, node, item, data) {
              this.set('title', title);
              this.setting('pg_node', node);
              this.setting('pg_item', item);
              this.setting('pg_item_data', data);
            },

            build: function() {
              Alertify.pgDialogBuild.apply(this);
            },

            setup: function() {
              return {
                buttons: [{
                  text: gettext('Cancel'),
                  key: 27,
                  'data-btn-name': 'cancel',
                  className: 'btn btn-secondary fa fa-lg fa-times pg-alertify-button',
                }, {
                  text: gettext('OK'),
                  key: 13,
                  disable: true,
                  'data-btn-name': 'ok',
                  className: 'btn btn-primary fa fa-lg fa-check pg-alertify-button',
                }],
                options: {
                  modal: true,
                  padding: !1,
                  overflow: !1,
                },
              };
            },

            settings: {
              pg_node: null,
              pg_item: null,
              pg_item_data: null,
            },

            // Callback functions when click on the buttons of the Alertify dialogs
            callback: function(e) {
              if (e.button['data-btn-name'] === 'ok') {

                var n = this.settings['pg_node'],
                  i = this.settings['pg_item'],
                  treeInfo = n.getTreeNodeHierarchy.apply(n, [i]);

                this.view.model.set({
                  'database': treeInfo.database._label,
                  'schema': treeInfo.schema._label,
                  'table': treeInfo.table._label,
                });
                var self = this;

                $.ajax({
                  url: url_for(
                    'import_export.create_job', {
                      'sid': treeInfo.server._id,
                    }
                  ),
                  method: 'POST',
                  data: {
                    'data': JSON.stringify(this.view.model.toJSON()),
                  },
                })
                  .done(function(res) {
                    if (res.success) {
                      Alertify.success(gettext('Import/Export job created.'), 5);
                      pgBrowser.Events.trigger('pgadmin-bgprocess:created', self);
                    } else {
                      Alertify.alert(
                        gettext('Import/Export job creation failed.'),
                        res.errormsg
                      );
                    }
                  })
                  .fail(function(xhr) {
                    try {
                      var err = JSON.parse(xhr.responseText);
                      Alertify.alert(
                        gettext('Import/Export job failed.'),
                        err.errormsg
                      );
                    } catch (e) {
                      console.warn(e.stack || e);
                    }
                  });
              }
            },

            hooks: {
              onclose: function() {
                if (this.view) {
                  this.view.remove({
                    data: true,
                    internal: true,
                    silent: true,
                  });
                }
              },

              // triggered when a dialog option gets update.
              onupdate: function(option, oldValue, newValue) {

                switch (option) {
                case 'resizable':
                  if (newValue) {
                    this.elements.content.removeAttribute('style');
                  } else {
                    this.elements.content.style.minHeight = 'inherit';
                  }
                  break;
                }
              },

              onshow: function() {
                var container = $(this.elements.body).find('.tab-content:first > .tab-pane.active:first');
                commonUtils.findAndSetFocus(container);
              },
            },

            prepare: function() {
              // Main import module container
              var self = this;

              // Disable OK button until user provides valid Filename
              this.__internal.buttons[1].element.disabled = true;

              var $container = $('<div class=\'import_dlg\'></div>'),
                n = this.settings.pg_node,
                i = this.settings.pg_item,
                treeInfo = n.getTreeNodeHierarchy.apply(n, [i]),
                newModel = new ImportExportModel({}, {
                  node_info: {},
                }),
                fields = Backform.generateViewSchema(
                  treeInfo, newModel, 'create', node, treeInfo.server, true
                ),
                view = this.view = new Backform.Dialog({
                  el: $container,
                  model: newModel,
                  schema: fields,
                });

              $(this.elements.body.childNodes[0]).addClass(
                'alertify_tools_dialog_properties obj_properties'
              );
              // My variable is not propagated as 'node_info'
              newModel.set('selected_info', treeInfo);
              _.each(treeInfo, function(e) {
                try {
                  newModel.set(e._type, e._label);
                } catch (ignore) {
                  // placeholder for syntax checker
                }
              });
              newModel.set('is_def_ds', !newModel.get('data_group'));
              //
              view.render();

              this.elements.content.appendChild($container.get(0));

              // Listen to model & if filename is provided then enable OK button
              // For the 'Quote', 'escape' and 'delimiter' only one character is allowed to enter
              this.view.model.on('change', function() {
                if (!_.isUndefined(this.get('filename')) && this.get('filename') !== '') {
                  this.errorModel.clear();
                  if (!_.isUndefined(this.get('delimiter')) && !_.isNull(this.get('delimiter'))) {
                    this.errorModel.clear();
                    if (!_.isUndefined(this.get('quote')) && this.get('quote') !== '' &&
                      this.get('quote').length == 1) {
                      this.errorModel.clear();
                      if (!_.isUndefined(this.get('escape')) && this.get('escape') !== '' &&
                        this.get('escape').length == 1) {
                        this.errorModel.clear();
                        self.__internal.buttons[1].element.disabled = false;
                      } else {
                        self.__internal.buttons[1].element.disabled = true;
                        this.errorModel.set('escape', gettext('Escape should contain only one character'));
                      }
                    } else {
                      self.__internal.buttons[1].element.disabled = true;
                      this.errorModel.set('quote', gettext('Quote should contain only one character'));
                    }
                  } else {
                    self.__internal.buttons[1].element.disabled = true;
                    this.errorModel.set('delimiter', gettext('Delimiter should contain only one character'));
                  }
                } else {
                  self.__internal.buttons[1].element.disabled = true;
                  this.errorModel.set('filename', gettext('Please provide filename'));
                }
              });

              view.$el.attr('tabindex', -1);
              setTimeout(function() {
                pgBrowser.keyboardNavigation.getDialogTabNavigator($(self.elements.dialog));
              }, 200);
            },
          };
        });
      }


      var StartImportDialog = !check_data;

      if (!StartImportDialog) {
        const baseUrl = url_for('import_export.utility_exists', {
          'sid': check_data._id,
        });

        // Check psql utility exists or not.
        $.ajax({
          url: baseUrl,
          type:'GET',
        })
          .done(function(res) {
            if (!res.success) {
              Alertify.alert(
                gettext('Utility not found'),
                res.errormsg
              );
              return;
            }

            // Open the Alertify dialog for the import/export module
            Alertify.ImportDialog(
              gettext('Import/Export data - table \'%s\'', treeInfo.table.label),
              node, i, d
            ).set('resizable', true).resizeTo(pgAdmin.Browser.stdW.md,pgAdmin.Browser.stdH.lg);
            return;
          })
          .fail(function() {
            Alertify.alert(
              gettext('Utility not found'),
              gettext('Failed to fetch Utility information')
            );
            return;
          });
      } else {
        // Open the Alertify dialog for the import/export module
        Alertify.ImportDialog(
          gettext('Import/Export data - preselected \'%s\'', source_data.label),
          node, i, d
        ).set('resizable', true).resizeTo(pgAdmin.Browser.stdW.md,pgAdmin.Browser.stdH.lg);
      }
    },
  };

  return pgAdmin.Tools.import_utility;
});
