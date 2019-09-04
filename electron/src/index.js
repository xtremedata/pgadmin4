const electron = require('electron');
const { globalShortcut, dialog } = require('electron');
const crypto = require('crypto');
const net = require('net');

const app = electron.app;
const BrowserWindow = electron.BrowserWindow;
const path = require('path');
const waitForPythonServerToBeAvailable = require('./check_python_server');
const childProcess = require('child_process');
const { createLogger } = require('./logger');
const { EVENTS, CONFIG_FILENAME } = require('./constants');
const {ipcEventMain} = require('./ipc_event');

const APP_DATA_DIR = path.join(app.getPath('appData'),app.getName());

const electronLogger = createLogger(path.join(APP_DATA_DIR, 'electron.log'),'electron');
const pythonAppLogger = createLogger(path.join(APP_DATA_DIR, 'pgAdmin.log'),'python');

var {ConfigureStore} = require('./configure_store');

var ipcEvent = ipcEventMain;

/* to be changed with configuration */
var pythonApplicationUrl;

const secret = crypto.randomBytes(12).toString('hex');
const session = electron.session;
const Menu = electron.Menu;

const allWindows = {};

let pyProc = null;
let activeWindow = null;
let loadingWindow = null;
let manualPyProcExit = false;

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (require('electron-squirrel-startup')) { // eslint-disable-line global-require
  app.quit();
}

/*************************************************************
 * window management
 ************************************************************ */

let mainWindow = null;

function createNewWindow(url) {
  const windowId = Math.random()
    .toString();
  const webPreferences = {
    nativeWindowOpen: true,

  };

  let newWindow = new BrowserWindow({
    width: 1024,
    height: 768,
    icon: path.join(__dirname, 'assets/icons/mac/logo-256.png.icns'),
    webPreferences,
    show: false,
  });

  let urlToLoad = `file://${__dirname}/index.html`;

  if (url !== undefined && url !== null) {
    urlToLoad = url;
  }
  newWindow.loadURL(urlToLoad);

  newWindow.on('close', (e) => {
    e.preventDefault();
    newWindow.destroy();
  });

  newWindow.on('closed', () => {
    electronLogger.debug(`window: ${urlToLoad} just closed`);
    newWindow = null;
    delete allWindows[windowId];

    if(Object.keys(allWindows).length <= 0) {
      app.quit();
    }
  });

  newWindow.on('focus', () => {
    activeWindow = newWindow;
  });

  newWindow.webContents.once('dom-ready', () => {
    newWindow.show();
    loadingWindowClose();
  });

  activeWindow = newWindow;

  allWindows[windowId] = newWindow;

  return newWindow;
}

function createMainWindow() {
  setLoadingText('Loading the home page...');
  mainWindow = createNewWindow(pythonApplicationUrl);
  mainWindow.maximize();

  let appSubmenu = [
    {
      label: 'New window',
      accelerator: 'CommandOrControl+N',
      selector: 'newwindow:',
      click: () => {
        createNewWindow(pythonApplicationUrl);
      },
    },
    {
      label: 'Open windows',
      role: 'window',
      submenu: [{
        role: 'minimize',
      },{
        role: 'close',
      }],
    },
    { type: 'separator' },
    {
      label: 'Configure',
      click() {
        handleConfigureClick();
      },
    },
    {
      label: 'Diagnose',
      click: () => {
        if (activeWindow !== null) {
          if(activeWindow.webContents.isDevToolsOpened()) {
            activeWindow.webContents.closeDevTools();
          } else {
            activeWindow.webContents.openDevTools({
              mode: 'bottom',
            });
          }
        }
      },
    },
    {
      label: 'Hard reload',
      click: () => {
        if (activeWindow !== null) {
          activeWindow.webContents.reloadIgnoringCache();
        }
      },
    },
  ];

  if (process.platform === 'darwin') {
    appSubmenu.push(...[
      { type: 'separator' },
      { role: 'services', submenu: [] },
      { type: 'separator' },
      { role: 'hide' },
      { role: 'hideothers' },
      { role: 'unhide' },
    ]);
  }

  appSubmenu.push(...[
    { type: 'separator' },
    {
      label: 'About pgAdmin',
      selector: 'orderFrontStandardAboutPanel:',
    },
    { type: 'separator' },
    {
      label: 'Quit',
      accelerator: 'Command+Q',
      click() {
        app.quit();
      },
    },
  ]);

  // Create the Application's main menu
  const template = [{
    label: app.getName(),
    submenu: appSubmenu,
  },{
    label: 'Edit',
    submenu: [
      { label: 'Undo', accelerator: 'CmdOrCtrl+Z', selector: 'undo:' },
      { label: 'Redo', accelerator: 'Shift+CmdOrCtrl+Z', selector: 'redo:' },
      { type: 'separator' },
      { label: 'Cut', accelerator: 'CmdOrCtrl+X', selector: 'cut:' },
      { label: 'Copy', accelerator: 'CmdOrCtrl+C', selector: 'copy:' },
      { label: 'Paste', accelerator: 'CmdOrCtrl+V', selector: 'paste:' },
      { label: 'Select All', accelerator: 'CmdOrCtrl+A', selector: 'selectAll:' },
    ]},
  ];


  Menu.setApplicationMenu(Menu.buildFromTemplate(template));

  globalShortcut.register('CommandOrControl+N', () => {
    electronLogger.debug('CommandOrControl+N is pressed');
    createNewWindow(`http://${pythonApplicationUrl}`);
  });
}

