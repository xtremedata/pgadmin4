define('pgadmin.node.server_group', [
  'sources/gettext', 'sources/url_for', 'underscore', 'pgadmin.browser',
  'pgadmin.browser.node',
], function(gettext, url_for, _, pgBrowser) {

  if (!pgBrowser.Nodes.server_group) {
    pgBrowser.Nodes.server_group = pgBrowser.Node.extend({
      parent_type: null,
      type: 'server_group',
      dialogHelp: url_for(
        'help.static', {'filename': 'server_group_dialog.html'}
      ),
      label: gettext('Server Group'),
      width: '350px',
      height: '250px',
      is_collection: true,
      Init: function() {
        /* Avoid multiple registration of menus */
        if (this.initialized)
          return;

        this.initialized = true;

        pgBrowser.add_menus([{
          name: 'create_server_group', node: 'server_group', module: this,
          applies: ['object', 'context'], callback: 'show_obj_properties',
          category: 'create', priority: 1, label: gettext('Server Group...'),
          data: {'action': 'create'}, icon: 'wcTabIcon icon-server_group',
        }]);
      },
      model: pgBrowser.Node.Model.extend({
        defaults: {
          id: undefined,
          name: null,
        },
        schema: [
          {
            id: 'id', label: gettext('ID'), type: 'int', group: null,
            mode: ['properties'],
          },{
            id: 'name', label: gettext('Name'), type: 'text', group: null,
            mode: ['properties', 'edit', 'create'],
          },
        ],
        validate: function() {
          var errmsg = null;

          if (!this.isNew() && 'id' in this.changed) {
            errmsg = gettext('The ID cannot be changed.');
            this.errorModel.set('id', errmsg);
            return errmsg;
          }
          if (
            _.isUndefined(this.get('name')) || _.isNull(this.get('name')) ||
            String(this.get('name')).replace(/^\s+|\s+$/g, '') === ''
          ) {
            errmsg = gettext('Name cannot be empty.');
            this.errorModel.set('name', errmsg);
            return errmsg;
          }
          this.errorModel.unset('id');
          this.errorModel.unset('name');

          return null;
        },
      }),
      canDrop: function(itemData) { return itemData.can_delete; },
      canDelete: function(i) {
        var s = pgBrowser.tree.siblings(i, true);

        /* This is the only server group - we can't remove it*/
        if (!s || s.length == 0) {
          return false;
        }
        return true;
      },
    });
  }

  return pgBrowser.Nodes.server_group;
});
