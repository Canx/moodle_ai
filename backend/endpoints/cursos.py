from fastapi import APIRouter, HTTPException
from database import cursor
from scraper import get_tareas_de_curso, login_moodle
from playwright.sync_api import sync_playwright

router = APIRouter()

@router.get("/api/cursos")
def obtener_cursos():
    cursor.execute("SELECT id, nombre FROM cursos")
    cursos = cursor.fetchall()
    return [{"id": c[0], "nombre": c[1]} for c in cursos]

@router.post("/api/cursos/{curso_id}/sincronizar_tareas")
def sincronizar_tareas_curso(curso_id: int):
    # Obtener cuenta asociada al curso
    cursor.execute("SELECT cuenta_id, url FROM cursos WHERE id = ?", (curso_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    cuenta_id, url_curso = row
    cursor.execute("SELECT usuario_moodle, contrasena_moodle, moodle_url FROM cuentas_moodle WHERE id = ?", (cuenta_id,))
    cuenta = cursor.fetchone()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    usuario, contrasena, moodle_url = cuenta
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            login_moodle(page, moodle_url, usuario, contrasena)
            # Recuperar objeto curso necesario para get_tareas_de_curso
            cursor.execute("SELECT nombre, url FROM cursos WHERE id = ?", (curso_id,))
            curso_row = cursor.fetchone()
            curso_obj = {"nombre": curso_row[0], "url": curso_row[1]}
            tareas = get_tareas_de_curso(browser, page, moodle_url, cuenta_id, curso_obj)
            # Borrar tareas previas del curso
            cursor.execute("DELETE FROM tareas WHERE curso_id = ?", (curso_id,))
            # Borrar entregas antiguas de todas las tareas de este curso
            cursor.execute("SELECT id FROM tareas WHERE curso_id = ?", (curso_id,))
            tarea_ids = [row[0] for row in cursor.fetchall()]
            if tarea_ids:
                cursor.execute(f"DELETE FROM entregas WHERE tarea_id IN ({','.join(['?']*len(tarea_ids))})", tarea_ids)

            for tarea in tareas:
                # Determinar el estado de la tarea
                entregas = tarea.get('entregas_pendientes', [])
                if not entregas:
                    estado = 'sin_entregas'
                elif any(e.get('estado', '').lower().startswith('enviado') or e.get('estado', '').lower().startswith('pendiente') for e in entregas):
                    estado = 'pendiente_calificar'
                else:
                    estado = 'sin_pendientes'
                cursor.execute(
                    "INSERT OR REPLACE INTO tareas (cuenta_id, curso_id, tarea_id, titulo, estado, calificacion_maxima) VALUES (?, ?, ?, ?, ?, ?)",
                    (cuenta_id, curso_id, tarea["tarea_id"], tarea["titulo"], estado, tarea.get("calificacion_maxima"))
                )
                print(f"[DEBUG] Entregas pendientes para tarea '{tarea['titulo']}': {len(tarea.get('entregas_pendientes', []))}")
                # Guardar entregas en la tabla entregas
                cursor.execute("SELECT id FROM tareas WHERE curso_id = ? AND tarea_id = ?", (curso_id, tarea["tarea_id"]))
                tarea_db_row = cursor.fetchone()
                tarea_db_id = tarea_db_row[0] if tarea_db_row else None
                if tarea_db_id:
                    for entrega in tarea.get('entregas_pendientes', []):
                        cursor.execute(
                            "INSERT OR IGNORE INTO entregas (tarea_id, alumno_id, fecha_entrega, file_url, file_name, estado) VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                tarea_db_id,
                                entrega["alumno_id"],
                                entrega["fecha_entrega"],
                                entrega["archivos"][0]["url"] if entrega["archivos"] else None,
                                entrega["archivos"][0]["nombre"] if entrega["archivos"] else None,
                                entrega["estado"]
                            )
                        )
            from database import conn
            conn.commit()
            browser.close()
        return {"mensaje": "Tareas sincronizadas", "tareas": tareas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al sincronizar tareas: {e}")

@router.get("/api/cursos/{curso_id}/tareas")
def obtener_tareas_curso(curso_id: int):
    cursor.execute(
        "SELECT id, tarea_id, titulo, descripcion, estado FROM tareas WHERE curso_id = ?",
        (curso_id,)
    )
    tareas = cursor.fetchall()
    return [{"id": t[0], "tarea_id": t[1], "titulo": t[2], "descripcion": t[3], "estado": t[4]} for t in tareas]  # url se genera en frontend