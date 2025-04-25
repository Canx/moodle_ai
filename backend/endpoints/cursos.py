from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from models_db import CursoDB, CuentaMoodleDB, TareaDB, EntregaDB, SincronizacionDB
from database import get_db, SessionLocal
from services.scraper_service import login_moodle, get_tareas_de_curso, scrape_task_details
from datetime import datetime
import traceback
from playwright.sync_api import sync_playwright
import logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/cursos")
def obtener_cursos(db: Session = Depends(get_db)):
    cursos = db.query(CursoDB).all()
    return [{"id": c.id, "nombre": c.nombre} for c in cursos]

def run_sync_tareas(cuenta_id: int, curso_id: int, moodle_url: str, usuario: str, contrasena: str, url_curso: str):
    db_task = SessionLocal()
    try:
        # Conservar tareas ocultas y preparar borrado de visibles
        old_tareas = db_task.query(TareaDB).filter(TareaDB.curso_id == curso_id).all()
        hidden_remote_ids = {t.tarea_id for t in old_tareas if t.oculto}
        tarea_ids = [t.id for t in old_tareas if not t.oculto]
        if tarea_ids:
            db_task.query(EntregaDB).filter(EntregaDB.tarea_id.in_(tarea_ids)).delete(synchronize_session=False)
            db_task.commit()
        db_task.query(TareaDB).filter(TareaDB.curso_id == curso_id, TareaDB.oculto == False).delete(synchronize_session=False)
        db_task.commit()
        # Scraping excluyendo tareas ocultas y procesando progresivamente
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page()
            page.on("console", lambda msg: logger.info(f"[browser] {msg.text}"))
            logger.info(f"SCRAPER: iniciar sesión en {moodle_url} usuario {usuario}")
            # Login y lista inicial de tareas
            login_moodle(page, moodle_url, usuario, contrasena)
            logger.info("SCRAPER: login moodle OK")
            curso_info = {"url": url_curso}
            tareas_info = get_tareas_de_curso(browser, page, moodle_url, None, curso_info, hidden_remote_ids)
            total = len(tareas_info)
            logger.info(f"SCRAPER: tareas encontradas: {total}")
            for idx, info in enumerate(tareas_info, start=1):
                # Actualizar progreso
                sin = db_task.query(SincronizacionDB).filter(SincronizacionDB.cuenta_id == cuenta_id).first()
                if sin:
                    sin.estado = f"sincronizando tarea {idx}/{total}"
                    sin.fecha = datetime.utcnow()
                    sin.porcentaje = (idx/total)*100
                    db_task.commit()
                    logger.info(f"SINCRONIZACION PROGRESO: tarea {idx}/{total}")
                logger.info(f"SCRAPER: procesando tarea {idx}/{total} id {info.get('tarea_id')}")
                if info.get('tarea_id') in hidden_remote_ids:
                    continue
                # Estado según entregas
                entregas = info.get('entregas_pendientes', [])
                if not entregas:
                    estado = 'sin_entregas'
                elif any(e.get('estado','').lower().startswith('enviado') or e.get('estado','').lower().startswith('pendiente') for e in entregas):
                    estado = 'pendiente_calificar'
                else:
                    estado = 'sin_pendientes'
                # Detalles y descripción
                logger.info(f"SCRAPER: obteniendo detalles tarea {info.get('tarea_id')}")
                try:
                    details = scrape_task_details(moodle_url, usuario, contrasena, info['tarea_id'])
                except:
                    details = {}
                descripcion = details.get('descripcion')
                tipo_calificacion = details.get('tipo_calificacion', info.get('tipo_calificacion'))
                detalles_calificacion = details.get('detalles_calificacion', info.get('detalles_calificacion'))
                # Crear registros en BD
                nueva_tarea = TareaDB(
                    cuenta_id=cuenta_id,
                    curso_id=curso_id,
                    tarea_id=info['tarea_id'],
                    titulo=info['titulo'],
                    descripcion=descripcion,
                    estado=estado,
                    calificacion_maxima=info.get('calificacion_maxima'),
                    tipo_calificacion=tipo_calificacion,
                    detalles_calificacion=detalles_calificacion
                )
                db_task.add(nueva_tarea)
                db_task.commit()
                db_task.refresh(nueva_tarea)
                for entrega in entregas:
                    archivos = entrega.get('archivos', [])
                    file_url = archivos[0]['url'] if archivos else None
                    file_name = archivos[0]['nombre'] if archivos else None
                    texto = entrega.get('texto')
                    nota_text = entrega.get('nota')
                    try:
                        nota = float(str(nota_text).replace(',', '.')) if nota_text else None
                    except:
                        nota = None
                    nueva_entrega = EntregaDB(
                        tarea_id=nueva_tarea.id,
                        alumno_id=entrega.get('alumno_id'),
                        fecha_entrega=entrega.get('fecha_entrega'),
                        contenido=texto,
                        file_url=file_url,
                        file_name=file_name,
                        estado=entrega.get('estado'),
                        nombre=entrega.get('nombre'),
                        nota=nota
                    )
                    db_task.add(nueva_entrega)
                db_task.commit()
            browser.close()
            logger.info("SCRAPER: browser cerrado")
        sin = db_task.query(SincronizacionDB).filter(SincronizacionDB.cuenta_id==cuenta_id).first()
        if sin:
            sin.estado = 'completada'
            sin.fecha = datetime.utcnow()
            sin.porcentaje = 100.0
            # Duración en segundos
            sin.duracion = (datetime.utcnow() - sin.fecha_inicio).total_seconds()
            db_task.commit()
            logger.info("SINCRONIZACION COMPLETADA")
    except Exception as e:
        # Limpiar la sesión tras fallo para evitar transacción abortada
        db_task.rollback()
        # Log exception stack and message
        traceback.print_exc()
        sin = db_task.query(SincronizacionDB).filter(SincronizacionDB.cuenta_id==cuenta_id).first()
        if sin:
            sin.estado = f"error: {e}"
            sin.fecha = datetime.utcnow()
            db_task.commit()
    finally:
        db_task.close()

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
    sin = db.query(SincronizacionDB).filter(SincronizacionDB.cuenta_id==cuenta.id).first()
    if not sin:
        sin = SincronizacionDB(
            cuenta_id=cuenta.id,
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
    sin = db.query(SincronizacionDB).filter(SincronizacionDB.cuenta_id == curso.cuenta_id).first()
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
        # contar solo entregas con archivo o contenido de texto
        entregadas = db.query(EntregaDB).filter(
            EntregaDB.tarea_id == t.id,
            or_(EntregaDB.file_url != None, EntregaDB.contenido != None)
        ).count()
        pendientes = db.query(EntregaDB).filter(EntregaDB.tarea_id == t.id, EntregaDB.nota == None).count()
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