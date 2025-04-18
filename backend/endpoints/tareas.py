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
            from scraper import get_tarea
            tarea_data = get_tarea(browser, moodle_url, usuario_moodle, contrasena_moodle, tarea_id_moodle)
            descripcion_html = tarea_data['descripcion']
            entregas = tarea_data['entregas_pendientes']

            from database import cursor as db_cursor
            db_cursor.execute("SELECT id FROM tareas WHERE tarea_id = ? AND cuenta_id = ?", (tarea_id_moodle, cuenta_id))
            tarea_db_row = db_cursor.fetchone()
            tarea_db_id = tarea_db_row[0] if tarea_db_row else None
            if tarea_db_id:
                db_cursor.execute("DELETE FROM entregas WHERE tarea_id = ?", (tarea_db_id,))
                for entrega in entregas:
                    db_cursor.execute(
                        "INSERT OR IGNORE INTO entregas (tarea_id, alumno_id, fecha_entrega, file_url, file_name, estado, nombre) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            tarea_db_id,
                            entrega["alumno_id"],
                            entrega["fecha_entrega"],
                            entrega["archivos"][0]["url"] if entrega["archivos"] else None,
                            entrega["archivos"][0]["nombre"] if entrega["archivos"] else None,
                            entrega["estado"],
                            entrega["nombre"]
                        )
                    )
                from database import conn as db_conn
                db_conn.commit()
            browser.close()
        # Calcular el estado de la tarea según las entregas
        if not entregas:
            estado = 'sin_entregas'
        elif any(e.get('estado', '').lower().startswith('enviado') or e.get('estado', '').lower().startswith('pendiente') for e in entregas):
            estado = 'pendiente_calificar'
        else:
            estado = 'sin_pendientes'
        now_str = datetime.now().isoformat()
        cursor.execute("UPDATE tareas SET descripcion = ?, fecha_sincronizacion = ?, estado = ? WHERE id = ?", (descripcion_html, now_str, estado, tarea_id))
        conn.commit()
        return {"descripcion": descripcion_html, "estado": estado}
    except Exception as e:
        cursor.execute("UPDATE tareas SET estado = ? WHERE id = ?", ("error", tarea_id))
        conn.commit()
        raise HTTPException(status_code=500, detail=f"Error al obtener descripción: {e}")

@router.get("/api/tareas/{tarea_id}/entregas_pendientes")
def obtener_entregas_pendientes_tarea(tarea_id: int):
    cursor.execute(
        "SELECT id, alumno_id, fecha_entrega, file_url, file_name, estado, nombre FROM entregas WHERE tarea_id = ? AND (estado IS NULL OR estado LIKE '%calificar%') ORDER BY fecha_entrega DESC",
        (tarea_id,)
    )
    entregas = cursor.fetchall()
    # Obtener la URL base de Moodle y el id de la tarea para construir el enlace manual
    cursor.execute("SELECT cuenta_id, tarea_id FROM tareas WHERE id = ?", (tarea_id,))
    tarea_row = cursor.fetchone()
    moodle_url = None
    tarea_id_moodle = None
    if tarea_row:
        cuenta_id, tarea_id_moodle = tarea_row
        cursor.execute("SELECT moodle_url FROM cuentas_moodle WHERE id = ?", (cuenta_id,))
        cuenta_row = cursor.fetchone()
        if cuenta_row:
            moodle_url = cuenta_row[0]
    def generar_link_calificar(moodle_url, tarea_id_moodle, alumno_id):
        if moodle_url and tarea_id_moodle and alumno_id:
            return f"{moodle_url}/mod/assign/view.php?id={tarea_id_moodle}&action=grader&userid={alumno_id}"
        return None
    return [
        {
            "id": row[0],
            "alumno_id": row[1],
            "fecha_entrega": row[2],
            "file_url": row[3],
            "file_name": row[4],
            "estado": row[5],
            "nombre": row[6],
            "link_calificar": generar_link_calificar(moodle_url, tarea_id_moodle, row[1])
        }
        for row in entregas
    ]

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