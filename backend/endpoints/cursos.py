from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from models_db import CursoDB, CuentaMoodleDB, TareaDB, EntregaDB, SincronizacionDB
from database import get_db, SessionLocal
from services.scraper_service import login_moodle, get_tareas_de_curso, scrape_task_details, login_moodle_async, scrape_task_details_async
from datetime import datetime
import traceback
from playwright.async_api import async_playwright
import logging
import os
import requests
import re
from pathlib import Path
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/cursos")
def obtener_cursos(db: Session = Depends(get_db)):
    cursos = db.query(CursoDB).all()
    return [{"id": c.id, "nombre": c.nombre} for c in cursos]

async def download_submission_file(page, file_url, tarea_id, entrega_id, nombre_archivo):
    # Crear estructura de directorios
    download_dir = Path("downloads") / str(tarea_id) / str(entrega_id)
    download_dir.mkdir(parents=True, exist_ok=True)
    
    local_path = download_dir / nombre_archivo
    
    try:
        # Timeout general para la descarga
        timeout = 120000  # 2 minutos para todos los archivos
        
        # Crear un nuevo contexto de navegador usando el browser existente
        browser = page.context.browser
        context = await browser.new_context(
            accept_downloads=True,
            viewport={'width': 1920, 'height': 1080}
        )
        
        try:
            # Transferir cookies de la sesión principal al nuevo contexto
            await context.add_cookies(await page.context.cookies())
            
            # Crear una nueva página en el contexto dedicado
            download_page = await context.new_page()
            try:
                # Configurar comportamiento optimizado para descargas
                await download_page.route("**/*", lambda route: route.continue_(
                    headers={
                        "Accept": "*/*",
                        "Accept-Encoding": "identity",  # Evitar compresión que puede causar problemas
                        "Connection": "keep-alive"
                    }
                ))
                
                # Preparar URL de descarga
                download_url = file_url
                if "forcedownload=1" not in download_url:
                    download_url += ("&" if "?" in download_url else "?") + "forcedownload=1"
                
                logger.info(f"Iniciando descarga desde: {download_url}")

                # Configurar y esperar la descarga con mejor manejo de errores
                async with download_page.expect_download(timeout=timeout) as download_info:
                    # Navegar directamente a la URL de descarga
                    await download_page.goto("about:blank")  # Página en blanco primero
                    await download_page.evaluate(f"window.location.href = '{download_url}'")
                    
                    # Esperar la descarga con validación adicional
                    download = await download_info.value
                    
                    # Dar tiempo para que inicie la descarga
                    await asyncio.sleep(2)
                    
                    # Guardar el archivo y validar resultado
                    await download.save_as(local_path)
                    
                    # Verificación exhaustiva del archivo descargado
                    if not local_path.exists():
                        raise Exception("El archivo descargado no existe")
                    
                    file_size = local_path.stat().st_size
                    if file_size == 0:
                        raise Exception("El archivo descargado está vacío")
                        
                    logger.info(f"Descarga completada: {nombre_archivo} ({file_size} bytes)")
                    return str(local_path)

            except Exception as e:
                logger.error(f"Error durante la descarga: {str(e)}")
                if local_path.exists():
                    local_path.unlink()
                raise
            finally:
                await download_page.close()
                
        except Exception as e:
            logger.error(f"Error durante el proceso de descarga: {str(e)}", exc_info=True)
            raise
        finally:
            await context.close()
            
    except Exception as e:
        logger.error(f"Error descargando archivo {file_url}: {str(e)}", exc_info=True)
        if local_path.exists():
            local_path.unlink()
        raise

