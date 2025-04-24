from celery_app import celery_app
from endpoints.cursos import run_sync_tareas
from celery.utils.log import get_task_logger

# Logger para la tarea de sincronización
logger = get_task_logger(__name__)

@celery_app.task(name='run_sync_tareas_task')
def run_sync_tareas_task(cuenta_id, curso_id, moodle_url, usuario, contrasena, url_curso):
    logger.info(f"Worker: comenzando sincronización del curso {curso_id} (cuenta {cuenta_id})")
    try:
        run_sync_tareas(cuenta_id, curso_id, moodle_url, usuario, contrasena, url_curso)
        logger.info(f"Worker: sincronización completada del curso {curso_id} (cuenta {cuenta_id})")
    except Exception as e:
        logger.exception(f"Worker: error al sincronizar curso {curso_id} (cuenta {cuenta_id}): {e}")
        raise
