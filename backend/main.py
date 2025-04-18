# backend/main.py
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import sqlite3
import requests
from fastapi.middleware.cors import CORSMiddleware
from endpoints import usuarios, cuentas, cursos, tareas

app = FastAPI()
app.include_router(usuarios.router)
app.include_router(cuentas.router)
app.include_router(cursos.router)
app.include_router(tareas.router)

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

# Crear tabla cursos si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS cursos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cuenta_id INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        url TEXT,
        FOREIGN KEY (cuenta_id) REFERENCES cuentas_moodle (id)
    )
''')

# Crear tabla tareas si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tareas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cuenta_id INTEGER NOT NULL,
        curso_id INTEGER NOT NULL,
        tarea_id INTEGER NOT NULL,
        titulo TEXT NOT NULL,
        descripcion TEXT,
        rubrica TEXT,
        fecha_sincronizacion TEXT,
        estado TEXT,
        FOREIGN KEY (cuenta_id) REFERENCES cuentas_moodle (id),
        FOREIGN KEY (curso_id) REFERENCES cursos (id),
        UNIQUE (curso_id, tarea_id)
    )
''')

# Crear tabla sincronizaciones si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sincronizaciones (
        cuenta_id INTEGER PRIMARY KEY,
        estado TEXT NOT NULL
    )
''')

# Crear tabla entregas si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS entregas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarea_id INTEGER NOT NULL,
        alumno_id TEXT NOT NULL,
        fecha_entrega TEXT,
        contenido TEXT,
        file_url TEXT,
        file_name TEXT,
        file_id TEXT,
        estado TEXT,
        nota REAL,
        feedback TEXT,
        FOREIGN KEY (tarea_id) REFERENCES tareas (id),
        UNIQUE (tarea_id, alumno_id)
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