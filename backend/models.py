from pydantic import BaseModel

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