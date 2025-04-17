from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from database import cursor, conn
from models import CuentaMoodle
from scraper import sincronizar_cursos_y_tareas
import re

router = APIRouter()

@router.get("/api/usuarios/{usuario_id}/cuentas")
def obtener_cuentas(usuario_id: int):
    cursor.execute(
        "SELECT id, moodle_url, usuario_moodle FROM cuentas_moodle WHERE usuario_id = ?",
        (usuario_id,),
    )
    cuentas = cursor.fetchall()
    return [
        {"id": c[0], "moodle_url": c[1], "usuario_moodle": c[2]}
        for c in cuentas
    ]

@router.post("/api/usuarios/{usuario_id}/cuentas")
def agregar_cuenta(usuario_id: int, cuenta: CuentaMoodle):
    cursor.execute(
        "INSERT INTO cuentas_moodle (usuario_id, moodle_url, usuario_moodle, contrasena_moodle) VALUES (?, ?, ?, ?)",
        (usuario_id, cuenta.moodle_url, cuenta.usuario_moodle, cuenta.contrasena_moodle),
    )
    conn.commit()
    return {"mensaje": "Cuenta de Moodle agregada exitosamente"}

@router.put("/api/usuarios/{usuario_id}/cuentas/{cuenta_id}")
def editar_cuenta(usuario_id: int, cuenta_id: int, cuenta: CuentaMoodle):
    cursor.execute(
        "UPDATE cuentas_moodle SET moodle_url = ?, usuario_moodle = ?, contrasena_moodle = ? WHERE id = ? AND usuario_id = ?",
        (cuenta.moodle_url, cuenta.usuario_moodle, cuenta.contrasena_moodle, cuenta_id, usuario_id),
    )
    conn.commit()
    return {"mensaje": "Cuenta de Moodle actualizada exitosamente"}

@router.delete("/api/usuarios/{usuario_id}/cuentas/{cuenta_id}")
def borrar_cuenta(usuario_id: int, cuenta_id: int):
    cursor.execute(
        "DELETE FROM cuentas_moodle WHERE id = ? AND usuario_id = ?",
        (cuenta_id, usuario_id),
    )
    conn.commit()
    return {"mensaje": "Cuenta de Moodle eliminada exitosamente"}

def sync_task(usuario, contrasena, url, cuenta_id):
    print(f"[DEBUG] sync_task lanzado para cuenta {cuenta_id}")
    # Marcar como "sincronizando"
    cursor.execute(
        "INSERT OR REPLACE INTO sincronizaciones (cuenta_id, estado) VALUES (?, ?)",
        (cuenta_id, "sincronizando")
    )
    conn.commit()
    try:
        print("[DEBUG] Antes de llamar a sincronizar_cursos_y_tareas")
        cursos, tareas_por_curso = sincronizar_cursos_y_tareas(usuario, contrasena, url)
        print(f"[DEBUG] Cursos obtenidos: {len(cursos)}")

        # Eliminar cursos y tareas anteriores de esta cuenta
        cursor.execute("DELETE FROM tareas WHERE curso_id IN (SELECT id FROM cursos WHERE cuenta_id = ?)", (cuenta_id,))
        cursor.execute("DELETE FROM cursos WHERE cuenta_id = ?", (cuenta_id,))

        # Insertar cursos y mapear id real de Moodle a id en la base de datos
        curso_id_map = {}
        for curso in cursos:
            cursor.execute(
                "INSERT INTO cursos (cuenta_id, nombre, url) VALUES (?, ?, ?)",
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
                    "INSERT OR IGNORE INTO tareas (curso_id, tarea_id, titulo) VALUES (?, ?, ?)",
                    (curso_db_id, tarea["tarea_id"], tarea["titulo"])
                )

        cursor.execute(
            "INSERT OR REPLACE INTO sincronizaciones (cuenta_id, estado) VALUES (?, ?)",
            (cuenta_id, "ok")
        )
    except Exception as e:
        print(f"[ERROR] Excepción en sync_task: {e}")
        cursor.execute(
            "INSERT OR REPLACE INTO sincronizaciones (cuenta_id, estado) VALUES (?, ?)",
            (cuenta_id, "error")
        )
    conn.commit()

@router.post("/api/cuentas/{cuenta_id}/sincronizar")
def sincronizar_cursos_y_tareas_endpoint(cuenta_id: int, background_tasks: BackgroundTasks):
    cursor.execute(
        "SELECT usuario_moodle, contrasena_moodle, moodle_url FROM cuentas_moodle WHERE id = ?",
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
    cursor.execute(
        "SELECT id, nombre, url FROM cursos WHERE cuenta_id = ?",
        (cuenta_id,)
    )
    cursos = cursor.fetchall()
    return [{"id": c[0], "nombre": c[1], "url": c[2]} for c in cursos]

@router.get("/api/cuentas/{cuenta_id}/sincronizacion")
def estado_sincronizacion(cuenta_id: int):
    cursor.execute(
        "SELECT estado FROM sincronizaciones WHERE cuenta_id = ?",
        (cuenta_id,)
    )
    row = cursor.fetchone()
    return {"estado": row[0] if row else "ok"}