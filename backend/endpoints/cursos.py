from fastapi import APIRouter, HTTPException
from database import cursor
# Importa aquí tu función de scraping si la necesitas

router = APIRouter()

@router.get("/api/cursos")
def obtener_cursos():
    cursor.execute("SELECT id, nombre FROM cursos")
    cursos = cursor.fetchall()
    return [{"id": c[0], "nombre": c[1]} for c in cursos]

@router.get("/api/cursos/{curso_id}/tareas")
def obtener_tareas_curso(curso_id: int):
    # Aquí deberías llamar a tu función de scraping o consultar la base de datos
    # Ejemplo ficticio:
    cursor.execute("SELECT nombre, enlace FROM tareas WHERE curso_id = ?", (curso_id,))
    tareas = cursor.fetchall()
    return [{"nombre": t[0], "enlace": t[1]} for t in tareas]