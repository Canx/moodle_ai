# backend/main.py
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import sqlite3
import requests
from fastapi.middleware.cors import CORSMiddleware
from scraper import obtener_cursos_desde_moodle
from endpoints import usuarios, cuentas, cursos

app = FastAPI()
app.include_router(usuarios.router)
app.include_router(cuentas.router)
app.include_router(cursos.router)

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
        curso_id INTEGER NOT NULL,
        titulo TEXT NOT NULL,
        url TEXT,
        FOREIGN KEY (curso_id) REFERENCES cursos (id)
    )
''')

# Crear tabla sincronizaciones si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sincronizaciones (
        cuenta_id INTEGER PRIMARY KEY,
        estado TEXT NOT NULL
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