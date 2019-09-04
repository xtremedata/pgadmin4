const {ipcMain, ipcRenderer} = require('electron');

function send(ipc, event, args) {
  ipc.send(event, args);
}

function on(ipc, event, callback) {
  ipc.on(event, callback);
}

function off(ipc, event, callback) {
  if(callback === undefined || callback === null) {
    ipc.removeAllListeners(event);
  } else {
    ipc.removeListener(event, callback);
  }
}

module.exports = {
  ipcEventRenderer: {
    send: send.bind(null, ipcRenderer),
    on: on.bind(null, ipcRenderer),
    off: off.bind(null, ipcRenderer),
  },

  ipcEventMain: {
    send: send.bind(null, ipcMain),
    on: on.bind(null, ipcMain),
    off: off.bind(null, ipcMain),
  },
};