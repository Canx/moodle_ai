# backend/endpoints/tareas.py

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session
from models import Tarea
from models_db import TareaDB, CuentaMoodleDB, EntregaDB
from database import get_db
from tasks import run_sync_tarea_task
import re
import time
from datetime import datetime, timedelta
import json

router = APIRouter()

@router.get("/api/tareas/{tarea_id}")
def obtener_tarea(tarea_id: int, curso_id: int = Query(None), db: Session = Depends(get_db)):
    tarea = db.query(TareaDB).filter(TareaDB.id == tarea_id).first()
    if tarea:
        # Construir enlace a la tarea en Moodle
        cuenta = db.query(CuentaMoodleDB).filter(CuentaMoodleDB.id == tarea.cuenta_id).first()
        link_tarea = f"{cuenta.moodle_url}/mod/assign/view.php?id={tarea.tarea_id}" if cuenta else None
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
            "tipo_calificacion": tarea.tipo_calificacion,
            "detalles_calificacion": tarea.detalles_calificacion,
            "link_tarea": link_tarea
        }
    # Si no existe, intentar sincronizar tareas del curso indicado (si se pasa curso_id)
    if curso_id is not None:
        from .cursos import sincronizar_tareas_curso
        sincronizar_tareas_curso(curso_id)
        tarea = db.query(TareaDB).filter(TareaDB.id == tarea_id).first()
        if tarea:
            cuenta = db.query(CuentaMoodleDB).filter(CuentaMoodleDB.id == tarea.cuenta_id).first()
            link_tarea = f"{cuenta.moodle_url}/mod/assign/view.php?id={tarea.tarea_id}" if cuenta else None
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
                "tipo_calificacion": tarea.tipo_calificacion,
                "detalles_calificacion": tarea.detalles_calificacion,
                "link_tarea": link_tarea
            }
        raise HTTPException(status_code=404, detail="Tarea no encontrada tras sincronizar el curso indicado")
    raise HTTPException(status_code=404, detail="Tarea no encontrada y no se puede sincronizar porque no se conoce el curso")

@router.post("/api/tareas/{tarea_id}/sincronizar", status_code=202)
def sincronizar_tarea(tarea_id: int):
    """Encola sincronización de una tarea en segundo plano vía Celery"""
    run_sync_tarea_task.delay(tarea_id)
    return {"mensaje": "Sincronización de tarea en segundo plano iniciada"}

@router.get("/api/tareas/{tarea_id}/entregas_pendientes")
def obtener_entregas_pendientes_tarea(tarea_id: int, db: Session = Depends(get_db)):
    # Obtener todas las entregas de la base de datos para la tarea
    entregas_query = db.query(EntregaDB).filter(
        EntregaDB.tarea_id == tarea_id
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
                "nota": row.nota,
                "feedback": row.feedback,
                "texto": row.contenido,
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
            # Descargar archivo si existe
            if entrega.file_url:
                import os, requests
                download_dir = os.path.join("downloads", str(tarea_id), str(entrega.id))
                os.makedirs(download_dir, exist_ok=True)
                local_path = os.path.join(download_dir, entrega.file_name or os.path.basename(entrega.file_url))
                try:
                    r = requests.get(entrega.file_url)
                    with open(local_path, "wb") as f:
                        f.write(r.content)
                    print(f"[DEBUG] Archivo descargado en {local_path}")
                except Exception as err:
                    print(f"[ERROR] No se pudo descargar {entrega.file_url}: {err}")
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