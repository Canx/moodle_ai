from celery_app import celery_app
from endpoints.cursos import run_sync_tareas
from celery.utils.log import get_task_logger
from database import SessionLocal
from models_db import TareaDB, CuentaMoodleDB, EntregaDB
from services.scraper_service import scrape_task_details
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
import asyncio
import backoff
from contextlib import asynccontextmanager
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

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
        
        # Obtener detalles de la tarea y entregas
        log.info(f"Worker: iniciando scraping de detalles para tarea {tarea_db_id}")
        details = scrape_task_details(cuenta.moodle_url, cuenta.usuario_moodle, cuenta.contrasena_moodle, tarea.tarea_id)
        log.info(f"Worker: scraping completado para tarea {tarea_db_id}")
        
        descripcion = details.get('descripcion')
        entregas = details.get('entregas_pendientes', [])
        log.info(f"Worker: obtenidas {len(entregas)} entregas para tarea {tarea_db_id}")
        tipo_calif = details.get('tipo_calificacion')
        detalles_calif = details.get('detalles_calificacion')
        calif_max = details.get('calificacion_maxima')
        
        # Persistir entregas y encolar descargas
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
            
            # Encolar descarga si hay archivo
            if entrega_db.file_url and entrega_db.file_name:
                download_submission_file_task.delay(
                    file_url=entrega_db.file_url,
                    tarea_id=tarea_db_id,
                    entrega_id=entrega_db.alumno_id,
                    nombre_archivo=entrega_db.file_name,
                    moodle_url=cuenta.moodle_url,
                    usuario=cuenta.usuario_moodle,
                    contrasena=cuenta.contrasena_moodle
                )
                log.info(f"Worker: descarga encolada para archivo {entrega_db.file_name}")
        
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

# Variable global para el browser por worker
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None

async def get_or_create_browser():
    global _browser, _context
    if not _browser:
        p = await async_playwright().start()
        _browser = await p.chromium.launch(headless=True)
    if not _context:
        _context = await _browser.new_context()
    return _browser, _context

@asynccontextmanager
async def get_page_with_login(moodle_url: str, usuario: str, contrasena: str):
    browser, context = await get_or_create_browser()
    page = await context.new_page()
    try:
        # Primero intentar navegar a una página que requiere autenticación
        try:
            await page.goto(f"{moodle_url}/my", wait_until="domcontentloaded", timeout=10000)
            # Si no vemos el formulario de login, asumimos que la sesión es válida
            login_form = await page.query_selector("form#login")
            if login_form:
                # Necesitamos hacer login
                @backoff.on_exception(backoff.expo,
                                    Exception,
                                    max_tries=3,
                                    max_time=30)
                async def do_login():
                    from services.scraper_service import login_moodle_async
                    await login_moodle_async(page, moodle_url, usuario, contrasena)
                
                await do_login()
            else:
                logger.info("Sesión existente válida, no es necesario hacer login")
        except Exception as e:
            # Si hay error al verificar la sesión, intentar login por si acaso
            logger.warning(f"Error verificando sesión: {e}, intentando login")
            from services.scraper_service import login_moodle_async
            await login_moodle_async(page, moodle_url, usuario, contrasena)
        
        yield page
    finally:
        await page.close()

@celery_app.task(name='download_submission_file_task', bind=True, max_retries=3)
def download_submission_file_task(self, file_url: str, tarea_id: int, entrega_id: str, nombre_archivo: str, moodle_url: str, usuario: str, contrasena: str):
    """Task for downloading submission files with retries"""
    log = get_task_logger(__name__)
    log.info(f"Worker: iniciando descarga de archivo {nombre_archivo} para entrega {entrega_id}")
    
    db = SessionLocal()
    try:
        # Asegurar que el directorio base existe con los permisos correctos
        base_download_dir = Path("downloads")
        base_download_dir.mkdir(mode=0o755, exist_ok=True)
        
        # Crear estructura de directorios con permisos correctos
        download_dir = base_download_dir / str(tarea_id) / str(entrega_id)  
        download_dir.mkdir(parents=True, mode=0o755, exist_ok=True)
        local_path = download_dir / nombre_archivo

        async def download_file():
            async with get_page_with_login(moodle_url, usuario, contrasena) as page:
                try:
                    # Configurar timeouts y comportamiento del navegador
                    await page.set_viewport_size({"width": 1920, "height": 1080})
                    await page.set_extra_http_headers({
                        "Accept": "*/*",
                        "Accept-Encoding": "gzip, deflate, br",
                    })
                    
                    # Intentar descarga con manejo de errores
                    local_file_path = await download_submission_file(page, file_url, tarea_id, entrega_id, nombre_archivo)
                    
                    if not local_file_path or not Path(local_file_path).exists():
                        raise Exception("Descarga no completada correctamente")
                    
                    return local_file_path
                        
                except Exception as e:
                    log.error(f"Error durante la descarga: {e}")
                    raise

        # Ejecutar la descarga asíncrona
        local_file_path = asyncio.run(download_file())
        
        # Asegurar que el archivo descargado tiene los permisos correctos  
        if Path(local_file_path).exists():
            Path(local_file_path).chmod(0o644)
            
            # Actualizar la ruta en la base de datos
            db.query(EntregaDB).filter(
                EntregaDB.tarea_id == tarea_id,
                EntregaDB.alumno_id == entrega_id
            ).update({"local_file_path": local_file_path})
            
            db.commit()
            log.info(f"Worker: archivo descargado exitosamente: {local_file_path}")
            return local_file_path
        else:
            raise Exception("Archivo no encontrado después de la descarga")
            
    except Exception as e:
        log.error(f"Worker: error descargando archivo {nombre_archivo} para entrega {entrega_id}: {e}")
        db.rollback()
        # Reintento con backoff exponencial
        retry_in = (2 ** self.request.retries) * 60  # 1min, 2min, 4min
        # Si es un error específico de tipo de archivo, esperar más tiempo
        if '.xopp' in nombre_archivo.lower():
            retry_in *= 2  # Doble tiempo de espera para archivos .xopp
        raise self.retry(exc=e, countdown=retry_in)
    finally:
        db.close()

# Función de limpieza para cerrar el navegador al terminar el worker
@celery_app.task(name='cleanup_browser')
def cleanup_browser():
    """Clean up browser resources when worker shuts down"""
    global _browser, _context
    
    async def do_cleanup():
        if _context:
            await _context.close()
            _context = None
        if _browser:
            await _browser.close()
            _browser = None
            
    if _browser or _context:
        asyncio.run(do_cleanup())
