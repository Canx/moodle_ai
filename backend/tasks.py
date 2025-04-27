from celery_app import celery_app
from endpoints.cursos import run_sync_tareas
from celery.utils.log import get_task_logger
from database import SessionLocal
from models_db import TareaDB, CuentaMoodleDB, EntregaDB
from services.scraper_service import scrape_task_details
from datetime import datetime
from celery_app import celery_app

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

# Task para sincronizar una sola tarea en segundo plano
@celery_app.task(name='run_sync_tarea_task')
def run_sync_tarea_task(tarea_db_id):
    log = get_task_logger(__name__)
    log.info(f"Worker: comenzando sincronización de la tarea {tarea_db_id}")
    db = SessionLocal()
    try:
        tarea = db.query(TareaDB).filter(TareaDB.id == tarea_db_id).first()
        if not tarea:
            log.error(f"Tarea {tarea_db_id} no encontrada")
            return
        cuenta = db.query(CuentaMoodleDB).filter(CuentaMoodleDB.id == tarea.cuenta_id).first()
        if not cuenta:
            log.error(f"Cuenta Moodle {tarea.cuenta_id} no encontrada para tarea {tarea_db_id}")
            return
        db.query(TareaDB).filter(TareaDB.id == tarea_db_id).update({'estado': 'sincronizando'})
        db.commit()
        log.info(f"Worker: estado de tarea {tarea_db_id} actualizado a 'sincronizando'")
        log.info(f"Worker: iniciando scraping de detalles para tarea {tarea_db_id}")
        details = scrape_task_details(cuenta.moodle_url, cuenta.usuario_moodle, cuenta.contrasena_moodle, tarea.tarea_id)
        log.info(f"Worker: scraping completado para tarea {tarea_db_id}")
        descripcion = details.get('descripcion')
        entregas = details.get('entregas_pendientes', [])
        log.info(f"Worker: obtenidas {len(entregas)} entregas para tarea {tarea_db_id}")
        tipo_calif = details.get('tipo_calificacion')
        detalles_calif = details.get('detalles_calificacion')
        calif_max = details.get('calificacion_maxima')
        # Persistir entregas
        log.info(f"Worker: iniciando persistencia de entregas para tarea {tarea_db_id}")
        for e in entregas:
            log.info(f"Worker: procesando entrega alumno {e.get('alumno_id')} para tarea {tarea_db_id}")
            entrega_db = db.query(EntregaDB).filter(EntregaDB.tarea_id == tarea_db_id, EntregaDB.alumno_id == e['alumno_id']).first()
            if not entrega_db:
                entrega_db = EntregaDB(tarea_id=tarea_db_id, alumno_id=e['alumno_id'])
            entrega_db.fecha_entrega = e.get('fecha_entrega')
            entrega_db.estado = e.get('estado')
            entrega_db.nombre = e.get('nombre')
            archivos = e.get('archivos', [])
            entrega_db.file_url = archivos[0]['url'] if archivos else None
            entrega_db.file_name = archivos[0]['nombre'] if archivos else None
            entrega_db.contenido = e.get('texto')
            nota_text = e.get('nota')
            try:
                entrega_db.nota = float(str(nota_text).replace(',', '.')) if nota_text else None
            except:
                entrega_db.nota = None
            db.add(entrega_db)
        db.commit()
        log.info(f"Worker: persistencia de entregas completada para tarea {tarea_db_id}")
        # Estado final de la tarea (basado en entregas reales con archivos o texto)
        reales = [e for e in entregas if e.get('archivos') or e.get('texto')]
        if not reales:
            estado = 'sin_entregas'
        elif any(e.get('estado','').lower().startswith(('enviado','pendiente')) for e in reales):
            estado = 'pendiente_calificar'
        else:
            estado = 'sin_pendientes'
        log.info(f"Worker: estado final calculado '{estado}' para tarea {tarea_db_id}")
        # Actualizar tarea
        db.query(TareaDB).filter(TareaDB.id == tarea_db_id).update({
            'descripcion': descripcion,
            'fecha_sincronizacion': datetime.now().isoformat(),
            'calificacion_maxima': calif_max,
            'estado': estado,
            'tipo_calificacion': tipo_calif,
            'detalles_calificacion': detalles_calif
        })
        db.commit()
        log.info(f"Worker: tarea {tarea_db_id} actualizada en BD")
        # Eliminar entregas no existentes
        scraped_ids = [e['alumno_id'] for e in entregas]
        db.query(EntregaDB).filter(EntregaDB.tarea_id == tarea_db_id, ~EntregaDB.alumno_id.in_(scraped_ids)).delete(synchronize_session=False)
        db.commit()
        log.info(f"Worker: entregas obsoletas eliminadas para tarea {tarea_db_id}")
        log.info(f"Worker: sincronización completada de la tarea {tarea_db_id}")
    except Exception as e:
        log.exception(f"Worker: error sincronizando tarea {tarea_db_id}: {e}")
        db.rollback()
        db.query(TareaDB).filter(TareaDB.id == tarea_db_id).update({'estado':'error'})
        db.commit()
    finally:
        db.close()
