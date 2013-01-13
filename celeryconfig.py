from datetime import timedelta

BROKER_URL = 'sqla+sqlite:///celerydb.sqlite'

CELERY_IMPORTS = ('meter', 'requests', )

CELERYBEAT_SCHEDULE = {
    'update-meter': {
        'task': 'meter.tq_update_meter_data',
        'schedule': timedelta(minutes=20),
        'args': ()
    },
}

CELERY_TIMEZONE = 'UTC'
