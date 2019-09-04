
const {ipcEventRenderer} = require('./ipc_event');

window.get_event_handle = function() {
  return ipcEventRenderer;
};

window.require_package = function(pack_name) {
  const ALLOWED_PAKCS = ['jquery', 'bootstrap', './constants'];
  if(ALLOWED_PAKCS.indexOf(pack_name) < 0) {
    return undefined;
  }
  return require(pack_name);
};