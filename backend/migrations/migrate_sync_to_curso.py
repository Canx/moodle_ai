from sqlalchemy import create_engine, text
from pathlib import Path
import os

# Configuración de la base de datos
db_path = Path(__file__).parent.parent / 'moodle_llm.db'
engine = create_engine(f'sqlite:///{db_path}')

def migrate():
    # Create temporary backup of existing synchronization records
    with engine.connect() as conn:
        # Get existing sync records
        result = conn.execute(text("SELECT cuenta_id, estado, fecha, fecha_inicio, porcentaje, tipo, duracion FROM sincronizaciones"))
        sync_records = result.fetchall()
        
        # Get all courses per account
        result = conn.execute(text("SELECT id, cuenta_id FROM cursos"))
        courses = result.fetchall()
        
        # Create account -> courses mapping
        account_courses = {}
        for course_id, account_id in courses:
            if account_id not in account_courses:
                account_courses[account_id] = []
            account_courses[account_id].append(course_id)
        
        # Drop and recreate table with new schema
        conn.execute(text("""
            DROP TABLE IF EXISTS sincronizaciones_old;
            ALTER TABLE sincronizaciones RENAME TO sincronizaciones_old;
            CREATE TABLE sincronizaciones (
                cuenta_id INTEGER NOT NULL,
                curso_id INTEGER NOT NULL,
                estado TEXT NOT NULL,
                fecha TIMESTAMP NOT NULL,
                fecha_inicio TIMESTAMP,
                porcentaje FLOAT NOT NULL DEFAULT 0.0,
                tipo TEXT,
                duracion FLOAT,
                PRIMARY KEY (cuenta_id, curso_id),
                FOREIGN KEY(cuenta_id) REFERENCES cuentas_moodle(id) ON DELETE CASCADE,
                FOREIGN KEY(curso_id) REFERENCES cursos(id) ON DELETE CASCADE
            );
        """))
        
        # For each old sync record, create new records for all courses of that account
        for sync in sync_records:
            account_id = sync[0]
            if account_id in account_courses:
                for course_id in account_courses[account_id]:
                    conn.execute(
                        text("""
                            INSERT INTO sincronizaciones 
                            (cuenta_id, curso_id, estado, fecha, fecha_inicio, porcentaje, tipo, duracion)
                            VALUES (:cuenta_id, :curso_id, :estado, :fecha, :fecha_inicio, :porcentaje, :tipo, :duracion)
                        """),
                        {
                            "cuenta_id": account_id,
                            "curso_id": course_id,
                            "estado": sync[1],
                            "fecha": sync[2],
                            "fecha_inicio": sync[3],
                            "porcentaje": sync[4],
                            "tipo": sync[5],
                            "duracion": sync[6]
                        }
                    )
        
        # Drop old table
        conn.execute(text("DROP TABLE sincronizaciones_old;"))
        
if __name__ == '__main__':
    migrate()
