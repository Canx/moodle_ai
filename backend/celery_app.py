import os
import logging
logging.basicConfig(level=logging.INFO)
from celery import Celery

# Configuración de Celery
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)

celery_app = Celery(
    'moodle_ai',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=['tasks']
)

# Configurar logging de Celery para capturar prints y eventos de tareas
celery_app.conf.update(
    # Allow hijacking root logger so application logs and prints are captured
    worker_hijack_root_logger=True,
    worker_redirect_stdouts=True,
    worker_redirect_stdouts_level='INFO',
    task_track_started=True,
)

# Importar módulo tasks para registrar las tareas decoradas
import tasks
