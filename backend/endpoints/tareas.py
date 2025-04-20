# backend/endpoints/tareas.py

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session
from models import Tarea
from models_db import TareaDB, CuentaMoodleDB, EntregaDB
from database import get_db
from scraper import get_tarea
from playwright.sync_api import sync_playwright
import re
import time
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/api/tareas/{tarea_id}")
def obtener_tarea(tarea_id: int, curso_id: int = Query(None), db: Session = Depends(get_db)):
    tarea = db.query(TareaDB).filter(TareaDB.id == tarea_id).first()
    if tarea:
        return {
            "id": tarea.id,
            "cuenta_id": tarea.cuenta_id,
            "curso_id": tarea.curso_id,
            "tarea_id": tarea.tarea_id,
            "titulo": tarea.titulo,
            "descripcion": tarea.descripcion,
            "calificacion_maxima": tarea.calificacion_maxima,
            "estado": tarea.estado,
            "fecha_sincronizacion": tarea.fecha_sincronizacion,
        }
    # Si no existe, intentar sincronizar tareas del curso indicado (si se pasa curso_id)
    if curso_id is not None:
        from .cursos import sincronizar_tareas_curso
        sincronizar_tareas_curso(curso_id)
        tarea = db.query(TareaDB).filter(TareaDB.id == tarea_id).first()
        if tarea:
            return {
                "id": tarea.id,
                "cuenta_id": tarea.cuenta_id,
                "curso_id": tarea.curso_id,
                "tarea_id": tarea.tarea_id,
                "titulo": tarea.titulo,
                "descripcion": tarea.descripcion,
                "calificacion_maxima": tarea.calificacion_maxima,
                "estado": tarea.estado,
                "fecha_sincronizacion": tarea.fecha_sincronizacion,
            }
        raise HTTPException(status_code=404, detail="Tarea no encontrada tras sincronizar el curso indicado")
    raise HTTPException(status_code=404, detail="Tarea no encontrada y no se puede sincronizar porque no se conoce el curso")

@router.post("/api/tareas/{tarea_id}/sincronizar")
def sincronizar_tarea(tarea_id: int, db: Session = Depends(get_db)):
    tarea = db.query(TareaDB).filter(TareaDB.id == tarea_id).first()
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    # 2. Obtener credenciales de la cuenta Moodle asociada
    cuenta = db.query(CuentaMoodleDB).filter(CuentaMoodleDB.id == tarea.cuenta_id).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta Moodle asociada no encontrada")
    moodle_url = cuenta.moodle_url
    usuario_moodle = cuenta.usuario_moodle
    contrasena_moodle = cuenta.contrasena_moodle
    # 3. Hacer scraping bajo demanda con login
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            url_tarea = f"{moodle_url}/mod/assign/view.php?id={tarea.tarea_id}"
            tarea_data = get_tarea(browser, moodle_url, usuario_moodle, contrasena_moodle, tarea.tarea_id)
            descripcion_html = tarea_data['descripcion']
            entregas = tarea_data['entregas_pendientes']

            # Calcular el estado de la tarea según las entregas
            if not entregas:
                estado = 'sin_entregas'
            elif any(e.get('estado', '').lower().startswith('enviado') or e.get('estado', '').lower().startswith('pendiente') for e in entregas):
                estado = 'pendiente_calificar'
            else:
                estado = 'sin_pendientes'
            now_str = datetime.now().isoformat()
            db.query(TareaDB).filter(TareaDB.id == tarea_id).update({"descripcion": descripcion_html, "fecha_sincronizacion": now_str, "estado": estado})
            db.commit()
            return {"descripcion": descripcion_html, "estado": estado}
    except Exception as e:
        db.query(TareaDB).filter(TareaDB.id == tarea_id).update({"estado": "error"})
        db.commit()
        raise HTTPException(status_code=500, detail=f"Error al obtener descripción: {e}")

