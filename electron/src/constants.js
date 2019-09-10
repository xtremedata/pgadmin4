const app = require('electron').app;
const path = require('path');

var devConst;
try {
  devConst = require('./constants_dev');
}
catch(e) {
  devConst = {}
}


/* LOG LEVELS
  error: 0,
  warn: 1,
  info: 2,
  verbose: 3,
  debug: 4,
  silly: 5
*/
let osPF = process.platform;
let osName = {
  'darwin': 'macos',
  'win32': 'windows',
}[osPF];

var constants = {
  APP_DATA_DIR: path.join(app.getPath('appData'),app.getName()),
  CONFIG_FILENAME: 'configure-settings.json',
  UPGRADE_CHECK_URL: 'https://www.pgadmin.org/versions.json',
  UPGRADE_CHECK_KEY: 'pgadmin4',
  DOWNLOAD_BASE_URL: 'https://ftp.postgresql.org',
  DOWNLOAD_SUB_URL: 'pub/pgadmin/pgadmin4/v${version}/${os}',
  LOG_LEVEL: 'debug',
  OS_PLATFORM: osPF,
  ...devConst,
  IS_DEV: process.env.ENV === 'dev'? true : false,
  OS_NAME: osName,
  EVENTS: {
    LOAD_CONFIG: 'load-config',
    SAVE_CONFIG: 'save-config',
    SAVE_DATA_SUCCESS: 'save-data-success',
    SAVE_DATA_FAILED: 'save-data-failed',
  },
};

module.exports = constants;