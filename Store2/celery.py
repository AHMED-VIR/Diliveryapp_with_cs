import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')

app = Celery('your_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'check-sale-expirations': {
        'task': 'products.tasks.expire_sales',
        'schedule': 3600.0,  # Every hour (in seconds)
    },
}