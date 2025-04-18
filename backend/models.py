from pydantic import BaseModel
from typing import Optional

class Usuario(BaseModel):
    nombre: str
    correo: str
    contrasena: str

class CuentaMoodle(BaseModel):
    moodle_url: str
    usuario_moodle: str
    contrasena_moodle: str

class LoginRequest(BaseModel):
    identificador: str  # Puede ser correo o nombre de usuario
    contrasena: str

class Tarea(BaseModel):
    id: Optional[int] = None
    cuenta_id: Optional[int] = None  # ID de la cuenta Moodle asociada
    curso_id: int
    tarea_id: int
    titulo: str
    descripcion: Optional[str] = None
    rubrica: Optional[str] = None
    fecha_sincronizacion: Optional[str] = None
    estado: Optional[str] = None