async def run_sync_tareas_async(cuenta_id: int, curso_id: int, moodle_url: str, usuario: str, contrasena: str, url_curso: str):
    """
    Sincroniza todas las tareas no ocultas de un curso.
    Reutiliza una sesión de navegador y aprovecha la función sync_single_task para cada tarea.
    """
    db_task = SessionLocal()
    try:
        # Obtener estado actual de las tareas antes de empezar
        existing_tasks = {
            t.tarea_id: t
            for t in db_task.query(TareaDB).filter(TareaDB.curso_id == curso_id).all()
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = await browser.new_context()
            page = await context.new_page()

            # Login
            from services.scraper_service import login_moodle_async
            await login_moodle_async(page, moodle_url, usuario, contrasena)
            logger.info("SCRAPER: login moodle OK")

            # Obtener la lista de tareas del curso
            match = re.search(r"id=(\d+)", url_curso)
            if not match:
                raise Exception("URL del curso inválida")
                
            cid = int(match.group(1))
            await page.goto(f"{moodle_url}/course/view.php?id={cid}", wait_until="networkidle")
            
            elementos = await page.query_selector_all(".modtype_assign")
            
            # Extraer información básica de todas las tareas visibles
            tareas_info = []
            seen = set()
            
            for el in elementos:
                link_el = await el.query_selector("a.aalink")
                name_el = await el.query_selector(".instancename")
                if not (link_el and name_el):
                    continue
                    
                url = await link_el.get_attribute("href")
                nombre = await name_el.inner_text()
                
                m2 = re.search(r"id=(\d+)", url)
                if not m2:
                    continue
                    
                tid = int(m2.group(1))
                if tid in seen:
                    continue
                    
                # Si la tarea existe y está oculta, omitirla
                existing_task = existing_tasks.get(tid)
                if existing_task and existing_task.oculto:
                    continue
                    
                seen.add(tid)
                tareas_info.append({
                    "tarea_id": tid,
                    "titulo": nombre.strip(),
                    "url": url
                })
            
            total = len(tareas_info)
            logger.info(f"SCRAPER: Encontradas {total} tareas para sincronizar")
            
            # Limpiar las entregas de tareas no ocultas que ya no existen en Moodle
            tareas_actuales = {t["tarea_id"] for t in tareas_info}
            tareas_obsoletas = [
                t.id for t in existing_tasks.values()
                if not t.oculto and t.tarea_id not in tareas_actuales
            ]
            if tareas_obsoletas:
                # Eliminar primero las entregas
                db_task.query(EntregaDB).filter(
                    EntregaDB.tarea_id.in_(tareas_obsoletas)
                ).delete(synchronize_session=False)
                # Luego las tareas
                db_task.query(TareaDB).filter(
                    TareaDB.id.in_(tareas_obsoletas)
                ).delete(synchronize_session=False)
                db_task.commit()
            
            # Procesar cada tarea reutilizando la sesión
            for idx, info in enumerate(tareas_info, start=1):
                # Actualizar progreso
                sin = db_task.query(SincronizacionDB).filter(
                    SincronizacionDB.cuenta_id == cuenta_id,
                    SincronizacionDB.curso_id == curso_id
                ).first()
                if sin:
                    sin.estado = f"sincronizando tarea {idx}/{total}"
                    sin.fecha = datetime.utcnow()
                    sin.porcentaje = (idx/total)*100
                    db_task.commit()
                
                logger.info(f"SCRAPER: Sincronizando tarea {idx}/{total}: {info['titulo']} (cmid={info['tarea_id']})")
                
                try:
                    existing_task = existing_tasks.get(info['tarea_id'])
                    was_hidden = existing_task.oculto if existing_task else False
                    
                    # Usar sync_single_task para procesar cada tarea
                    from services.task_sync_service import sync_single_task
                    await sync_single_task(
                        db=db_task,
                        task_info=info,
                        page=page,
                        cuenta_id=cuenta_id,
                        curso_id=curso_id,
                        moodle_url=moodle_url,
                        existing_task=existing_task,
                        was_hidden=was_hidden
                    )
                except Exception as e:
                    logger.error(f"Error sincronizando tarea {info['tarea_id']}: {e}")
                    # Continue with next task sin romper el proceso completo
                    continue

            await browser.close()
            
            # Actualizar estado final
            sin = db_task.query(SincronizacionDB).filter(
                SincronizacionDB.cuenta_id == cuenta_id,
                SincronizacionDB.curso_id == curso_id
            ).first()
            if sin:
                sin.estado = 'completada'
                sin.fecha = datetime.utcnow()
                sin.porcentaje = 100.0
                sin.duracion = (datetime.utcnow() - sin.fecha_inicio).total_seconds()
                db_task.commit()
                logger.info("SINCRONIZACION COMPLETADA")

    except Exception as e:
        logger.error(f"Error en sincronización: {e}")
        traceback.print_exc()
        db_task.rollback()
        sin = db_task.query(SincronizacionDB).filter(
            SincronizacionDB.cuenta_id == cuenta_id,
            SincronizacionDB.curso_id == curso_id
        ).first()
        if sin:
            sin.estado = f"error: {str(e)}"
            sin.fecha = datetime.utcnow()
            db_task.commit()
        raise
    finally:
        db_task.close()

def run_sync_tareas(cuenta_id: int, curso_id: int, moodle_url: str, usuario: str, contrasena: str, url_curso: str):
    # Wrapper síncrono para ejecutar la versión asíncrona
    asyncio.run(run_sync_tareas_async(cuenta_id, curso_id, moodle_url, usuario, contrasena, url_curso))

@router.post("/api/cursos/{curso_id}/sincronizar_tareas")
def sincronizar_tareas_curso(curso_id: int):
    db = SessionLocal()
    curso = db.query(CursoDB).filter(CursoDB.id == curso_id).first()
    if not curso:
        db.close()
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    cuenta = db.query(CuentaMoodleDB).filter(CuentaMoodleDB.id == curso.cuenta_id).first()
    if not cuenta:
        db.close()
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    now = datetime.utcnow()
    # Inicializar o reiniciar sincronización con campos de progreso
    sin = db.query(SincronizacionDB).filter(
        SincronizacionDB.cuenta_id==cuenta.id,
        SincronizacionDB.curso_id==curso_id
    ).first()
    if not sin:
        sin = SincronizacionDB(
            cuenta_id=cuenta.id,
            curso_id=curso_id,
            estado='sincronizando',
            fecha=now,
            fecha_inicio=now,
            porcentaje=0.0,
            tipo='tareas',
            duracion=None
        )
        db.add(sin)
    else:
        sin.estado = 'sincronizando'
        sin.fecha = now
        sin.fecha_inicio = now
        sin.porcentaje = 0.0
        sin.tipo = 'tareas'
        sin.duracion = None
    db.commit()
    # Encolar sincronización en worker Celery (import local para evitar ciclo)
    from tasks import run_sync_tareas_task
    run_sync_tareas_task.delay(cuenta.id, curso_id, cuenta.moodle_url, cuenta.usuario_moodle, cuenta.contrasena_moodle, curso.url)
    db.close()
    return {"mensaje": "Sincronización iniciada"}

@router.get("/api/cursos/{curso_id}/sincronizacion")
def estado_sincronizacion(curso_id: int, db: Session = Depends(get_db)):
    curso = db.query(CursoDB).filter(CursoDB.id == curso_id).first()
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    sin = db.query(SincronizacionDB).filter(
        SincronizacionDB.cuenta_id == curso.cuenta_id,
        SincronizacionDB.curso_id == curso_id
    ).first()
    if not sin:
        return {"estado": "no_iniciado", "fecha": None}
    return {
        "estado": sin.estado,
        "fecha": sin.fecha.isoformat(),
        "fecha_inicio": sin.fecha_inicio.isoformat() if sin.fecha_inicio else None,
        "porcentaje": sin.porcentaje,
        "tipo": sin.tipo,
        "duracion": sin.duracion
    }

@router.get("/api/cursos/{curso_id}/tareas")
def obtener_tareas_curso(curso_id: int, db: Session = Depends(get_db)):
    tareas = db.query(TareaDB).filter(
        TareaDB.curso_id == curso_id,
        TareaDB.oculto == False
    ).order_by(TareaDB.id.desc()).all()
    # Incluir count de entregas pendientes por tarea
    result = []
    for t in tareas:
        # contar solo entregas que realmente tienen contenido enviado
        entregadas = db.query(EntregaDB).filter(
            EntregaDB.tarea_id == t.id,
            or_(EntregaDB.file_url != None, EntregaDB.contenido != None),
            EntregaDB.estado.ilike('%enviado%')  # Solo contar las que están en estado "enviado"
        ).count()
        # contar solo entregas enviadas que no tienen nota
        pendientes = db.query(EntregaDB).filter(
            EntregaDB.tarea_id == t.id,
            EntregaDB.nota == None,
            or_(EntregaDB.file_url != None, EntregaDB.contenido != None),
            EntregaDB.estado.ilike('%enviado%')  # Solo contar las que están en estado "enviado"
        ).count()
        result.append({
            "id": t.id,
            "tarea_id": t.tarea_id,
            "titulo": t.titulo,
            "descripcion": t.descripcion,
            "estado": t.estado,
            "entregadas": entregadas,
            "pendientes": pendientes
        })
    return result

@router.get("/api/cursos/{curso_id}/tareas/ocultas")
def obtener_tareas_ocultas_curso(curso_id: int, db: Session = Depends(get_db)):
    tareas = db.query(TareaDB).filter(
        TareaDB.curso_id == curso_id,
        TareaDB.oculto == True
    ).order_by(TareaDB.id.desc()).all()
    return [{"id": t.id, "tarea_id": t.tarea_id, "titulo": t.titulo, "descripcion": t.descripcion, "estado": t.estado} for t in tareas]

@router.post("/api/cursos/{curso_id}/ocultar")
def ocultar_curso(curso_id: int, db: Session = Depends(get_db)):
    curso = db.query(CursoDB).filter(CursoDB.id == curso_id).first()
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    curso.oculto = True
    db.commit()
    return {"ok": True, "oculto": True}

@router.post("/api/cursos/{curso_id}/mostrar")
def mostrar_curso(curso_id: int, db: Session = Depends(get_db)):
    curso = db.query(CursoDB).filter(CursoDB.id == curso_id).first()
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    curso.oculto = False
    db.commit()
    return {"ok": True, "oculto": False}