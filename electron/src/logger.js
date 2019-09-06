const winston = require('winston');
const { format } = require('logform');
const path = require('path');

const pythonLogFormat = format.printf((info) => {
  return `[${info.label}] ${info.level}: ${info.message}`;
});
const electronLogFormat = format.printf((info) => {
  return `${info.timestamp} [${info.label}] ${info.level}: ${info.message}`;
});

const createLogger = function(logFilePath, logFormat='', level='debug') {
  let formatObj = null, fileName = null;

  if(logFormat === 'python') {
    formatObj = format.combine(
      format.label({ label: 'PythonServer' }),
      pythonLogFormat,
    );
    fileName = path.join(logFilePath, 'pgadmin.log');
  } else if(logFormat === 'electron') {
    formatObj = format.combine(
      format.label({ label: 'Electron' }),
      format.timestamp(),
      electronLogFormat,
    );
    fileName = path.join(logFilePath, 'electron.log');
  }

  return winston.createLogger({
    level: level,
    format: formatObj,
    transports: [
      new winston.transports.Console(),
      new winston.transports.File({ filename: fileName}),
    ],
  });
};

module.exports = function(logFilePath, level='debug') {
  if(!logFilePath) {
    logFilePath = '.';
  }
  return {
    electronLogger: createLogger(logFilePath, 'electron', level),
    pythonAppLogger: createLogger(logFilePath, 'python', level),
  };
};
