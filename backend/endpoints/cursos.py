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
            for tarea in tareas:
                cursor.execute(
                    "INSERT INTO tareas (cuenta_id, curso_id, tarea_id, titulo) VALUES (?, ?, ?, ?)",
                    (cuenta_id, curso_id, tarea["tarea_id"], tarea["titulo"])
                )
            from database import connection
            connection.commit()
            browser.close()
        return {"mensaje": "Tareas sincronizadas", "tareas": tareas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al sincronizar tareas: {e}")

@router.get("/api/cursos/{curso_id}/tareas")
def obtener_tareas_curso(curso_id: int):
    cursor.execute(
        "SELECT id, tarea_id, titulo, descripcion FROM tareas WHERE curso_id = ?",
        (curso_id,)
    )
    tareas = cursor.fetchall()
    return [{"id": t[0], "tarea_id": t[1], "titulo": t[2], "descripcion": t[3]} for t in tareas]  # url se genera en frontend