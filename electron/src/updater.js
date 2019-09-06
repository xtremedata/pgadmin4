const { dialog, app } = require('electron');
/* In dev mode, prebuilt electron is used. So getVersion
 * returns version of electron and not the actual app
 */

if(process.env.ENV === 'dev') {
  const version = require('../package.json').version;
  app.getVersion = ()=> version;
}

const {autoUpdater} = require('electron-updater');

var updater = null, logger = console;
autoUpdater.autoDownload = false;

autoUpdater.on('error', (error) => {
  logger.error('Error: ' + (error == null ? 'unknown' : (error.stack || error).toString()));
  dialog.showErrorBox('Error: ', error == null ? 'unknown' : (error.stack || error).toString());
});

autoUpdater.on('update-available', () => {
  logger.debug('Update available...');
  dialog.showMessageBox({
    type: 'info',
    title: 'Found Updates',
    message: 'Found updates, do you want update now?',
    buttons: ['Sure', 'No'],
  }, (buttonIndex) => {
    if (buttonIndex === 0) {
      logger.debug('Downloading update...');
      autoUpdater.downloadUpdate();
    }
    else {
      updater.enabled = true;
      updater = null;
    }
  });
});

autoUpdater.on('update-not-available', (event) => {
  logger.debug(`Update not available - ${event.url}`);
  dialog.showMessageBox({
    title: 'No Updates',
    message: 'Current version is up-to-date.',
  });
  updater.enabled = true;
  updater = null;
});

autoUpdater.on('update-downloaded', () => {
  logger.debug('Update download complete...');
  dialog.showMessageBox({
    title: 'Install Updates',
    message: 'Updates downloaded, application will be quit for update...',
  }, () => {
    logger.debug('Installing update...');
    setImmediate(() => autoUpdater.quitAndInstall());
  });
});

autoUpdater.on('checking-for-update', (event) => {
  logger.debug('Checking for update', event);
});

function checkForUpdates(menuItem) {
  updater = menuItem;
  updater.enabled = false;
  logger.debug('Checking for updates...');
  autoUpdater.checkForUpdates();
}

module.exports = function(_logger) {
  if(_logger) {
    logger = _logger;
  }
  return checkForUpdates;
};