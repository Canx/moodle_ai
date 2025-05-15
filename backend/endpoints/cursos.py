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
    db_task = SessionLocal()
    try:
        # Cache task hidden states before any deletions
        existing_task_states = {
            t.tarea_id: {"id": t.id, "oculto": t.oculto} 
            for t in db_task.query(TareaDB).filter(TareaDB.curso_id == curso_id).all()
        }
        
        # Get IDs of non-hidden tasks
        tarea_ids = [info["id"] for info in existing_task_states.values() if not info["oculto"]]
        
        # Delete entries for non-hidden tasks
        if tarea_ids:
            db_task.query(EntregaDB).filter(EntregaDB.tarea_id.in_(tarea_ids)).delete(synchronize_session=False)
            db_task.commit()
            
        # Delete non-hidden tasks
        db_task.query(TareaDB).filter(TareaDB.curso_id == curso_id, TareaDB.oculto == False).delete(synchronize_session=False)
        db_task.commit()

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
            
            tareas_info = []
            seen = set()
            
            elementos = await page.query_selector_all(".modtype_assign")
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
                
                # Check if task exists and is hidden using cached states
                task_state = existing_task_states.get(tid)
                if task_state and task_state["oculto"]:
                    continue
                    
                seen.add(tid)
                tareas_info.append({"tarea_id": tid, "titulo": nombre.strip(), "url": url})
            
            total = len(tareas_info)
            logger.info(f"SCRAPER: encontradas {total} tareas")

            # Procesar cada tarea
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
                    logger.info(f"SINCRONIZACION PROGRESO: tarea {idx}/{total}")

                logger.info(f"SCRAPER: procesando tarea {idx}/{total} id {info.get('tarea_id')}")
                
                # Obtener detalles de la tarea usando la sesión existente
                details = await scrape_task_details_async(page, moodle_url, info['tarea_id'])
                entregas = details.get('entregas_pendientes', [])
                
                # Determinar estado según entregas
                if not entregas:
                    estado = 'sin_entregas'
                elif any(e.get('estado','').lower().startswith('enviado') or e.get('estado','').lower().startswith('pendiente') for e in entregas):
                    estado = 'pendiente_calificar'
                else:
                    estado = 'sin_pendientes'

                # Find if task exists or create new 
                task_state = existing_task_states.get(info['tarea_id'])
                tarea = None
                if task_state:
                    tarea = db_task.query(TareaDB).filter(TareaDB.id == task_state["id"]).first()
                
                # Preparar datos de la tarea
                tarea_data = {
                    'cuenta_id': cuenta_id,
                    'curso_id': curso_id,
                    'tarea_id': info['tarea_id'],
                    'titulo': info['titulo'],
                    'descripcion': details.get('descripcion'),
                    'estado': estado,
                    'calificacion_maxima': details.get('calificacion_maxima'),
                    'tipo_calificacion': details.get('tipo_calificacion'),
                    'detalles_calificacion': details.get('detalles_calificacion')
                }
                
                if tarea:
                    # Si existe y está oculta, mantener ese estado
                    if task_state["oculto"]:
                        tarea_data['oculto'] = True
                    # Actualizar la tarea existente
                    for key, value in tarea_data.items():
                        setattr(tarea, key, value)
                else:
                    # Crear nueva tarea
                    tarea = TareaDB(**tarea_data)
                    db_task.add(tarea)
                
                db_task.commit()
                db_task.refresh(tarea)

                # Process submissions
                for entrega in entregas:
                    archivos = entrega.get('archivos', [])
                    file_url = archivos[0]['url'] if archivos else None
                    file_name = archivos[0]['nombre'] if archivos else None
                    texto = entrega.get('texto')
                    nota_text = entrega.get('nota')
                    
                    local_path = None
                    if file_url and file_name:
                        # Try multiple times if download fails
                        max_intentos = 3
                        for intento in range(max_intentos):
                            try:
                                logger.info(f"Intento {intento + 1} de {max_intentos} descargando {file_name}")
                                # Use our DB task ID, not Moodle's
                                local_path = await download_submission_file(page, file_url, tarea.id, entrega.get('alumno_id'), file_name)
                                break  # If download successful, exit loop
                            except Exception as e:
                                logger.error(f"Error intento {intento + 1} descargando archivo de entrega: {e}")
                                await asyncio.sleep(5 * (intento + 1))  # Wait longer between attempts
                                continue
                    
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
                    db_task.add(nueva_entrega)
                
                db_task.commit()

            await browser.close()
            
            # Update final state
            sin = db_task.query(SincronizacionDB).filter(
                SincronizacionDB.cuenta_id==cuenta_id,
                SincronizacionDB.curso_id==curso_id
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
            SincronizacionDB.cuenta_id==cuenta_id,
            SincronizacionDB.curso_id==curso_id
        ).first()
        if sin:
            sin.estado = f"error: {e}"
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