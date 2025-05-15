import asyncio
from datetime import datetime
import traceback
from sqlalchemy import event
from database import SessionLocal, engine
from models_db import TareaDB, CuentaMoodleDB, EntregaDB
from services.scraper_service import scrape_task_details_async, login_moodle_async
from playwright.async_api import async_playwright
import logging

logger = logging.getLogger(__name__)

from celery_app import celery_app

@celery_app.task
def run_sync_tarea_task(tarea_id: int):
    """
    Task asíncrona para sincronizar una tarea específica, reusando la sesión de navegador
    para todas las operaciones necesarias.
    """
    try:
        db = SessionLocal()
        # Obtener información de la tarea y cuenta
        tarea = db.query(TareaDB).filter(TareaDB.id == tarea_id).first()
        if not tarea:
            raise Exception(f"No se encontró la tarea {tarea_id}")
            
        cuenta = db.query(CuentaMoodleDB).filter(CuentaMoodleDB.id == tarea.cuenta_id).first()
        if not cuenta:
            raise Exception(f"No se encontró la cuenta para la tarea {tarea_id}")
            
        # Actualizar estado de tarea a 'sincronizando'
        tarea.estado = 'sincronizando'
        tarea.fecha_sincronizacion = datetime.utcnow()
        db.commit()
        
        # Lanzar función asíncrona de sincronización
        asyncio.run(sync_tarea_async(
            tarea_id=tarea_id,
            moodle_url=cuenta.moodle_url,
            usuario=cuenta.usuario_moodle,
            contrasena=cuenta.contrasena_moodle
        ))
        
        # Actualizar estado final como completada
        tarea.estado = 'completada'
        tarea.fecha_sincronizacion = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        logger.error(f"Error sincronizando tarea {tarea_id}: {e}", exc_info=True)
        # Marcar error en la tarea
        tarea.estado = f"error: {str(e)}"
        tarea.fecha_sincronizacion = datetime.utcnow()
        db.commit()
        raise
    finally:
        db.close()

async def sync_tarea_async(tarea_id: int, moodle_url: str, usuario: str, contrasena: str):
    """
    Función asíncrona que maneja la sincronización real de la tarea,
    reutilizando la sesión del navegador para todas las operaciones.
    """
    async with async_playwright() as p:
        # Configurar navegador con optimizaciones
        browser = await p.chromium.launch(
            headless=True, 
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Login una sola vez
            await login_moodle_async(page, moodle_url, usuario, contrasena)
            logger.info(f"SCRAPER: login moodle OK para tarea {tarea_id}")

            # Obtener detalles de la tarea
            logger.info(f"SCRAPER: obteniendo detalles de tarea {tarea_id}")
            details = await scrape_task_details_async(page, moodle_url, tarea_id)
            
            # Actualizar la tarea en la base de datos
            db = SessionLocal()
            try:
                tarea = db.query(TareaDB).filter(TareaDB.id == tarea_id).first()
                
                # Actualizar campos de la tarea
                tarea.descripcion = details.get('descripcion')
                tarea.calificacion_maxima = details.get('calificacion_maxima')
                tarea.tipo_calificacion = details.get('tipo_calificacion')
                tarea.detalles_calificacion = details.get('detalles_calificacion')
                
                # Procesar entregas
                entregas = details.get('entregas_pendientes', [])
                if not entregas:
                    tarea.estado = 'sin_entregas'
                elif any(e.get('estado','').lower().startswith('enviado') or 
                        e.get('estado','').lower().startswith('pendiente') 
                        for e in entregas):
                    tarea.estado = 'pendiente_calificar'
                else:
                    tarea.estado = 'sin_pendientes'
                
                # Eliminar entregas anteriores
                db.query(EntregaDB).filter(EntregaDB.tarea_id == tarea_id).delete(synchronize_session=False)
                
                # Crear nuevas entregas
                for entrega in entregas:
                    archivos = entrega.get('archivos', [])
                    file_url = archivos[0]['url'] if archivos else None
                    file_name = archivos[0]['nombre'] if archivos else None
                    texto = entrega.get('texto')
                    nota_text = entrega.get('nota')
                    
                    local_path = None  # TODO: Implementar descarga de archivos

                    try:
                        nota = float(str(nota_text).replace(',', '.')) if nota_text else None
                    except:
                        nota = None

                    nueva_entrega = EntregaDB(
                        tarea_id=tarea.id,
                        alumno_id=entrega.get('alumno_id'),
                        fecha_entrega=entrega.get('fecha_entrega'),
                        contenido=texto,
                        file_url=file_url,
                        file_name=file_name,
                        estado=entrega.get('estado'),
                        nombre=entrega.get('nombre'),
                        nota=nota,
                        local_file_path=local_path
                    )
                    db.add(nueva_entrega)
                
                db.commit()
                logger.info(f"SCRAPER: tarea {tarea_id} actualizada con {len(entregas)} entregas")
                
            except Exception as e:
                db.rollback()
                raise
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error en sincronización de tarea {tarea_id}: {e}", exc_info=True)
            raise
        finally:
            await browser.close()