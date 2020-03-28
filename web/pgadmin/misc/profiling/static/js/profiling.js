/////////////////////////////////////////////////////////////
//
// pgAdmin 4 - PostgreSQL Tools
//
// Copyright (C) 2013 - 2020, The pgAdmin Development Team
// This software is released under the PostgreSQL Licence
//
//////////////////////////////////////////////////////////////

define('misc.profiling', [
  'sources/gettext', 'underscore', 'jquery', 'backbone',
  'sources/pgadmin', 'pgadmin.browser', 'pgadmin.alertifyjs', 'pgadmin.backgrid',
  'sources/size_prettify',
  'sources/utils',
], function(gettext, _, $, Backbone,
  pgAdmin, pgBrowser, Alertify, Backgrid,
  pgadminUtils,
  sizePrettify) {

  if (pgBrowser.NodeProfiling)
    return pgBrowser.NodeProfiling;

  pgBrowser.NodeProfiling = pgBrowser.NodeProfiling || {};

  var wcDocker = window.wcDocker;

  var SizeFormatter = Backgrid.SizeFormatter = function() {};
  _.extend(SizeFormatter.prototype, {
    /**
       Takes a raw value from a model and returns the human readable formatted
       string for display.

       @member Backgrid.SizeFormatter
       @param {*} rawData
       @param {Backbone.Model} model Used for more complicated formatting
       @return {*}
    */
    fromRaw: function(rawData) {
      return sizePrettify(rawData);
    },
    toRaw: function(formattedData) {
      return formattedData;
    },
  });

  var PGBooleanCell = Backgrid.Extension.SwitchCell.extend({
      defaults: _.extend({}, Backgrid.Extension.SwitchCell.prototype.defaults),
    }),
    typeCellMapper = {
      // boolean
      16: PGBooleanCell,
      // int8
      20: Backgrid.IntegerCell,
      // int2
      21: Backgrid.IntegerCell,
      // int4
      23: Backgrid.IntegerCell,
      // float4
      700: Backgrid.NumberCell,
      // float8
      701: Backgrid.NumberCell,
      // numeric
      1700: Backgrid.NumberCell,
      // abstime
      702: Backgrid.DatetimeCell,
      // reltime
      703: Backgrid.DatetimeCell,
      // date
      1082: Backgrid.DatetimeCell.extend({
        includeDate: true,
        includeTime: false,
        includeMilli: false,
      }),
      // time
      1083: Backgrid.DatetimeCell.extend({
        includeDate: false,
        includeTime: true,
        includeMilli: true,
      }),
      // timestamp
      1114: Backgrid.DatetimeCell.extend({
        includeDate: true,
        includeTime: true,
        includeMilli: true,
      }),
      // timestamptz
      1184: 'string'
      /* Backgrid.DatetimeCell.extend({
              includeDate: true, includeTime: true, includeMilli: true
            }) */
      ,
      1266: 'string',
      /* Backgrid.DatetimeCell.extend({
            includeDate: false, includeTime: true, includeMilli: true
          }) */
    },
    GRID_CLASSES = 'backgrid presentation table table-bordered table-noouter-border table-hover';

  _.extend(
    PGBooleanCell.prototype.defaults.options, {
      onText: gettext('True'),
      offText: gettext('False'),
      onColor: 'success',
      offColor: 'primary',
      size: 'mini',
    }
  );

  _.extend(pgBrowser.NodeProfiling, {
    init: function() {
      if (this.initialized) {
        return;
      }

      this.initialized = true;
      this.profilingPanel = pgBrowser.docker.findPanels('profiling')[0];
      /* Parameter is used to set the proper label of the
       * backgrid header cell.
       */
      _.bindAll(this, 'showProfiling', '__loadMoreRows', '__appendGridToPanel');

      _.extend(
        this, {
          initialized: true,
          collection: new(Backbone.Collection)(null),
          profiling_columns: [{
            editable: false,
            name: 'profiling',
            label: gettext('Profiling Parameter'),
            cell: 'string',
            headerCell: Backgrid.Extension.CustomHeaderCell,
            cellHeaderClasses: 'width_percent_25',
          }, {
            editable: false,
            name: 'value',
            label: gettext('Value'),
            cell: 'string',
          }],
          columns: null,
          grid: null,
        });

      // Defining Backbone Model for Profiling.
      var Model = Backbone.Model.extend({
        defaults: {
          icon: 'icon-unknown',
          type: undefined,
          name: undefined,
          /* field contains 'Database Name' for 'Tablespace and Role node',
           * for other node it contains 'Restriction'.
           */
          field: undefined,
        },
        // This function is used to fetch/set the icon for the type(Function, Role, Database, ....)
        parse: function(res) {
          var node = pgBrowser.Nodes[res.type];
          if(res.icon == null || res.icon == '') {
            res.icon = node ? (_.isFunction(node['node_image']) ?
              (node['node_image']).apply(node, [null, null]) :
              (node['node_image'] || ('icon-' + res.type))) :
              ('icon-' + res.type);
          }
          res.type = pgadminUtils.titleize(res.type.replace(/_/g, ' '), true);
          return res;
        },
      });

      // Defining Backbone Collection for Profiling.
      this.profilingCollection = new(Backbone.Collection.extend({
        model: Model,
      }))(null);

      pgBrowser.Events.on('pgadmin-browser:tree:selected', this.showProfiling);
      pgBrowser.Events.on('pgadmin-browser:tree:refreshing', this.refreshProfiling, this);
      this.__appendGridToPanel();
    },

    /* Function is used to create and render backgrid with
     * empty collection. We just want to add backgrid into the
     * panel only once.
     */
    __appendGridToPanel: function() {
      var $container = this.profilingPanel.layout().scene().find('.pg-panel-content'),
        $gridContainer = $container.find('.pg-panel-profiling-container'),
        grid = new Backgrid.Grid({
          emptyText: 'No data found',
          columns: [{
            name: 'type',
            label: gettext('Type'),
            // Extend it to render the icon as per the type.
            cell: Backgrid.Cell.extend({
              render: function() {
                Backgrid.Cell.prototype.render.apply(this, arguments);
                this.$el.prepend($('<i>', {
                  class: 'wcTabIcon ' + this.model.get('icon'),
                }));
                return this;
              },
            }),
            editable: false,
          },
          {
            name: 'name',
            label: gettext('Name'),
            cell: 'string',
            editable: false,
          },
          {
            name: 'field',
            label: '', // label kept blank, it will change dynamically
            cell: 'string',
            editable: false,
          },
          ],

          collection: this.profilingCollection,
          className: 'backgrid table presentation table-bordered table-noouter-border table-hover',
        });

      // Condition is used to save grid object to change the label of the header.
      this.profilingGrid = grid;

      $gridContainer.append(grid.render().el);

      return true;
    },

    // Fetch the actual data and update the collection
    showProfiling: function(item, data, node) {
      var self = this;
      if (!node) {
        return;
      }
      /**
       * We can't start fetching the profiling immediately, it is possible -
       * the user is just using keyboards to select the node, and just
       * traversing through.
       *
       * We will wait for some time before fetching the profiling for the
       * selected node.
       **/
      if (node) {
        if (self.timeout) {
          clearTimeout(self.timeout);
        }
        self.timeout = setTimeout(
          function() {
            self.__updateCollection.call(
              self, node.generate_url(item, 'profiling', data, true), node, item, data._type
            );
          }, 400);
      }
    },

    __collectProfilingData: function(node, item) {
      var i = item,
        server = null,
        table = null,
        col = null,
        hasProfiling = false,
        tableName = null,
        colName = null;

      if(_.isFunction(node.hasProfiling)) {
        const treeHierarchy = node.getTreeNodeHierarchy(item);
        return node.hasProfiling(treeHierarchy);
      }

      while(i) {
        var n = pgBrowser.tree.itemData(i);
        if (n._type == 'table') {
          table = n;
        }
        if (n._type == 'column') {
          col = n;
        }
        if (n._type == 'server') {
          server = n;
          break;
        }

        if (pgBrowser.tree.hasParent(i)) {
          i = $(pgBrowser.tree.parent(i));
        } else {
          break;
        }
      }

      hasProfiling = node.hasProfiling && server && server.server_type == 'dbx';
      tableName = table && table._label;
      colName = col && col._label;

      return { 'has_profiling': hasProfiling,
        'table_name': tableName,
        'col_name': colName };
    },

    // Fetch the actual data and update the collection
    __updateCollection: function(url, node, item, node_type) {
      var $container = this.profilingPanel.layout().scene().find('.pg-panel-content'),
        $msgContainer = $container.find('.pg-panel-profiling-message'),
        $gridContainer = $container.find('.pg-panel-profiling-container'),
        panel = this.profilingPanel,
        self = this,
        msg = gettext('Please select an object in the tree view.'),
        n_type = node_type;

      if (node) {
        msg = gettext('No profiling are available for the selected object.');
        /* We fetch the profiling only for those node who set the parameter
         * showProfiling function.
         */

        // Avoid unnecessary reloads
        var treeHierarchy = node.getTreeNodeHierarchy(item);
        var cache_flag = {
          node_type: node_type,
          url: url,
        };
        if (_.isEqual($(panel[0]).data('node-prof'), cache_flag)) {
          return;
        }
        // Cache the current IDs for next time
        $(panel[0]).data('node-prof', cache_flag);

        var post_data = this.__collectProfilingData(node, item);

        if (post_data && post_data['has_profiling']) {

          // Hide message container and show grid container.
          $msgContainer.addClass('d-none');
          $gridContainer.removeClass('d-none');

          var timer = '';
          // Set the url, fetch the data and update the collection
          var ajaxHook = function() {
            $.ajax({
              url: url,
              type: 'POST',
              data: post_data,
              beforeSend: function(xhr) {
                xhr.setRequestHeader(
                  pgAdmin.csrf_token_header, pgAdmin.csrf_token
                );
                // Generate a timer for the request
                timer = setTimeout(function() {
                  // notify user if request is taking longer than 1 second

                  $msgContainer.text(gettext('Fetching profiling information from the server...'));
                  $msgContainer.removeClass('d-none');
                  msg = '';
                }, 1000);
              },
            })
              .done(function(res) {
              // clear timer and reset message.
                clearTimeout(timer);
                $msgContainer.text('');
                if (res.data) {
                  var data = self.profilingData = res.data;
                  if (data['rows'].length > 1) {
                    // Listen scroll event to load more rows
                    pgBrowser.Events.on(
                      'pgadmin-browser:panel-profiling:' +
                    wcDocker.EVENT.SCROLLED,
                      self.__loadMoreRows
                    );
                    self.__createMultiLineProfiling.call(self, data, node.profilingPrettifyFields);
                  } else {
                    // Do not listen the scroll event
                    pgBrowser.Events.off(
                      'pgadmin-browser:panel-profiling:' +
                    wcDocker.EVENT.SCROLLED,
                      self.__loadMoreRows
                    );
                    self.__createSingleLineProfiling.call(self, data, node.profilingPrettifyFields);
                  }

                  if (self.grid) {
                    delete self.grid;
                    self.grid = null;
                  }

                  self.grid = new Backgrid.Grid({
                    emptyText: 'No data found',
                    columns: self.columns,
                    collection: self.collection,
                    className: GRID_CLASSES,
                  });
                  self.grid.render();
                  $gridContainer.empty();
                  $gridContainer.append(self.grid.$el);

                  if (!$msgContainer.hasClass('d-none')) {
                    $msgContainer.addClass('d-none');
                  }
                  $gridContainer.removeClass('d-none');

                } else if (res.info) {
                  if (!$gridContainer.hasClass('d-none')) {
                    $gridContainer.addClass('d-none');
                  }
                  $msgContainer.text(res.info);
                  $msgContainer.removeClass('d-none');
                }
              })
              .fail(function(xhr, error, message) {
                var _label = treeHierarchy[n_type].label;
                pgBrowser.Events.trigger(
                  'pgadmin:node:retrieval:error', 'profiling', xhr, error, message, item
                );
                if (!Alertify.pgHandleItemError(xhr, error, message, {
                  item: item,
                  info: treeHierarchy,
                })) {
                  Alertify.pgNotifier(
                    error, xhr,
                    gettext('Error retrieving the information - %s', message || _label),
                    function(msg) {
                      if(msg === 'CRYPTKEY_SET') {
                        ajaxHook();
                      } else {
                        console.warn(arguments);
                      }
                    }
                  );
                }
                // show failed message.
                $msgContainer.text(gettext('Failed to retrieve data from the server.'));
              });
          };

          ajaxHook();
        }
      }
      if (msg != '') {
        // Hide the grid container and show the default message container
        $msgContainer.text(msg);
        $msgContainer.removeClass('d-none');
        if (!$gridContainer.hasClass('d-none')) {
          $gridContainer.addClass('d-none');
        }
      }
    },

    __createMultiLineProfiling: function(data, prettifyFields) {
      var rows = data['rows'],
        columns = data['columns'];

      this.columns = [];
      for (var idx in columns) {
        var rawColumn = columns[idx],
          cell_type = typeCellMapper[rawColumn['type_code']] || 'string';

        // Don't show PID comma separated
        if (rawColumn['name'] == 'PID') {
          cell_type = cell_type.extend({
            orderSeparator: '',
          });
        }

        var col = {
          editable: false,
          name: rawColumn['name'],
          cell: cell_type,
        };
        if (_.indexOf(prettifyFields, rawColumn['name']) != -1) {
          col['formatter'] = SizeFormatter;
        }
        this.columns.push(col);

      }

      this.collection.reset(rows.splice(0, 50));
    },

    __createSingleLineProfiling: function(data, prettifyFields) {
      var row = data['rows'][0],
        columns = data['columns'],
        res = [],
        name;

      this.columns = this.profiling_columns;
      for (var idx in columns) {
        name = (columns[idx])['name'];
        res.push({
          'profiling': name,
          // Check if row is undefined?
          'value': row && row[name] ?
            ((_.indexOf(prettifyFields, name) != -1) ?
              sizePrettify(row[name]) : row[name]) : null,
        });
      }

      this.collection.reset(res);
    },

    __loadMoreRows: function() {
      if (this.profilingPanel.length < 1) return ;

      let elem = this.profilingPanel.$container.find('.pg-panel-profiling-container').closest('.wcFrameCenter')[0];
      if ((elem.scrollHeight - 10) < elem.scrollTop + elem.offsetHeight) {
        if (this.profilingData.length > 0) {
          this.profilingCollection.add(this.profilingData.splice(0, 100), {parse: true});
        }
      }
    },
  });

  return pgBrowser.NodeProfiling;
});
