define('pgadmin.node.fts_dictionary', [
  'sources/gettext', 'sources/url_for', 'underscore', 'pgadmin.backform',
  'pgadmin.browser', 'pgadmin.browser.collection',
], function(gettext, url_for, _, Backform, pgBrowser) {

  // Extend the browser's node model class to create a option/value pair
  var OptionLabelModel = pgBrowser.Node.Model.extend({
    defaults: {options: undefined, value: undefined},
    // Define the schema for the Options
    schema: [{
      id: 'option', label: gettext('Option'), type:'text', group: null,
      cellHeaderClasses: 'width_percent_50', editable: true,
    },{
      id: 'value', label: gettext('Value'), type: 'text', group:null,
      cellHeaderClasses: 'width_percent_50', editable: true,
    }],
    validate: function() {
      var msg;

      // Clear any existing errors.
      this.errorModel.clear();

      if (
        _.isUndefined(this.get('option')) ||
        String(this.get('option')).replace(/^\s+|\s+$/g, '') === ''
      ) {
        msg = gettext('Option cannot be empty!');
        this.errorModel.set('option',msg);
        return msg;
      }
      if (
        _.isUndefined(this.get('value')) ||
        String(this.get('value')).replace(/^\s+|\s+$/g, '') === ''
      ) {
        msg = gettext('Value cannot be empty!');
        this.errorModel.set('value',msg);
        return msg;
      }
      return null;
    },
  });

  // Extend the collection class for FTS Dictionary
  if (!pgBrowser.Nodes['coll-fts_dictionary']) {
    pgBrowser.Nodes['coll-fts_dictionary'] =
      pgBrowser.Collection.extend({
        node: 'fts_dictionary', label: gettext('FTS Dictionaries'),
        type: 'coll-fts_dictionary', columns: ['name', 'description'],
      });
  }

  // Extend the node class for FTS Dictionary
  if (!pgBrowser.Nodes.fts_dictionary) {
    pgBrowser.Nodes.fts_dictionary = pgBrowser.Node.extend({
      parent_type: ['schema', 'catalog'],
      type: 'fts_dictionary',
      sqlAlterHelp: 'sql-altertsdictionary.html',
      sqlCreateHelp: 'sql-createtsdictionary.html',
      dialogHelp: url_for('help.static', {'filename': 'fts_dictionary_dialog.html'}),
      canDrop: true,
      canDropCascade: true,
      label: gettext('FTS Dictionary'),
      hasSQL: true,
      hasDepends: true,
      Init: function() {

        // Avoid multiple registration of menus
        if (this.initialized) {
          return;
        }

        this.initialized = true;

        // Add context menus for FTS Dictionary
        pgBrowser.add_menus([{
          name: 'create_fts_dictionary_on_schema', node: 'schema', module: this,
          applies: ['object', 'context'], callback: 'show_obj_properties',
          category: 'create', priority: 4, label: gettext('FTS Dictionary...'),
          icon: 'wcTabIcon icon-fts_dictionary', data: {action: 'create'},
          enable: 'canCreate',
        },{
          name: 'create_fts_dictionary_on_coll', node: 'coll-fts_dictionary',
          module: this, applies: ['object', 'context'],  priority: 4,
          callback: 'show_obj_properties', category: 'create',
          label: gettext('FTS Dictionary...'), data: {action: 'create'},
          icon: 'wcTabIcon icon-fts_dictionary', enable: 'canCreate',
        },{
          name: 'create_fts_dictionary', node: 'fts_dictionary', module: this,
          applies: ['object', 'context'], callback: 'show_obj_properties',
          category: 'create', priority: 4, label: gettext('FTS Dictionary...'),
          icon: 'wcTabIcon icon-fts_dictionary', data: {action: 'create'},
          enable: 'canCreate',
        }]);
      },

      // Defining backform model for FTS Dictionary node
      model: pgBrowser.Node.Model.extend({
        defaults: {
          name: undefined,        // FTS Dictionary name
          owner: undefined,       // FTS Dictionary owner
          description: undefined, // Comment on FTS Dictionary
          schema: undefined,      // Schema name FTS dictionary belongs to
          template: undefined,    // Template list for FTS dictionary node
          options: undefined,      // option/value pair list for FTS Dictionary
        },
        initialize: function(attrs, args) {
          var isNew = (_.size(attrs) === 0);
          pgBrowser.Node.Model.prototype.initialize.apply(this, arguments);

          if (isNew) {
            var user = pgBrowser.serverInfo[args.node_info.server._id].user;
            this.set({
              'owner': user.name,
              'schema': args.node_info.schema._id,
            }, {silent: true});
          }
        },
        // Defining schema for fts dictionary
        schema: [{
          id: 'name', label: gettext('Name'), cell: 'string',
          type: 'text', cellHeaderClasses: 'width_percent_50',
        },{
          id: 'oid', label: gettext('OID'), cell: 'string',
          editable: false, type: 'text', disabled: true, mode:['properties'],
        },{
          id: 'owner', label: gettext('Owner'), cell: 'string',
          type: 'text', mode: ['properties', 'edit','create'], node: 'role',
          control: Backform.NodeListByNameControl,
        },{
          id: 'schema', label: gettext('Schema'), cell: 'string',
          type: 'text', mode: ['create','edit'], node: 'schema',
          cache_node: 'database', control: 'node-list-by-id',
        },{
          id: 'description', label: gettext('Comment'), cell: 'string',
          type: 'multiline', cellHeaderClasses: 'width_percent_50',
        },{
          id: 'template', label: gettext('Template'),type: 'text',
          disabled: function(m) { return !m.isNew(); }, url: 'fetch_templates',
          group: gettext('Definition'), control: 'node-ajax-options',
          cache_node: 'fts_template',
        },{
          id: 'options', label: gettext('Option'), type: 'collection',
          group: gettext('Options'), control: 'unique-col-collection',
          model: OptionLabelModel, columns: ['option', 'value'],
          uniqueCol : ['option'], mode: ['edit', 'create'],
          canAdd: true, canEdit: false,canDelete: true,
        }],

        /*
         * Triggers control specific error messages for dictionary name,
         * template and schema, if any one of them is not specified
         * while creating new fts dictionary
         */
        validate: function() {
          var name = this.get('name'),
            template = this.get('template'),
            schema = this.get('schema'),
            msg;

          // Validate FTS Dictionary name
          if (
            _.isUndefined(name) || _.isNull(name) ||
              String(name).replace(/^\s+|\s+$/g, '') === ''
          ) {
            msg = gettext('Name must be specified!');
            this.errorModel.set('name', msg);
            return msg;
          }
          if (
            _.isUndefined(template) || _.isNull(template) ||
              String(template).replace(/^\s+|\s+$/g, '') === ''
          ) {
            // Validate template name
            msg = gettext('Template must be selected!');
            this.errorModel.set('template', msg);
            return msg;
          }
          if (
            _.isUndefined(schema) || _.isNull(schema) ||
              String(schema).replace(/^\s+|\s+$/g, '') === ''
          ) {
            // Validate schema
            msg = gettext('Schema must be selected!');
            this.errorModel.set('schema', msg);
            return msg;
          }
          this.errorModel.clear();

          this.trigger('on-status-clear');
          return null;
        },
      }),
      canCreate: function(itemData, item, data) {
        //If check is false then , we will allow create menu
        if (data && !data.check) {
          return true;
        }

        var t = pgBrowser.tree, i = item, d = itemData,
          prev_i, prev_d;
        // To iterate over tree to check parent node
        while (i) {
          // If it is schema then allow user to create fts dictionary
          if (_.indexOf(['schema'], d._type) > -1) {
            return true;
          }

          if (d._type === 'coll-fts_dictionary') {
            // Check if we are not child of catalog
            prev_i = t.hasParent(i) ? t.parent(i) : null;
            prev_d = prev_i ? t.itemData(prev_i) : null;

            return prev_d && prev_d._type !== 'catalog';
          }
          i = t.hasParent(i) ? t.parent(i) : null;
          d = i ? t.itemData(i) : null;
        }
        // by default we do not want to allow create menu
        return true;
      },
    });
  }

  return pgBrowser.Nodes.fts_dictionary;
});
