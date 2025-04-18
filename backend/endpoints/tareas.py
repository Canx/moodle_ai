# backend/endpoints/tareas.py

from fastapi import APIRouter, HTTPException, BackgroundTasks
from database import cursor, conn
from models import Tarea
from datetime import datetime, timedelta
from scraper import sync_playwright, get_descripcion_tarea
import re
import time

router = APIRouter()

from fastapi import Query

@router.get("/api/tareas/{tarea_id}")
def obtener_tarea(tarea_id: int, curso_id: int = Query(None)):
    cursor.execute("SELECT id, cuenta_id, curso_id, tarea_id, titulo, descripcion FROM tareas WHERE id = ?", (tarea_id,))
    row = cursor.fetchone()
    if row:
        return {"id": row[0], "cuenta_id": row[1], "curso_id": row[2], "tarea_id": row[3], "titulo": row[4], "descripcion": row[5]}
    # Si no existe, intentar sincronizar tareas del curso indicado (si se pasa curso_id)
    if curso_id is not None:
        from .cursos import sincronizar_tareas_curso
        sincronizar_tareas_curso(curso_id)
        cursor.execute("SELECT id, cuenta_id, curso_id, tarea_id, titulo, descripcion FROM tareas WHERE id = ?", (tarea_id,))
        row = cursor.fetchone()
        if row:
            return {"id": row[0], "cuenta_id": row[1], "curso_id": row[2], "tarea_id": row[3], "titulo": row[4], "descripcion": row[5]}
        raise HTTPException(status_code=404, detail="Tarea no encontrada tras sincronizar el curso indicado")
    raise HTTPException(status_code=404, detail="Tarea no encontrada y no se puede sincronizar porque no se conoce el curso")


@router.get("/api/tareas/{tarea_id}/descripcion")
def obtener_descripcion_tarea(tarea_id: int):
    # 1. Obtener la tarea y la cuenta asociada
    cursor.execute("SELECT id, cuenta_id, tarea_id, descripcion, fecha_sincronizacion, estado FROM tareas WHERE id = ?", (tarea_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    id, cuenta_id, tarea_id_moodle, descripcion, fecha_sincronizacion, estado = row
    # 2. Si la descripción existe y es reciente (<3 días), devolverla
    if descripcion and fecha_sincronizacion:
        try:
            fecha_dt = datetime.fromisoformat(fecha_sincronizacion)
            if fecha_dt > datetime.now() - timedelta(days=3):
                return {"descripcion": descripcion, "estado": "ok"}
        except Exception:
            pass
    # 3. Obtener credenciales de la cuenta Moodle asociada
    cursor.execute("SELECT moodle_url, usuario_moodle, contrasena_moodle FROM cuentas_moodle WHERE id = ?", (cuenta_id,))
    cuenta = cursor.fetchone()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta Moodle asociada no encontrada")
    moodle_url, usuario_moodle, contrasena_moodle = cuenta
    # 4. Hacer scraping bajo demanda con login
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            url_tarea = f"{moodle_url}/mod/assign/view.php?id={tarea_id_moodle}"
            descripcion_html = get_descripcion_tarea(browser, moodle_url, usuario_moodle, contrasena_moodle, url_tarea)
            browser.close()
        # Actualizar en base de datos
        now_str = datetime.now().isoformat()
        cursor.execute("UPDATE tareas SET descripcion = ?, fecha_sincronizacion = ?, estado = ? WHERE id = ?", (descripcion_html, now_str, "ok", tarea_id))
        conn.commit()
        return {"descripcion": descripcion_html, "estado": "ok"}
    except Exception as e:
        cursor.execute("UPDATE tareas SET estado = ? WHERE id = ?", ("error", tarea_id))
        conn.commit()
        raise HTTPException(status_code=500, detail=f"Error al obtener descripción: {e}")

# Endpoint para iniciar la evaluación de una tarea
@router.post("/api/tareas/{tarea_id}/evaluar")
def evaluar_tarea(tarea_id: int, background_tasks: BackgroundTasks):
    # Marcar la tarea como "evaluando"
    cursor.execute(
        "UPDATE tareas SET estado = ? WHERE id = ?",
        ("evaluando", tarea_id)
    )
    conn.commit()
    background_tasks.add_task(evaluar_entregas_task, tarea_id)
    return {"mensaje": "Evaluación iniciada en segundo plano"}

# Endpoint para consultar el estado de la evaluación de una tarea
@router.get("/api/tareas/{tarea_id}/estado")
def estado_evaluacion_tarea(tarea_id: int):
    cursor.execute(
        "SELECT estado FROM tareas WHERE id = ?",
        (tarea_id,)
    )
    row = cursor.fetchone()
    return {"estado": row[0] if row else "desconocido"}

# Endpoint para subir notas a Moodle (placeholder)
@router.post("/api/tareas/{tarea_id}/subir_notas")
def subir_notas_tarea(tarea_id: int):
    # Aquí iría la lógica para subir las notas a Moodle
    return {"mensaje": "Funcionalidad de subida de notas pendiente de implementar"}

# Tarea en background para evaluar entregas
def evaluar_entregas_task(tarea_id: int):
    print(f"[DEBUG] Iniciando evaluación de entregas para tarea {tarea_id}")
    # Obtener todas las entregas pendientes de la tarea
    cursor.execute(
        "SELECT id, alumno_id, contenido FROM entregas WHERE tarea_id = ? AND (estado IS NULL OR estado != ?)",
        (tarea_id, "evaluada")
    )
    entregas = cursor.fetchall()
    for entrega in entregas:
        entrega_id, alumno_id, contenido = entrega
        print(f"[DEBUG] Evaluando entrega {entrega_id} de alumno {alumno_id}")
        # Aquí iría la llamada a la API de OpenAI/Assistants y el guardado de nota/feedback
        # Simulación de evaluación:
        nota = 10.0  # Simulación
        feedback = "¡Buen trabajo!"  # Simulación
        time.sleep(1)  # Simula tiempo de evaluación
        cursor.execute(
            "UPDATE entregas SET estado = ?, nota = ?, feedback = ? WHERE id = ?",
            ("evaluada", nota, feedback, entrega_id)
        )
        conn.commit()
    # Marcar la tarea como evaluada
    cursor.execute(
        "UPDATE tareas SET estado = ? WHERE id = ?",
        ("evaluada", tarea_id)
    )
    conn.commit()
    print(f"[DEBUG] Evaluación completada para tarea {tarea_id}")