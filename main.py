# backend/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import sqlite3

app = FastAPI()

# Conexión con la base de datos SQLite
conn = sqlite3.connect("moodle_llm.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS profesores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT,
    token TEXT,
    moodle_url TEXT
)
''')
conn.commit()

class ProfesorInput(BaseModel):
    nombre: str
    token: str
    moodle_url: str

class Curso(BaseModel):
    profesor_id: int

@app.post("/registrar_profesor")
def registrar_profesor(datos: ProfesorInput):
    cursor.execute("INSERT INTO profesores (nombre, token, moodle_url) VALUES (?, ?, ?)",
                   (datos.nombre, datos.token, datos.moodle_url))
    conn.commit()
    return {"mensaje": "Profesor registrado correctamente"}

@app.get("/cursos/{profesor_id}")
def obtener_cursos(profesor_id: int):
    cursor.execute("SELECT token, moodle_url FROM profesores WHERE id = ?", (profesor_id,))
    fila = cursor.fetchone()
    if not fila:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")

    token, url = fila
    params = {
        'wstoken': token,
        'wsfunction': 'core_course_get_courses',
        'moodlewsrestformat': 'json'
    }
    response = requests.get(f"{url}/webservice/rest/server.php", params=params)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Error al conectar con Moodle")

    cursos = response.json()
    return cursos

