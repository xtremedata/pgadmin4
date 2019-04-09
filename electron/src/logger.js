const winston = require('winston');
const { format } = require('logform');
const path = require('path');

const homeDir = require('os').homedir();
const logDir = path.join(homeDir, '.pgadmin');

const pythonLogFormat = format.printf((info) => {
  return `[${info.label}] ${info.level}: ${info.message}`;
});
const electronLogFormat = format.printf((info) => {
  return `${info.timestamp} [${info.label}] ${info.level}: ${info.message}`;
});

const electronLogger = winston.createLogger({
  level: 'debug',
  format: format.combine(
    format.label({ label: 'Electron' }),
    format.timestamp(),
    electronLogFormat,
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: path.join(logDir, 'electron.log')}),
  ],
});

const pythonAppLogger = winston.createLogger({
  level: 'debug',
  format: format.combine(
    format.label({ label: 'PythonServer' }),
    pythonLogFormat,
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: path.join(logDir, 'pgadmin.log') }),
  ],
});

module.exports = {
  electronLogger,
  pythonAppLogger,
};
