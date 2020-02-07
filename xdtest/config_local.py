from config import *

# Debug mode
DEBUG = True

# App mode
SERVER_MODE = True

# Enable the test module
MODULE_BLACKLIST.remove('test')

# Log
CONSOLE_LOG_LEVEL = DEBUG
FILE_LOG_LEVEL = DEBUG

DEFAULT_SERVER = '127.0.0.1'

UPGRADE_CHECK_ENABLED = False
DATA_DIR="/home/rga/tmp/pgadmin4"

# Use a different config DB for each server mode.
if SERVER_MODE == False:
    SQLITE_PATH = os.path.join( \
            DATA_DIR, "lib", \
            'pgadmin4-desktop.db')
else:
    SQLITE_PATH = os.path.join( \
            DATA_DIR, "lib", \
            'pgadmin4-server.db')

LOG_FILE = os.path.join( \
        DATA_DIR, "log", \
        'pgadmin4.log')
SESSION_DB_PATH = os.path.join(DATA_DIR, "lib", "sessions")
STORAGE_DIR = os.path.join(DATA_DIR, "lib", "storage")
HELP_PATH = '/usr/share/doc/pgadmin4-docs/en_US/html'