@router.get("/api/tareas/{tarea_id}/entregas_pendientes")
def obtener_entregas_pendientes_tarea(tarea_id: int, db: Session = Depends(get_db)):
    # Obtener todas las entregas de la base de datos para la tarea
    entregas_query = db.query(EntregaDB).filter(
        EntregaDB.tarea_id == tarea_id
    ).filter(
        (EntregaDB.estado == None) | (EntregaDB.estado.ilike("%calificar%"))
    ).order_by(EntregaDB.fecha_entrega.desc(), EntregaDB.alumno_id)
    rows = entregas_query.all()
    # Agrupar por alumno_id, fecha_entrega, estado, nombre (una entrega puede tener varios archivos)
    entregas_dict = {}
    for row in rows:
        entrega_key = (row.alumno_id, row.fecha_entrega, row.estado, row.nombre)
        if entrega_key not in entregas_dict:
            entregas_dict[entrega_key] = {
                "id": row.id,
                "alumno_id": row.alumno_id,
                "fecha_entrega": row.fecha_entrega,
                "estado": row.estado,
                "nombre": row.nombre,
                "archivos": [],
            }
        if row.file_url and row.file_name:
            entregas_dict[entrega_key]["archivos"].append({"url": row.file_url, "nombre": row.file_name})
    # Obtener la URL base de Moodle y el id de la tarea para construir el enlace manual
    tarea = db.query(TareaDB).filter(TareaDB.id == tarea_id).first()
    moodle_url = None
    tarea_id_moodle = None
    if tarea:
        cuenta = db.query(CuentaMoodleDB).filter(CuentaMoodleDB.id == tarea.cuenta_id).first()
        moodle_url = cuenta.moodle_url if cuenta else None
        tarea_id_moodle = tarea.tarea_id
    def generar_link_calificar(moodle_url, tarea_id_moodle, alumno_id):
        if moodle_url and tarea_id_moodle and alumno_id:
            return f"{moodle_url}/mod/assign/view.php?id={tarea_id_moodle}&action=grader&userid={alumno_id}"
        return None
    entregas = []
    for entrega in entregas_dict.values():
        entrega["link_calificar"] = generar_link_calificar(moodle_url, tarea_id_moodle, entrega["alumno_id"])
        entregas.append(entrega)
    return entregas


# Endpoint para iniciar la evaluación de una tarea
@router.post("/api/tareas/{tarea_id}/evaluar")
def evaluar_tarea(tarea_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Marcar la tarea como "evaluando"
    db.query(TareaDB).filter(TareaDB.id == tarea_id).update({"estado": "evaluando"})
    db.commit()
    background_tasks.add_task(evaluar_entregas_task, tarea_id)
    return {"mensaje": "Evaluación iniciada en segundo plano"}

# Endpoint para consultar el estado de la evaluación de una tarea
@router.get("/api/tareas/{tarea_id}/estado")
def estado_evaluacion_tarea(tarea_id: int, db: Session = Depends(get_db)):
    tarea = db.query(TareaDB).filter(TareaDB.id == tarea_id).first()
    return {"estado": tarea.estado if tarea else "desconocido"}

# Tarea en background para evaluar entregas
from sqlalchemy.orm import scoped_session, sessionmaker
from database import SessionLocal

def evaluar_entregas_task(tarea_id: int):
    db = SessionLocal()
    try:
        print(f"[DEBUG] Iniciando evaluación de entregas para tarea {tarea_id}")
        # Obtener todas las entregas pendientes de la tarea
        entregas = db.query(EntregaDB).filter(
            EntregaDB.tarea_id == tarea_id,
            (EntregaDB.estado == None) | (EntregaDB.estado != "evaluada")
        ).all()
        for entrega in entregas:
            print(f"[DEBUG] Evaluando entrega {entrega.id} de alumno {entrega.alumno_id}")
            # Aquí iría la llamada a la API de OpenAI/Assistants y el guardado de nota/feedback
            # Simulación de evaluación:
            entrega.nota = 10.0  # Simulación
            entrega.feedback = "¡Buen trabajo!"  # Simulación
            entrega.estado = "evaluada"
            db.commit()
        # Marcar la tarea como evaluada
        db.query(TareaDB).filter(TareaDB.id == tarea_id).update({"estado": "evaluada"})
        db.commit()
    finally:
        db.close()
    print(f"[DEBUG] Evaluación completada para tarea {tarea_id}")

@router.post("/api/tareas/{tarea_id}/ocultar")
def ocultar_tarea(tarea_id: int, db: Session = Depends(get_db)):
    tarea = db.query(TareaDB).filter(TareaDB.id == tarea_id).first()
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    tarea.oculto = True
    db.commit()
    return {"ok": True, "oculto": True}

@router.post("/api/tareas/{tarea_id}/mostrar")
def mostrar_tarea(tarea_id: int, db: Session = Depends(get_db)):
    tarea = db.query(TareaDB).filter(TareaDB.id == tarea_id).first()
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    tarea.oculto = False
    db.commit()
    return {"ok": True, "oculto": False}