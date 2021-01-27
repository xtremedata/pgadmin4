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
  'sources/url_for',
  'apexcharts',
], function(gettext, _, $, Backbone,
  pgAdmin, pgBrowser, Alertify, Backgrid,
  pgadminUtils,
  sizePrettify,
  url_for,
  ApexCharts) {

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
      _.bindAll(this, 
        'showProfiling',
        '__initProfilingPanel',
        '__loadMoreRows');

      _.extend(
        this, {
          initialized: true,
          collections: {},
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
          columns: {},
          grids: {},
          chart: null,
        });

      // Defining Backbone Model for Profiling.
      this.model = Backbone.Model.extend({
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

      pgBrowser.Events.on('pgadmin-browser:tree:selected', this.showProfiling);
      pgBrowser.Events.on('pgadmin-browser:tree:refreshing', this.refreshProfiling, this);
      this.__initProfilingPanel();
    },

    /**
     * Creates histogram.
     */
    __createHistogram: function(subtitle) {
      var chart = null,
        options = {
          animationEnabled: true,

          title: {
            text: 'Profiling top N histogram',
          },
          subtitle: {
            text: subtitle,
          },
          chart: {
            id: 'profileChart',
            type: 'bar',
            height: '400',
            width: '100%',
            animations: {
              enabled: true,
            },
          },
          plotOptions: {
            bar: {
              horizontal: true,
              dataLabels: {
                position: 'top',
              },
            },
          },
          dataLabels: {
            enabled: true,
            offsetX: -6,
            style: {
              fontSize: '12px',
              colors: ['#fff'],
            },
          },
          stroke: {
            show: true,
            width: 1,
            colors: ['#fff'],
          },          

          xaxis: {
            title: {
              text: 'Frequency',
            },
            type: 'category',
          },
          yaxis: {
            title: {
              text: 'Top N Values',
            },
          },

          legend: {
            position: 'top',
            horizontalAlign: 'left',
            offsetX: 40,
          },

          series: [],
        };

      chart = new ApexCharts(document.querySelector('#histochart_canvas'), options);
      return chart;
    },

    /**
     * Initializes Profiling panel based on server template.
     * Profiling contains pills panel presenting various metrics for profiling.
     */
    __initProfilingPanel: function() {

      if (this.profilingPanel) {
        var $container = this.profilingPanel.layout().scene().find('.pg-panel-content'),
          $msgContainer = $container.find('.pg-panel-profiling-message'),
          $dataContainer = $container.find('.pg-panel-profiling-container'),
          msg = gettext('Please select an object in the tree view.'),
          url = url_for('profiling.index');

        // Hide message container and show grid container.
        $msgContainer.removeClass('d-none');
        $dataContainer.addClass('d-none');

        if ($container) {
          var ajaxHook = function() {
            $.ajax({
              url: url,
              type: 'GET',
              dataType: 'html',
            })
              .done(function(data) {
                $dataContainer.html(data);
              })
              .fail(function(xhr, error) {
                Alertify.pgNotifier(
                  error, xhr,
                  gettext('An error occurred whilst loading the profiling template.'),
                  function(msg) {
                    if(msg === 'CRYPTKEY_SET') {
                      ajaxHook();
                    } else {
                      console.warn(arguments);
                    }
                  }
                );
                // show failed message.
                $msgContainer.text(gettext('Failed to retrieve profiling template from the server.'));
              });
          };
          $msgContainer.text(gettext('Fetching profiling template from the server...'));
          ajaxHook();
        }

        $msgContainer.text(msg);
      }
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

    /**
     * Helper function for histogram chart.
     */
    __toolTipFormatter: function(e) {
      var str = '';
      var total = 0 ;
      var str3;
      var str2 ;
      for (var i = 0; i < e.entries.length; i++){
        var str1 = '<span style= \'color:'+e.entries[i].dataSeries.color 
          + '\'>' + e.entries[i].dataSeries.name + '</span>: <strong>' 
          +  e.entries[i].dataPoint.y + '</strong> <br/>' ;
        total = e.entries[i].dataPoint.y + total;
        str = str.concat(str1);
      }
      str2 = '<strong>' + e.entries[0].dataPoint.label + '</strong> <br/>';
      str3 = '<span style = \'color:Tomato\'>Total: </span><strong>' + total + '</strong><br/>';
      return (str2.concat(str)).concat(str3);
    },

    /**
     * Helper function for histogram chart.
     */
    __toggleDataSeries: function(e) {
      e.dataSeries.visible = (typeof (e.dataSeries.visible) !== 'undefined' && !e.dataSeries.visible);
      e.chart.render();
    },

    /**
     * Creates histogram data points for a column.
     */
    __createColumnHisto: function(column, values) {
      var data_points = {
        name: column,
        color: '#014D65',
        data: [
        ],
      };

      values.sort(function(a, b){return a.x > b.x;}); 
      data_points.data = values;

      return data_points;
    },

    /**
     * Updates histogram.
     */
    __updateHistogram: function(data, table, column) {
      var title = null,
        new_series = [],
        cols = null,
        rows = null;

      if (Object.keys(data).length > 1) {
        var col_dict = {},
          col_name = null,
          col_val = null,
          col_freq = null,
          key = null,
          row = null;

        cols = data.columns;
        rows = data.rows;

        title = (table !== null ? (table + ' table') : '')
          + (column !== null ? (', ' + column + ' column') : '');

        if (column == null) {
          col_name = cols[0].name;
          col_val = cols[1].name;
          col_freq = cols[2].name;
          for (key in rows) {
            row = rows[key];
            if (!(row[col_name] in col_dict)) {
              col_dict[row[col_name]] = [];
            }
            col_dict[row[col_name]].push({'x': row[col_val], 'y': parseInt(row[col_freq])});
          }
        } else {
          col_name = column;
          col_val = cols[0].name;
          col_freq = cols[1].name;
          var values = [];
          for (key in rows) {
            row = rows[key];
            values.push({'x': row[col_val], 'y': parseInt(row[col_freq])});
          }
          col_dict[col_name] = values;
        }

        for (var col in col_dict) {
          new_series.push(this.__createColumnHisto(col, col_dict[col]));
        }
      }

      // when jquery.canvasjs.min instead of canvasjs.min
      //$('#histochart_canvas').CanvasJSChart(options);
      if (this.chart != null) {
        this.chart.destroy();
      }

      this.chart = this.__createHistogram(title);
      this.chart.render();

      this.chart.updateOptions({
        subtitle: {
          text: title,
        },
      });

      this.chart.updateSeries(new_series, true);
    },

    // Copies db data
    __copyData: function(src, dst) {
      dst = _.clone(src);
      for (var key in src) {
        dst[key] = _.extend(true, {}, src[key]);
      }
    },

    // Process single tab data
    __processSingleData: function(node, data, key) {
      var self = this;
      if (data[key]['rows'].length > 1) {
        // Listen scroll event to load more rows
        pgBrowser.Events.on(
          'pgadmin-browser:panel-profiling:' +
        wcDocker.EVENT.SCROLLED,
          self.__loadMoreRows
        );
        self.__createMultiLineProfiling.call(self, data, key, node.profilingPrettifyFields);
      } else {
        // Do not listen the scroll event
        pgBrowser.Events.off(
          'pgadmin-browser:panel-profiling:' +
        wcDocker.EVENT.SCROLLED
        );
        self.__createSingleLineProfiling(data, key, node.profilingPrettifyFields);
      }
    },

    // Process multiple tabs data
    __processMultipleData: function($dataContainer, $msgContainer, node, data, post_data) {
      var self = this,
        gridContainers = {};
      var table = '',
        column = null;
      var histo_data = null;

      table = post_data.table_name;
      column = post_data.col_name;

      // self.__copyData.call(self, data.topn, histo_data);
      histo_data = JSON.parse(JSON.stringify(data.topn));

      for (var key in data) {
        self.collections[key] = new(Backbone.Collection)(null),
        self.__processSingleData(node, data, key);
        gridContainers[key] = $dataContainer.find('#' + key +'_grid');
        self.grids[key] = new Backgrid.Grid({
          emptyText: 'No data found',
          columns: self.columns[key],
          collection: self.collections[key],
          className: GRID_CLASSES,
          scrollX: true,
          scrollY: 200,
          scrollCollapse: true,
        });
        self.grids[key].render();
        if (gridContainers[key]) {
          gridContainers[key].empty();
          gridContainers[key].append(self.grids[key].$el);
        }
      }

      self.__updateHistogram(histo_data, table, column);

      if (!$msgContainer.hasClass('d-none')) {
        $msgContainer.addClass('d-none');
      }
      $dataContainer.removeClass('d-none');
    },

    // Fetch the actual data and update the collection
    __updateCollection: function(url, node, item, node_type) {
      var $container = this.profilingPanel.layout().scene().find('.pg-panel-content'),
        $msgContainer = $container.find('.pg-panel-profiling-message'),
        $dataContainer = $container.find('.pg-panel-profiling-container'),
        panel = this.profilingPanel,
        self = this,
        node_types = ['table', 'column'],
        msg = gettext('Please select an object in the tree view.'),
        n_type = node_type;

      if (node) {
        msg = gettext('No profiling are available for the selected object.');
        /* We fetch the profiling only for those nodes which set the parameter
         * showProfiling function.
         */

        // Avoid unncessary action for not Profiling node
        if (node_types.includes(node_type)) {

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
            $dataContainer.removeClass('d-none');

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
                  }, 1000);
                },
              })
                .done(function(res) {
                  // clear timer and reset message.
                  clearTimeout(timer);
                  $msgContainer.text('');
                  if (res == null) {
                    if (!$dataContainer.hasClass('d-none')) {
                      $dataContainer.addClass('d-none');
                    }
                    $msgContainer.text(msg);
                    $msgContainer.removeClass('d-none');
                  } else if (res.info) {
                    if (!$dataContainer.hasClass('d-none')) {
                      $dataContainer.addClass('d-none');
                    }
                    $msgContainer.text(res.info);
                    $msgContainer.removeClass('d-none');
                  } else if (res.data) {
                    var data = self.profilingData = res.data;

                    if (self.grids && Object.keys(self.grids).length) {
                      delete self.grids;
                      self.grids = {};
                    }

                    self.__processMultipleData($dataContainer, $msgContainer, node, data, post_data);
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
      }
      if (msg != '') {
        // Hide the grid container and show the default message container
        $msgContainer.text(msg);
        $msgContainer.removeClass('d-none');
        if (!$dataContainer.hasClass('d-none')) {
          $dataContainer.addClass('d-none');
        }
      }
    },

    __createMultiLineProfiling: function(data, key, prettifyFields) {
      var rows = data[key]['rows'],
        columns = data[key]['columns'];

      this.columns[key] = [];
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
        this.columns[key].push(col);

      }

      this.collections[key].reset(rows.splice(0, 50));
    },

    __createSingleLineProfiling: function(data, key, prettifyFields) {
      var row = data[key]['rows'][0],
        columns = data[key]['columns'],
        res = [],
        name;

      this.columns[key] = this.profiling_columns;
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

      this.collections[key].reset(res);
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
