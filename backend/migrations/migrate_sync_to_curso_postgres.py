from sqlalchemy import create_engine, text
import os

# Configuración de la base de datos PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://moodle_user:moodle_pass@db:5432/moodle_llm')
engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        # Obtener registros existentes
        result = conn.execute(text("""
            SELECT cuenta_id, estado, fecha, fecha_inicio, porcentaje, tipo, duracion 
            FROM sincronizaciones
        """))
        sync_records = list(result.fetchall())
        
        # Obtener todos los cursos por cuenta
        result = conn.execute(text("SELECT id, cuenta_id FROM cursos"))
        courses = result.fetchall()
        
        # Crear mapeo cuenta -> cursos
        account_courses = {}
        for course_id, account_id in courses:
            if account_id not in account_courses:
                account_courses[account_id] = []
            account_courses[account_id].append(course_id)

        # Crear tabla temporal con la nueva estructura
        conn.execute(text("""
            CREATE TABLE sincronizaciones_new (
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
        
        # Insertar datos en la nueva tabla
        for sync in sync_records:
            account_id = sync[0]
            if account_id in account_courses:
                for course_id in account_courses[account_id]:
                    conn.execute(
                        text("""
                            INSERT INTO sincronizaciones_new 
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

        # Eliminamos los constraint de la tabla original
        conn.execute(text("""
            ALTER TABLE sincronizaciones DROP CONSTRAINT IF EXISTS sincronizaciones_pkey CASCADE;
        """))
        
        # Renombramos las tablas
        conn.execute(text("ALTER TABLE sincronizaciones RENAME TO sincronizaciones_old;"))
        conn.execute(text("ALTER TABLE sincronizaciones_new RENAME TO sincronizaciones;"))
        
        # Eliminamos la tabla antigua
        conn.execute(text("DROP TABLE sincronizaciones_old;"))
        
        conn.commit()
        print("Migration completed successfully")

if __name__ == '__main__':
    migrate()
