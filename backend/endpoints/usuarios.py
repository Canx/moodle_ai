from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Usuario, LoginRequest
from models_db import UsuarioDB

router = APIRouter()

@router.get("/api/usuarios/{usuario_id}")
def obtener_usuario(usuario_id: int, db: Session = Depends(get_db)):
    usuario = db.query(UsuarioDB).filter(UsuarioDB.id == usuario_id).first()
    if usuario:
        return {"nombre": usuario.nombre}
    raise HTTPException(status_code=404, detail="Usuario no encontrado")

@router.post("/api/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(UsuarioDB).filter(
        ((UsuarioDB.correo == request.identificador) | (UsuarioDB.nombre == request.identificador)) &
        (UsuarioDB.contrasena == request.contrasena)
    ).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"usuarioId": usuario.id}

@router.post("/api/usuarios")
def registrar_usuario(usuario: Usuario, db: Session = Depends(get_db)):
    try:
        nuevo_usuario = UsuarioDB(
            nombre=usuario.nombre,
            correo=usuario.correo,
            contrasena=usuario.contrasena
        )
        db.add(nuevo_usuario)
        db.commit()
        db.refresh(nuevo_usuario)
        return {"mensaje": "Usuario registrado exitosamente", "id": nuevo_usuario.id}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="El correo ya está registrado")