function setLoadingText(text) {
  if(loadingWindow) {
    loadingWindow.webContents.executeJavaScript(`setText('${text}');`);
  }
}

function handleConfigureClick() {
  let configureWindow = new BrowserWindow({
    parent: mainWindow,
    show: false,
    width: 800,
    height: 600,
    title: 'Configure',
    resizable: false,
    minimizable: false,
    maximizable: false,    
    webPreferences: {
      preload: path.resolve(__dirname, 'configure_preload.js'),
    },
  });
  let confiUIPath = `file://${__dirname}/configure_ui.html`;
  let eventHandlers = {};

  eventHandlers[EVENTS.LOAD_CONFIG] = () => {
    electronLogger.debug(`Received ${EVENTS.LOAD_CONFIG}`);
    configureWindow.webContents.send(EVENTS.LOAD_CONFIG, ConfigureStore.get_data_json());
  };
  eventHandlers[EVENTS.SAVE_CONFIG] = (event, data) => {
    electronLogger.debug(`Received ${EVENTS.SAVE_CONFIG}`);
    ConfigureStore.set(data);
    ConfigureStore.save();
    configureWindow.webContents.send(EVENTS.SAVE_DATA_SUCCESS);
  };

  configureWindow.on('focus', () => {
    activeWindow = configureWindow;
  });

  configureWindow.webContents.once('dom-ready', () => {
    configureWindow.show();
  });

  configureWindow.on('close', () => {
    Object.keys(eventHandlers).forEach((event)=>{
      ipcEvent.off(event, eventHandlers[event]);  
    });
  });

  /* Bind events */
  Object.keys(eventHandlers).forEach((event)=>{
    ipcEvent.on(event, eventHandlers[event]);  
  });
  
  electronLogger.debug(`Settings - ${confiUIPath}`);  
  configureWindow.loadURL(confiUIPath);
}

function loadingWindowClose() {
  try {
    loadingWindow.hide();
    loadingWindow.close();
  } catch (exp) {
    electronLogger.error(`failed to close loading window ${exp}`);
  }
}

function showMessageBox(message, title='', type='info') {
  const messageBoxOptions = {
    type: type,
    title: title,
    message: message,
  };
  dialog.showMessageBox(messageBoxOptions);
}

function getAvailablePort(host) {
  return new Promise(function(resolve, reject) {
    if(ConfigureStore.get('fixed_port')) {
      resolve(ConfigureStore.get('port_no'));
    } else {
      const server = net.createServer();

      server.on('error', (e) => {
        if (e.code != 'EADDRINUSE') {
          reject(e.code);
        }
      });

      server.on('listening', function () {
        const {port} = server.address();
        server.close(() => {
          resolve(port);
        });
      });

      for(let p=5555; p<=65535; p++) {
        server.listen(p, host);
      }
    }
  });
}

function pyProcExitHandler() {
  if(manualPyProcExit) {
    return;
  }
  loadingWindowClose();
  showMessageBox(
    'Unable to start python process. Please check logs for errors.',
    'Failed to start', 'error'
  );
}

function exitPyProc() {
  electronLogger.debug('Going to exit');
  manualPyProcExit = true;

  if (pyProc != null) {
    pyProc.kill();
    pyProc = null;
  } else {
    app.exit();
  }
}

