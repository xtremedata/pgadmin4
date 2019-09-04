const winston = require('winston');
const { format } = require('logform');

const pythonLogFormat = format.printf((info) => {
  return `[${info.label}] ${info.level}: ${info.message}`;
});
const electronLogFormat = format.printf((info) => {
  return `${info.timestamp} [${info.label}] ${info.level}: ${info.message}`;
});

const createLogger = function(logFilePath, logFormat='', level='debug') {
  let formatObj = null;

  if(logFormat === 'python') {
    formatObj = format.combine(
      format.label({ label: 'PythonServer' }),
      pythonLogFormat,
    );
  } else if(logFormat === 'electron') {
    formatObj = format.combine(
      format.label({ label: 'Electron' }),
      format.timestamp(),
      electronLogFormat,
    );
  }

  return winston.createLogger({
    level: level,
    format: formatObj,
    transports: [
      new winston.transports.Console(),
      new winston.transports.File({ filename: logFilePath }),
    ],
  });
};

module.exports = {
  createLogger,
};
