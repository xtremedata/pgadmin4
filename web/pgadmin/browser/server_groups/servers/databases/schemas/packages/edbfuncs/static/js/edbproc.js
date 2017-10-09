/* Create and Register Procedure Collection and Node. */
define('pgadmin.node.edbproc', [
  'sources/gettext', 'sources/url_for', 'underscore', 'pgadmin.browser',
  'pgadmin.node.edbfunc', 'pgadmin.browser.collection',
  'pgadmin.browser.server.privilege',
], function(gettext, url_for, _, pgBrowser, EdbFunction) {

  if (!pgBrowser.Nodes['coll-edbproc']) {
    pgBrowser.Nodes['coll-edbproc'] =
      pgBrowser.Collection.extend({
        node: 'edbproc',
        label: gettext('Procedures'),
        type: 'coll-edbproc',
        columns: ['name', 'funcowner', 'description'],
        hasStatistics: true,
      });
  }

  // Inherit Functions Node
  if (!pgBrowser.Nodes.edbproc) {
    pgBrowser.Nodes.edbproc = pgBrowser.Node.extend({
      type: 'edbproc',
      dialogHelp: url_for('help.static', {'filename': 'edbproc_dialog.html'}),
      label: gettext('Procedure'),
      collection_type: 'coll-edbproc',
      hasDepends: true,
      canEdit: false,
      hasSQL: true,
      hasScriptTypes: [],
      parent_type: ['package'],
      Init: function() {
        /* Avoid multiple registration of menus */
        if (this.proc_initialized) {
          return;
        }

        this.proc_initialized = true;
      },
      canDrop: false,
      canDropCascade: false,
      model: EdbFunction.model.extend({
        defaults: _.extend(
          {}, EdbFunction.model.prototype.defaults, {lanname: 'edbspl'}
        ),
        isVisible: function() {
          if (this.name === 'sysfunc') { return false; }
          if (this.name === 'sysproc') { return true; }
          return false;
        },
        validate: function()
        {
          return null;
        },
      }),
    });
  }

  return pgBrowser.Nodes.edbproc;
});