function createPyProc() {
  let sourceFolder = '..';

  if (process.env.ENV === 'dev') {
    sourceFolder = path.join('..', '..');
  }
  let pythonPath = '', appPath = '';

  if (process.platform === 'win32') {
    pythonPath = path.join(
      ConfigureStore.get('python_path', path.join(__dirname, sourceFolder, 'venv')),
      'python.exe'
    );
  } else {
    pythonPath = path.join(
      ConfigureStore.get('python_path', path.join(__dirname, sourceFolder, 'venv', 'bin')),
      'python'
    );
  }

  appPath = path.join(
    ConfigureStore.get('app_path', path.join(__dirname, sourceFolder)),
    'web',
    'pgAdmin4.py'
  );

  let hostAddr = '127.0.0.1';
  getAvailablePort('127.0.0.1')
    .then((pythonApplicationPort) => {
      pythonApplicationUrl = `http://${hostAddr}:${pythonApplicationPort}?key=${secret}`;
      electronLogger.info('info: Spawning...');
      const env = Object.create(process.env);
      env.PGADMIN_PORT = pythonApplicationPort;
      env.PGADMIN_KEY = secret;

      setLoadingText('Starting python server...');
      electronLogger.debug('pythonPath:' + pythonPath);
      electronLogger.debug('appPath:' + appPath);

      pyProc = childProcess.spawn(pythonPath, [appPath], { env });
      pyProc.on('error', (error) => {
        pythonAppLogger.error('PYTHON: ERROR: ', error);
        pyProcExitHandler();
      });

      electronLogger.debug('Python proc pid :' + pyProc.pid);

      if(pyProc.pid != undefined) {
        pyProc.on('exit', pyProcExitHandler);
        pyProc.on('close', pyProcExitHandler);

        pyProc.stdout.on('data', (data) => {
          pythonAppLogger.info(`PYTHON: ${data}`);
        });

        pyProc.stderr.on('data', (data) => {
          pythonAppLogger.info(`PYTHON: ${data}`);
        });

        waitForPythonServerToBeAvailable.waitForPythonServerToBeAvailable(pythonApplicationUrl, () => {
          electronLogger.debug('debug: Python server is Up, going to start the pgAdmin window');
          createMainWindow();
          electronLogger.debug('debug: closing the loading window');
        });
      }
    })
    .catch((err) => {
      showMessageBox(
        `Unable to get port. Port error: ${err}`,
        'Failed to start', 'error'
      );
      app.quit();
    });
}

app.on('ready', () => {
  if (process.env.ENV === 'DEV') {
    session.defaultSession.clearCache(() => {
    });
  }

  const template = [{
    label: 'pgAdmin',
    submenu: [
      {
        label: 'Configure',
        click() {
          handleConfigureClick();
        },
      },
      {
        label: 'Diagnose',
        click: () => {
          if (activeWindow !== null) {
            if(activeWindow.webContents.isDevToolsOpened()) {
              activeWindow.webContents.closeDevTools();
            } else {
              activeWindow.webContents.openDevTools({
                mode: 'bottom',
              });
            }
          }
        },
      },
      {
        label: 'About pgAdmin',
        selector: 'orderFrontStandardAboutPanel:',
      },
      { type: 'separator' },
      {
        label: 'Restart',
        click() {
          app.relaunch();
          app.quit();
        },
      },      
      {
        label: 'Quit',
        accelerator: 'Command+Q',
        click() {
          app.quit();
        },
      },
    ],
  },{
    label: 'Edit',
    submenu: [
      { label: 'Undo', accelerator: 'CmdOrCtrl+Z', selector: 'undo:' },
      { label: 'Redo', accelerator: 'Shift+CmdOrCtrl+Z', selector: 'redo:' },
      { type: 'separator' },
      { label: 'Cut', accelerator: 'CmdOrCtrl+X', selector: 'cut:' },
      { label: 'Copy', accelerator: 'CmdOrCtrl+C', selector: 'copy:' },
      { label: 'Paste', accelerator: 'CmdOrCtrl+V', selector: 'paste:' },
      { label: 'Select All', accelerator: 'CmdOrCtrl+A', selector: 'selectAll:' },
    ],
  }];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));

  try {
    ConfigureStore.init(path.join(APP_DATA_DIR, CONFIG_FILENAME));
    electronLogger.debug('Config file : ' + ConfigureStore.getConfigFilePath());
    electronLogger.debug('Python path in config : ' + ConfigureStore.get('python_path'));
  } catch (error) {
    showMessageBox(
      `Unable to load config file - ${error}`,
      'Failed to start', 'error'
    );
    app.quit();
  }

  loadingWindow = new BrowserWindow({
    show: false,
    frame: false,
    width: 440,
    height: 170,
    resizable: false,
    icon: `${__dirname}assets/icons/pgAdmin4.png`,
  });

  electronLogger.debug(`Loader - file://${__dirname}/loader.html`);

  loadingWindow.loadURL(`file://${__dirname}/loader.html`);

  loadingWindow.webContents.once('dom-ready', () => {
    loadingWindow.show();
    setLoadingText('pgAdmin4 loading...');
    createPyProc();
  });

  loadingWindow.on('closed', () => {
    loadingWindow = null;
  });
});

app.on('activate', () => {
  if (mainWindow === null && loadingWindow && !loadingWindow.isVisible()) {
    createMainWindow();
  }
});

app.on('before-quit', () => {
  electronLogger.debug('before-quit');
  exitPyProc();

  app.quit();
});

app.on('quit', () => {
  electronLogger.debug('quit');
});

app.on('window-all-closed', (e) => {
  e.preventDefault();
});
