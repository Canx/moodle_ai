# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from endpoints import usuarios, cuentas, cursos, tareas
from database import Base, engine
from models_db import UsuarioDB

app = FastAPI()
app.include_router(usuarios.router)
app.include_router(cuentas.router)
app.include_router(cursos.router)
app.include_router(tareas.router)

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

# (Las tablas se gestionan ahora con SQLAlchemy y Base.metadata.create_all)