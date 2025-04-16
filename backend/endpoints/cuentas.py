from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import cursor, conn
from models import CuentaMoodle
from scraper import obtener_cursos_desde_moodle

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

@router.post("/api/cuentas/{cuenta_id}/sincronizar")
def sincronizar_cursos(cuenta_id: int):
    # Obtener datos de la cuenta
    cursor.execute(
        "SELECT usuario_moodle, contrasena_moodle, moodle_url FROM cuentas_moodle WHERE id = ?",
        (cuenta_id,),
    )
    cuenta = cursor.fetchone()
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    usuario, contrasena, url = cuenta

    # Hacer scraping
    try:
        cursos = obtener_cursos_desde_moodle(usuario, contrasena, url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al sincronizar: {e}")

    # Guardar cursos en la base de datos (puedes limpiar antes si quieres evitar duplicados)
    cursor.execute("DELETE FROM cursos WHERE cuenta_id = ?", (cuenta_id,))
    for curso in cursos:
        cursor.execute(
            "INSERT INTO cursos (cuenta_id, nombre, url) VALUES (?, ?, ?)",
            (cuenta_id, curso["nombre"], curso["url"])
        )
    conn.commit()
    return {"mensaje": f"{len(cursos)} cursos sincronizados"}

@router.get("/api/cuentas/{cuenta_id}/cursos")
def obtener_cursos_cuenta(cuenta_id: int):
    cursor.execute(
        "SELECT id, nombre, url FROM cursos WHERE cuenta_id = ?",
        (cuenta_id,)
    )
    cursos = cursor.fetchall()
    return [{"id": c[0], "nombre": c[1], "url": c[2]} for c in cursos]