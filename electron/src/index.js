const electron = require('electron');
const { globalShortcut, dialog } = require('electron');
const crypto = require('crypto');
const net = require('net');

const app = electron.app;
const BrowserWindow = electron.BrowserWindow;
const path = require('path');
const waitForPythonServerToBeAvailable = require('./check_python_server');
const childProcess = require('child_process');
const { electronLogger, pythonAppLogger } = require('./logger');
var {ConfigureStore} = require('./configure_store');
ConfigureStore.init();

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

  newWindow.on('closed', () => {
    electronLogger.debug(`window: ${urlToLoad} just closed`);
    newWindow = null;
    delete allWindows[windowId];
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

  // Create the Application's main menu
  const template = [{
    label: 'pgAdmin',
    submenu: [
      {
        label: 'New window',
        accelerator: 'CommandOrControl+N',
        selector: 'newwindow:',
        click: () => {
          createNewWindow(pythonApplicationUrl);
        },
      }, {
        label: 'New tab',
        accelerator: 'CommandOrControl+t',
        selector: 'newtab:',
        click: () => {
          activeWindow.webContents.send(
            'tabs-channel',
            'create',
            'pgAdmin4',
            pythonApplicationUrl,
          );
        },
      },
      { type: 'separator' },
      {
        label: 'Configure',
        click() {
          handleConfigureClick();
        },
      },
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
    ],
  },{
    label: "Edit",
    submenu: [
      { label: "Undo", accelerator: "CmdOrCtrl+Z", selector: "undo:" },
      { label: "Redo", accelerator: "Shift+CmdOrCtrl+Z", selector: "redo:" },
      { type: "separator" },
      { label: "Cut", accelerator: "CmdOrCtrl+X", selector: "cut:" },
      { label: "Copy", accelerator: "CmdOrCtrl+C", selector: "copy:" },
      { label: "Paste", accelerator: "CmdOrCtrl+V", selector: "paste:" },
      { label: "Select All", accelerator: "CmdOrCtrl+A", selector: "selectAll:" }
  ]}];

  if (process.platform === 'darwin') {
    template.unshift({
      label: app.getName(),
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services', submenu: [] },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideothers' },
        { role: 'unhide' },
        { type: 'separator' },
        {
          label: 'Dev Tools',
          accelerator: 'CmdOrCtrl+Alt+I',
            click: () => {
              if (activeWindow !== null) {
                activeWindow.webContents.openDevTools();
              }
            },
          },
        { role: 'quit' },
      ],
    });
  }

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
  });

  configureWindow.on('focus', () => {
    activeWindow = configureWindow;
  });

  electronLogger.debug(`Settings - file://${__dirname}/configure_ui.html`);

  configureWindow.loadURL(`file://${__dirname}/configure_ui.html`);

  configureWindow.webContents.once('dom-ready', () => {
    configureWindow.show();
  });
}

function loadingWindowClose() {
  try {
    loadingWindow.hide();
    loadingWindow.close();
  } catch (exp) {
    electronLogger.error(`failed to close loading window ${exp}`);
  }
}

function showMessageBox(message, title="", type="info") {
  const messageBoxOptions = {
    type: type,
    title: title,
    message: message
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

      server.on('listening', function (e) {
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
  app.quit();
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
  let useServerMode = false;
  let sourceFolder = '..';

  if (process.env.ENV === 'DEV' || process.env.ENV === 'TEST') {
    sourceFolder = path.join('..', '..');
    useServerMode = true;
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
    ConfigureStore.get('app_path', path.join(__dirname, sourceFolder, 'web')), 
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
      env.SERVER_MODE = useServerMode;

      setLoadingText('Starting python server...');
      electronLogger.debug('pythonPath:' + pythonPath);
      electronLogger.debug('appPath:' + appPath);

      pyProc = childProcess.spawn(pythonPath, [appPath], { env });

      pyProc.on('exit', pyProcExitHandler);

      pyProc.on('error', (error) => {
        pythonAppLogger.error('PYTHON: ERROR: ', error);
        pyProcExitHandler();
      });

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
    })
    .catch((err) => {
      loadingWindowClose();
      showMessageBox(
        `Unable to get port. Port error: ${err}`,
        'Failed to start', 'error'
      );
      app.quit();
    });
}

app.on('ready', createPyProc);

app.on('ready', () => {
  if (process.env.ENV === 'DEV') {
    session.defaultSession.clearCache(() => {
    });
  }

  loadingWindow = new BrowserWindow({
    show: false,
    frame: false,
    width: 440,
    height: 170,
    resizable: false,
    icon: `${__dirname}assets/icons/pgAdmin4.png`,
  });

  const template = [];

  if (process.platform === 'darwin') {
    template.unshift({
      label: app.getName(),
    });
  }

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));

  electronLogger.debug(`Loader - file://${__dirname}/loader.html`);

  loadingWindow.loadURL(`file://${__dirname}/loader.html`);

  loadingWindow.webContents.once('dom-ready', () => {
    loadingWindow.show();
    setLoadingText('pgAdmin4 loading...');
  });
});

app.on('window-all-closed', () => {
  electronLogger.debug('perhaps going to close windows');
  globalShortcut.unregisterAll();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null && !loadingWindow.isVisible()) {
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
