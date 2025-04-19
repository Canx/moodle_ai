from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey, Float, Text, DateTime
from database import Base
from datetime import datetime

class UsuarioDB(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    correo = Column(String, unique=True, nullable=False)
    contrasena = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint('correo', name='uq_usuario_correo'),)

class CuentaMoodleDB(Base):
    __tablename__ = "cuentas_moodle"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    moodle_url = Column(String, nullable=False)
    usuario_moodle = Column(String, nullable=False)
    contrasena_moodle = Column(String, nullable=False)

class CursoDB(Base):
    __tablename__ = "cursos"
    id = Column(Integer, primary_key=True, index=True)
    cuenta_id = Column(Integer, ForeignKey("cuentas_moodle.id"), nullable=False)
    nombre = Column(String, nullable=False)
    url = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint('cuenta_id', 'url', name='uq_curso_cuenta_url'),)

class TareaDB(Base):
    __tablename__ = "tareas"
    id = Column(Integer, primary_key=True, index=True)
    cuenta_id = Column(Integer, ForeignKey("cuentas_moodle.id"), nullable=False)
    curso_id = Column(Integer, nullable=False)
    tarea_id = Column(Integer, nullable=False)
    titulo = Column(String, nullable=False)
    descripcion = Column(Text)
    rubrica = Column(Text)
    fecha_sincronizacion = Column(String)
    estado = Column(String)
    calificacion_maxima = Column(Float)
    __table_args__ = (UniqueConstraint('curso_id', 'tarea_id', name='uq_tarea_curso_tareaid'),)

class EntregaDB(Base):
    __tablename__ = "entregas"
    id = Column(Integer, primary_key=True, index=True)
    tarea_id = Column(Integer, ForeignKey("tareas.id"), nullable=False)
    alumno_id = Column(String, nullable=False)
    fecha_entrega = Column(String)
    contenido = Column(Text)
    file_url = Column(String)
    file_name = Column(String)
    file_id = Column(String)
    estado = Column(String)
    nota = Column(Float)
    feedback = Column(Text)
    nombre = Column(String)
    __table_args__ = (UniqueConstraint('tarea_id', 'alumno_id', name='uq_entrega_tarea_alumno'),)

class SincronizacionDB(Base):
    __tablename__ = "sincronizaciones"
    cuenta_id = Column(Integer, ForeignKey("cuentas_moodle.id"), primary_key=True)
    estado = Column(String, nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False)
