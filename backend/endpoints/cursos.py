from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_
from models_db import CursoDB, CuentaMoodleDB, TareaDB, EntregaDB, SincronizacionDB
from database import get_db, SessionLocal
from services.scraper_service import scrape_tasks
from datetime import datetime
import traceback

router = APIRouter()

@router.get("/api/cursos")
def obtener_cursos(db: Session = Depends(get_db)):
    cursos = db.query(CursoDB).all()
    return [{"id": c.id, "nombre": c.nombre} for c in cursos]

def run_sync_tareas(cuenta_id: int, curso_id: int, moodle_url: str, usuario: str, contrasena: str, url_curso: str):
    db_task = SessionLocal()
    try:
        tareas = scrape_tasks(moodle_url, usuario, contrasena, url_curso)
        old_tareas = db_task.query(TareaDB).filter(TareaDB.curso_id == curso_id).all()
        tarea_ids = [t.id for t in old_tareas]
        if tarea_ids:
            db_task.query(EntregaDB).filter(EntregaDB.tarea_id.in_(tarea_ids)).delete(synchronize_session=False)
            db_task.commit()
        db_task.query(TareaDB).filter(TareaDB.curso_id == curso_id).delete(synchronize_session=False)
        db_task.commit()
        for tarea in tareas:
            entregas = tarea.get('entregas_pendientes', [])
            if not entregas:
                estado = 'sin_entregas'
            elif any(e.get('estado','').lower().startswith('enviado') or e.get('estado','').lower().startswith('pendiente') for e in entregas):
                estado = 'pendiente_calificar'
            else:
                estado = 'sin_pendientes'
            nueva_tarea = TareaDB(
                cuenta_id=cuenta_id,
                curso_id=curso_id,
                tarea_id=tarea['tarea_id'],
                titulo=tarea['titulo'],
                estado=estado,
                calificacion_maxima=tarea.get('calificacion_maxima')
            )
            db_task.add(nueva_tarea)
            db_task.commit()
            db_task.refresh(nueva_tarea)
            for entrega in entregas:
                nueva_entrega = EntregaDB(
                    tarea_id=nueva_tarea.id,
                    alumno_id=entrega.get('alumno_id'),
                    fecha_entrega=entrega.get('fecha_entrega'),
                    file_url=entrega.get('archivos',[{}])[0].get('url') if entrega.get('archivos') else None,
                    file_name=entrega.get('archivos',[{}])[0].get('nombre') if entrega.get('archivos') else None,
                    estado=entrega.get('estado'),
                    nombre=entrega.get('nombre')
                )
                db_task.add(nueva_entrega)
            db_task.commit()
        sin = db_task.query(SincronizacionDB).filter(SincronizacionDB.cuenta_id==cuenta_id).first()
        if sin:
            sin.estado='completada'
            sin.fecha=datetime.utcnow()
            db_task.commit()
    except Exception as e:
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
def sincronizar_tareas_curso(curso_id: int, background_tasks: BackgroundTasks):
    db = SessionLocal()
    curso = db.query(CursoDB).filter(CursoDB.id == curso_id).first()
    if not curso:
        db.close()
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    cuenta = db.query(CuentaMoodleDB).filter(CuentaMoodleDB.id == curso.cuenta_id).first()
    if not cuenta:
        db.close()
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    sin = db.query(SincronizacionDB).filter(SincronizacionDB.cuenta_id==cuenta.id).first()
    now = datetime.utcnow()
    if not sin:
        sin = SincronizacionDB(cuenta_id=cuenta.id, estado='sincronizando', fecha=now)
        db.add(sin)
    else:
        sin.estado='sincronizando'
        sin.fecha=now
    db.commit()
    background_tasks.add_task(run_sync_tareas, cuenta.id, curso_id, cuenta.moodle_url, cuenta.usuario_moodle, cuenta.contrasena_moodle, curso.url)
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
    return {"estado": sin.estado, "fecha": sin.fecha.isoformat()}

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