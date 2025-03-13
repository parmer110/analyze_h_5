import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'm10.settings')

app = Celery('m10')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'refresh-web-request-every-20-min': {
        'task': 'scheduler.tasks.refresh_web_request',
        'schedule': crontab(minute='*/20'),
        'args': (),
    },
}

app.conf.task_time_limit = 300
app.conf.task_soft_time_limit = 270
