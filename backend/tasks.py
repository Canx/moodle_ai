from celery_app import celery_app
from endpoints.cursos import run_sync_tareas

@celery_app.task(name='run_sync_tareas_task')
def run_sync_tareas_task(cuenta_id, curso_id, moodle_url, usuario, contrasena, url_curso):
    # Ejecuta la función de sincronización original en el worker
    run_sync_tareas(cuenta_id, curso_id, moodle_url, usuario, contrasena, url_curso)
