from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import cursor, conn
from models import Usuario, LoginRequest

router = APIRouter()

@router.post("/api/login")
def login(request: LoginRequest):
    cursor.execute(
        """
        SELECT id FROM usuarios 
        WHERE (correo = ? OR nombre = ?) AND contrasena = ?
        """,
        (request.identificador, request.identificador, request.contrasena),
    )
    usuario = cursor.fetchone()
    if not usuario:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"usuarioId": usuario[0]}


@router.post("/api/usuarios")
def registrar_usuario(usuario: Usuario):
    try:
        cursor.execute(
            "INSERT INTO usuarios (nombre, correo, contrasena) VALUES (?, ?, ?)",
            (usuario.nombre, usuario.correo, usuario.contrasena),
        )
        conn.commit()
        return {"mensaje": "Usuario registrado exitosamente"}
    except Exception:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")