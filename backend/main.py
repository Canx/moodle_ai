# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from endpoints import usuarios, cuentas, cursos, tareas, llm_configs
from database import Base, engine
from models_db import UsuarioDB
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()
app.include_router(usuarios.router)
app.include_router(cuentas.router)
app.include_router(cursos.router)
app.include_router(tareas.router)
app.include_router(llm_configs.router)

# Crear todas las tablas al arrancar
Base.metadata.create_all(bind=engine)

# CORS para frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Asegurar que el directorio exista
os.makedirs("downloads", exist_ok=True)

# Servir archivos descargados (entregas)
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

# (Las tablas se gestionan ahora con SQLAlchemy y Base.metadata.create_all)