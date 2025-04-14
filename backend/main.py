# backend/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import requests
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS para frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conexión con la base de datos SQLite
conn = sqlite3.connect("moodle_llm.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS profesores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT,
    contrasena TEXT,
    moodle_url TEXT
)
''')
conn.commit()

class ProfesorInput(BaseModel):
    usuario: str
    contrasena: str
    moodle_url: str

@app.post("/registrar_profesor")
def registrar_profesor(datos: ProfesorInput):
    cursor.execute("INSERT INTO profesores (usuario, contrasena, moodle_url) VALUES (?, ?, ?)",
                   (datos.usuario, datos.contrasena, datos.moodle_url))
    conn.commit()
    return {"mensaje": "Profesor registrado correctamente"}

@app.get("/cursos/{profesor_id}")
def obtener_cursos(profesor_id: int):
    cursor.execute("SELECT usuario, contrasena, moodle_url FROM profesores WHERE id = ?", (profesor_id,))
    fila = cursor.fetchone()
    if not fila:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")

    usuario, contrasena, moodle_url = fila

    # Aquí más adelante haremos el scraping con Playwright
    # Por ahora solo simulamos el resultado
    cursos_simulados = [
        {"id": 1, "fullname": "Matemáticas 4ESO"},
        {"id": 2, "fullname": "Historia Contemporánea"},
    ]

    return cursos_simulados


