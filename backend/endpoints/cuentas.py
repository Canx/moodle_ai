from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from models import CuentaMoodle
from models_db import CuentaMoodleDB
from database import get_db, engine
from scraper import sincronizar_cursos_y_tareas
from services.scraper_service import scrape_courses
import re

router = APIRouter()

@router.get("/api/usuarios/{usuario_id}/cuentas")
def obtener_cuentas(usuario_id: int, db: Session = Depends(get_db)):
    cuentas = db.query(CuentaMoodleDB).filter(CuentaMoodleDB.usuario_id == usuario_id).all()
    return [
        {"id": c.id, "moodle_url": c.moodle_url, "usuario_moodle": c.usuario_moodle}
        for c in cuentas
    ]

@router.get("/api/usuarios/{usuario_id}/cuentas/{cuenta_id}")
def obtener_cuenta(usuario_id: int, cuenta_id: int, db: Session = Depends(get_db)):
    cuenta = db.query(CuentaMoodleDB).filter(
        CuentaMoodleDB.id == cuenta_id,
        CuentaMoodleDB.usuario_id == usuario_id
    ).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return {
        "id": cuenta.id,
        "moodle_url": cuenta.moodle_url,
        "usuario_moodle": cuenta.usuario_moodle
    }

@router.post("/api/usuarios/{usuario_id}/cuentas")
def agregar_cuenta(usuario_id: int, cuenta: CuentaMoodle, db: Session = Depends(get_db)):
    nueva_cuenta = CuentaMoodleDB(
        usuario_id=usuario_id,
        moodle_url=cuenta.moodle_url,
        usuario_moodle=cuenta.usuario_moodle,
        contrasena_moodle=cuenta.contrasena_moodle
    )
    db.add(nueva_cuenta)
    db.commit()
    db.refresh(nueva_cuenta)
    return {"mensaje": "Cuenta de Moodle agregada exitosamente"}

@router.put("/api/usuarios/{usuario_id}/cuentas/{cuenta_id}")
def editar_cuenta(usuario_id: int, cuenta_id: int, cuenta: CuentaMoodle, db: Session = Depends(get_db)):
    cuenta_db = db.query(CuentaMoodleDB).filter(CuentaMoodleDB.id == cuenta_id, CuentaMoodleDB.usuario_id == usuario_id).first()
    if not cuenta_db:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    cuenta_db.moodle_url = cuenta.moodle_url
    cuenta_db.usuario_moodle = cuenta.usuario_moodle
    cuenta_db.contrasena_moodle = cuenta.contrasena_moodle
    db.commit()
    return {"mensaje": "Cuenta de Moodle actualizada exitosamente"}

