import os
from pathlib import Path
import queue
import logging
import logging.handlers
import logging.config
from concurrent_log_handler import ConcurrentRotatingFileHandler
import atexit

BASE_DIR = Path(__file__).resolve().parent.parent

# تعریف مسیر‌های مورد نظر
LOGGING_DIR = os.path.join(BASE_DIR, 'logs')
DEBUG_LOG_DIR = os.path.join(LOGGING_DIR, 'debug')
ERROR_LOG_DIR = os.path.join(LOGGING_DIR, 'error')
WARNING_LOG_DIR = os.path.join(LOGGING_DIR, 'warning')

log_directories = [
    LOGGING_DIR,
    DEBUG_LOG_DIR,
    ERROR_LOG_DIR,
    WARNING_LOG_DIR
]

# ایجاد پوشه‌ها به صورت خودکار
for directory in log_directories:
    if not os.path.exists(directory):
        os.makedirs(directory)


q = queue.Queue()

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'error_file': {
            'level': 'ERROR',
            'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
            'filename': os.path.join(LOGGING_DIR, 'error/error.log'),
            'formatter': 'verbose',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 3,
        },
        'warning_file': {
            'level': 'WARNING',
            'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
            'filename': os.path.join(LOGGING_DIR, 'warning/warning.log'),
            'formatter': 'verbose',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 3,
        },
        'debug_file': {
            'level': 'DEBUG',
            'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
            'filename': os.path.join(LOGGING_DIR, 'debug/debug.log'),
            'formatter': 'verbose',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 3,
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'error_file', 'warning_file', 'debug_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

logging.config.dictConfig(LOGGING)

error_listener = logging.handlers.QueueListener(
    q, logging.FileHandler('error.log')
)
warning_listener = logging.handlers.QueueListener(
    q, logging.FileHandler('warning.log')
)
debug_listener = logging.handlers.QueueListener(
    q, logging.FileHandler('debug.log')
)

error_listener.start()
warning_listener.start()
debug_listener.start()

def stop_listeners():
    error_listener.stop()
    warning_listener.stop()
    debug_listener.stop()

atexit.register(stop_listeners)