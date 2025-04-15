# backend/main.py
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import sqlite3
import requests
from fastapi.middleware.cors import CORSMiddleware
from scraper import obtener_cursos_desde_moodle

app = FastAPI()
db = sqlite3.connect("database.db", check_same_thread=False)
cursor = db.cursor()
# Conexión con la base de datos SQLite
conn = sqlite3.connect("moodle_llm.db", check_same_thread=False)
cursor = conn.cursor()

# Crear tabla usuarios si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        correo TEXT NOT NULL UNIQUE,
        contrasena TEXT NOT NULL
    )
''')

# Crear tabla cuentas_moodle si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS cuentas_moodle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        moodle_url TEXT NOT NULL,
        usuario_moodle TEXT NOT NULL,
        contrasena_moodle TEXT NOT NULL,
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
    )
''')

conn.commit()

# CORS para frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos
class Usuario(BaseModel):
    nombre: str
    correo: str
    contrasena: str

class CuentaMoodle(BaseModel):
    moodle_url: str
    usuario_moodle: str
    contrasena_moodle: str

# Endpoint para registrar usuarios
@app.post("/api/usuarios")
def registrar_usuario(usuario: Usuario):
    try:
        cursor.execute(
            "INSERT INTO usuarios (nombre, correo, contrasena) VALUES (?, ?, ?)",
            (usuario.nombre, usuario.correo, usuario.contrasena),
        )
        db.commit()
        return {"mensaje": "Usuario registrado exitosamente"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

# Endpoint para agregar cuentas de Moodle
@app.post("/api/usuarios/{usuario_id}/cuentas")
def agregar_cuenta_moodle(usuario_id: int, cuenta: CuentaMoodle):
    cursor.execute(
        "INSERT INTO cuentas_moodle (usuario_id, moodle_url, usuario_moodle, contrasena_moodle) VALUES (?, ?, ?, ?)",
        (usuario_id, cuenta.moodle_url, cuenta.usuario_moodle, cuenta.contrasena_moodle),
    )
    db.commit()
    return {"mensaje": "Cuenta de Moodle agregada exitosamente"}

# Endpoint para obtener cuentas de Moodle de un usuario
@app.get("/api/usuarios/{usuario_id}/cuentas")
def obtener_cuentas_moodle(usuario_id: int):
    cursor.execute(
        "SELECT id, moodle_url, usuario_moodle FROM cuentas_moodle WHERE usuario_id = ?",
        (usuario_id,),
    )
    cuentas = cursor.fetchall()
    return [{"id": c[0], "moodle_url": c[1], "usuario_moodle": c[2]} for c in cuentas]


# Endpoint para obtener cursos de un profesor
@app.get("/cursos/{profesor_id}")
def obtener_cursos(profesor_id: int):
    cursor.execute("SELECT usuario, contrasena, moodle_url FROM profesores WHERE id = ?", (profesor_id,))
    fila = cursor.fetchone()
    if not fila:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")

    usuario, contrasena, moodle_url = fila

    try:
        cursos = obtener_cursos_desde_moodle(usuario, contrasena, moodle_url)
        return cursos
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener cursos: {str(e)}")


def obtener_tareas_desde_moodle(usuario: str, contrasena: str, moodle_url: str, curso_id: int):
    """
    Función de scraping para obtener las tareas de un curso específico desde Moodle.
    """
    import requests
    from bs4 import BeautifulSoup

    # Simular inicio de sesión en Moodle
    session = requests.Session()
    login_url = f"{moodle_url}/login/index.php"
    login_response = session.post(login_url, data={"username": usuario, "password": contrasena})

    if login_response.status_code != 200 or "login" in login_response.url:
        raise Exception("Inicio de sesión fallido. Verifica las credenciales.")

    # Acceder a la página del curso
    curso_url = f"{moodle_url}/course/view.php?id={curso_id}"
    response = session.get(curso_url)
    if response.status_code != 200:
        raise Exception("No se pudo acceder al curso. Verifica el ID del curso.")

    # Parsear la página para obtener las tareas
    soup = BeautifulSoup(response.text, "html.parser")
    tareas = []
    for tarea in soup.select(".activity.assign"):
        nombre = tarea.select_one(".instancename").text.strip()
        enlace = tarea.find("a")["href"]
        tareas.append({"nombre": nombre, "enlace": enlace})

    return tareas