@router.delete("/api/usuarios/{usuario_id}/cuentas/{cuenta_id}")
def borrar_cuenta(usuario_id: int, cuenta_id: int, db: Session = Depends(get_db)):
    cuenta_db = db.query(CuentaMoodleDB).filter(CuentaMoodleDB.id == cuenta_id, CuentaMoodleDB.usuario_id == usuario_id).first()
    if not cuenta_db:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    
    # Usar una conexión raw para operaciones que requieren SQL directo
    conn = engine.raw_connection()
    cursor = conn.cursor()
    try:
        # Eliminar registros relacionados en orden
        cursor.execute("DELETE FROM sincronizaciones WHERE cuenta_id = %s", (cuenta_id,))
        cursor.execute("DELETE FROM entregas WHERE tarea_id IN (SELECT id FROM tareas WHERE curso_id IN (SELECT id FROM cursos WHERE cuenta_id = %s))", (cuenta_id,))
        cursor.execute("DELETE FROM tareas WHERE curso_id IN (SELECT id FROM cursos WHERE cuenta_id = %s)", (cuenta_id,))
        cursor.execute("DELETE FROM cursos WHERE cuenta_id = %s", (cuenta_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar datos relacionados: {str(e)}")
    finally:
        cursor.close()
        conn.close()

    # Ahora sí podemos eliminar la cuenta
    db.delete(cuenta_db)
    db.commit()
    return {"mensaje": "Cuenta de Moodle eliminada exitosamente"}

def sync_task(usuario, contrasena, url, cuenta_id):
    # Raw SQL connection para sincronizaciones
    conn = engine.raw_connection()
    cursor = conn.cursor()
    print(f"[DEBUG] sync_task lanzado para cuenta {cuenta_id}")
    # Marcar como "sincronizando"
    cursor.execute(
        "INSERT INTO sincronizaciones (cuenta_id, estado, fecha) VALUES (%s, %s, NOW()) ON CONFLICT (cuenta_id) DO UPDATE SET estado = EXCLUDED.estado, fecha = NOW()",
        (cuenta_id, "sincronizando")
    )
    conn.commit()
    try:
        print("[DEBUG] Antes de llamar a sincronizar_cursos_y_tareas")
        cursos, tareas_por_curso = sincronizar_cursos_y_tareas(cuenta_id, usuario, contrasena, url)
        print(f"[DEBUG] Cursos obtenidos: {len(cursos)}")

        # Eliminar cursos y tareas anteriores de esta cuenta
        cursor.execute("DELETE FROM tareas WHERE curso_id IN (SELECT id FROM cursos WHERE cuenta_id = %s)", (cuenta_id,))
        cursor.execute("DELETE FROM cursos WHERE cuenta_id = %s", (cuenta_id,))

        # Insertar cursos y mapear id real de Moodle a id en la base de datos
        curso_id_map = {}
        for curso in cursos:
            cursor.execute(
                "INSERT INTO cursos (cuenta_id, nombre, url, oculto) VALUES (%s, %s, %s, FALSE)",
                (cuenta_id, curso["nombre"], curso["url"])
            )
            curso_db_id = cursor.lastrowid
            match = re.search(r"id=(\d+)", curso["url"])
            if match:
                curso_id_map[int(match.group(1))] = curso_db_id

        # Insertar tareas asociadas a cada curso
        for curso_id_real, tareas in tareas_por_curso.items():
            curso_db_id = curso_id_map.get(curso_id_real)
            if not curso_db_id:
                continue
            for tarea in tareas:
                print(f"[DEBUG] Intentando insertar tarea: {tarea}")
                if "tarea_id" not in tarea:
                    print(f"[ERROR] tarea_id no encontrado en tarea: {tarea}")
                    continue
                cursor.execute(
                    "INSERT OR IGNORE INTO tareas (cuenta_id, curso_id, tarea_id, titulo, url, descripcion) VALUES (%s, %s, %s, %s, %s, %s)",
                    (cuenta_id, curso_db_id, tarea["tarea_id"], tarea["titulo"], tarea.get("url"), tarea.get("descripcion"))
                )

        cursor.execute(
            "INSERT INTO sincronizaciones (cuenta_id, estado, fecha) VALUES (%s, %s, NOW()) ON CONFLICT (cuenta_id) DO UPDATE SET estado = EXCLUDED.estado, fecha = NOW()",
            (cuenta_id, "ok")
        )
    except Exception as e:
        print(f"[ERROR] Excepción en sync_task: {e}")
        cursor.execute(
            "INSERT INTO sincronizaciones (cuenta_id, estado, fecha) VALUES (%s, %s, NOW()) ON CONFLICT (cuenta_id) DO UPDATE SET estado = EXCLUDED.estado, fecha = NOW()",
            (cuenta_id, "error")
        )
    conn.commit()

@router.post("/api/cuentas/{cuenta_id}/sincronizar")
def sincronizar_cursos_y_tareas_endpoint(cuenta_id: int, background_tasks: BackgroundTasks):
    # Raw SQL connection para sincronizaciones
    conn = engine.raw_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT usuario_moodle, contrasena_moodle, moodle_url FROM cuentas_moodle WHERE id = %s",
        (cuenta_id,),
    )
    cuenta = cursor.fetchone()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    usuario, contrasena, url = cuenta

    # Marcar como sincronizando
    cursor.execute(
        "INSERT INTO sincronizaciones (cuenta_id, estado, fecha) VALUES (%s, %s, NOW()) ON CONFLICT (cuenta_id) DO UPDATE SET estado = EXCLUDED.estado, fecha = NOW()",
        (cuenta_id, "sincronizando")
    )
    conn.commit()
    try:
        cursos = scrape_courses(url, usuario, contrasena)
        # Upsert cursos para preservar IDs
        for curso in cursos:
            cursor.execute(
                "INSERT INTO cursos (cuenta_id, nombre, url, oculto) VALUES (%s, %s, %s, FALSE) ON CONFLICT (cuenta_id, url) DO UPDATE SET nombre = EXCLUDED.nombre",
                (cuenta_id, curso["nombre"], curso["url"])
            )
        cursor.execute(
            "INSERT INTO sincronizaciones (cuenta_id, estado, fecha) VALUES (%s, %s, NOW()) ON CONFLICT (cuenta_id) DO UPDATE SET estado = EXCLUDED.estado, fecha = NOW()",
            (cuenta_id, "ok")
        )
        conn.commit()
        return {"mensaje": "Sincronización de cursos completada", "cursos": cursos}
    except Exception as e:
        cursor.execute(
            "INSERT INTO sincronizaciones (cuenta_id, estado, fecha) VALUES (%s, %s, NOW()) ON CONFLICT (cuenta_id) DO UPDATE SET estado = EXCLUDED.estado, fecha = NOW()",
            (cuenta_id, "error")
        )
        conn.commit()
        raise HTTPException(status_code=500, detail=f"Error al sincronizar cursos: {e}")

@router.post("/api/cuentas/{cuenta_id}/sincronizar_cursos")
def sincronizar_cursos_cuenta(cuenta_id: int):
    # Raw SQL connection para sincronizaciones
    conn = engine.raw_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT usuario_moodle, contrasena_moodle, moodle_url FROM cuentas_moodle WHERE id = %s",
        (cuenta_id,),
    )
    cuenta = cursor.fetchone()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    usuario, contrasena, url = cuenta

    # Marcar como sincronizando
    cursor.execute(
        "INSERT INTO sincronizaciones (cuenta_id, estado, fecha, fecha_inicio, porcentaje, tipo, duracion) "
        "VALUES (%s, %s, NOW(), NOW(), 0.0, 'cursos', NULL) "
        "ON CONFLICT (cuenta_id) DO UPDATE SET "
        "estado = EXCLUDED.estado, fecha = NOW(), fecha_inicio = EXCLUDED.fecha_inicio, "
        "porcentaje = EXCLUDED.porcentaje, tipo = EXCLUDED.tipo, duracion = EXCLUDED.duracion",
        (cuenta_id, "sincronizando")
    )
    conn.commit()
    try:
        cursos = scrape_courses(url, usuario, contrasena)
        # Upsert cursos para preservar IDs
        for curso in cursos:
            cursor.execute(
                "INSERT INTO cursos (cuenta_id, nombre, url, oculto) VALUES (%s, %s, %s, FALSE) ON CONFLICT (cuenta_id, url) DO UPDATE SET nombre = EXCLUDED.nombre",
                (cuenta_id, curso["nombre"], curso["url"])
            )
        cursor.execute(
            "INSERT INTO sincronizaciones (cuenta_id, estado, fecha, porcentaje, tipo, duracion) "
            "VALUES (%s, %s, NOW(), 100.0, 'cursos', NULL) "
            "ON CONFLICT (cuenta_id) DO UPDATE SET estado = EXCLUDED.estado, fecha = NOW(), porcentaje = EXCLUDED.porcentaje",
            (cuenta_id, "ok")
        )
        conn.commit()
        return {"mensaje": "Sincronización de cursos completada", "cursos": cursos}
    except Exception as e:
        conn.rollback()  # Clear aborted transaction
        error_msg = str(e)
        estado = "error_credenciales" if "Login fallido" in error_msg else "error"
        cursor.execute(
            "INSERT INTO sincronizaciones (cuenta_id, estado, fecha, porcentaje, tipo, duracion) "
            "VALUES (%s, %s, NOW(), 0.0, 'cursos', NULL) "
            "ON CONFLICT (cuenta_id) DO UPDATE SET estado = EXCLUDED.estado, fecha = NOW(), porcentaje = EXCLUDED.porcentaje",
            (cuenta_id, f"{estado}: {error_msg}")
        )
        conn.commit()
        raise HTTPException(status_code=401 if estado == "error_credenciales" else 500, 
                          detail=error_msg)

    cursor.execute(
        "SELECT usuario_moodle, contrasena_moodle, moodle_url FROM cuentas_moodle WHERE id = %s",
        (cuenta_id,),
    )
    cuenta = cursor.fetchone()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    usuario, contrasena, url = cuenta

    background_tasks.add_task(sync_task, usuario, contrasena, url, cuenta_id)
    return {"mensaje": "Sincronización iniciada en segundo plano"}

@router.get("/api/cuentas/{cuenta_id}/cursos")
def obtener_cursos_cuenta(cuenta_id: int):
    # Raw SQL connection para sincronizaciones
    conn = engine.raw_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, url FROM cursos WHERE cuenta_id = %s AND oculto = false",
        (cuenta_id,)
    )
    cursos = cursor.fetchall()
    return [{"id": c[0], "nombre": c[1], "url": c[2]} for c in cursos]

@router.get("/api/cuentas/{cuenta_id}/cursos/ocultos")
def obtener_cursos_ocultos_cuenta(cuenta_id: int):
    conn = engine.raw_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, url FROM cursos WHERE cuenta_id = %s AND oculto = true",
        (cuenta_id,)
    )
    cursos = cursor.fetchall()
    return [{"id": c[0], "nombre": c[1], "url": c[2]} for c in cursos]

@router.get("/api/cuentas/{cuenta_id}/sincronizacion")
def estado_sincronizacion(cuenta_id: int):
    # Raw SQL connection para sincronizaciones
    conn = engine.raw_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT estado FROM sincronizaciones WHERE cuenta_id = %s",
        (cuenta_id,)
    )
    row = cursor.fetchone()
    return {"estado": row[0] if row else "ok"}