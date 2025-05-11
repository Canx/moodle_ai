from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models_db import LLMConfigDB, UsuarioLLMConfigDB, UsuarioDB

router = APIRouter()

def insert_default_configs(db: Session):
    """Inserta las configuraciones por defecto si no existen"""
    defaults = [
        {
            "nombre": "Google AI Studio",
            "url_template": "https://aistudio.google.com/prompts/new_chat",
            "descripcion": "Google AI Studio para evaluación de trabajos"
        },
        {
            "nombre": "OpenAI ChatGPT",
            "url_template": "https://chat.openai.com",
            "descripcion": "ChatGPT de OpenAI"
        },
        {
            "nombre": "Claude",
            "url_template": "https://claude.ai",
            "descripcion": "Claude de Anthropic"
        },
        {
            "nombre": "Gemini",
            "url_template": "https://gemini.google.com",
            "descripcion": "Google Gemini"
        }
    ]
    
    for config in defaults:
        existing = db.query(LLMConfigDB).filter(LLMConfigDB.nombre == config["nombre"]).first()
        if not existing:
            db.add(LLMConfigDB(**config))
    
    db.commit()

@router.get("/api/llm_configs")
def obtener_configuraciones_llm(db: Session = Depends(get_db)):
    """Obtiene todas las configuraciones de LLM disponibles"""
    configs = db.query(LLMConfigDB).all()
    if not configs:
        insert_default_configs(db)
        configs = db.query(LLMConfigDB).all()
    return [{"id": c.id, "nombre": c.nombre, "url_template": c.url_template, "descripcion": c.descripcion} for c in configs]

@router.get("/api/usuarios/{usuario_id}/llm_config")
def obtener_config_llm_usuario(usuario_id: int, db: Session = Depends(get_db)):
    """Obtiene la configuración por defecto de LLM para un usuario"""
    config = db.query(UsuarioLLMConfigDB, LLMConfigDB)\
        .join(LLMConfigDB)\
        .filter(UsuarioLLMConfigDB.usuario_id == usuario_id)\
        .filter(UsuarioLLMConfigDB.is_default == True)\
        .first()
    
    if not config:
        # Si no hay configuración por defecto, obtener la primera disponible
        config = db.query(LLMConfigDB).first()
        if not config:
            raise HTTPException(status_code=404, detail="No hay configuraciones LLM disponibles")
        return {"id": config.id, "nombre": config.nombre, "url_template": config.url_template, "descripcion": config.descripcion, "is_default": False}
    
    return {
        "id": config.LLMConfigDB.id,
        "nombre": config.LLMConfigDB.nombre,
        "url_template": config.LLMConfigDB.url_template,
        "descripcion": config.LLMConfigDB.descripcion,
        "is_default": True
    }

@router.post("/api/usuarios/{usuario_id}/llm_config/{config_id}/set_default")
def establecer_config_llm_defecto(usuario_id: int, config_id: int, db: Session = Depends(get_db)):
    """Establece la configuración de LLM por defecto para un usuario"""
    
    # Verificar que el usuario existe
    usuario = db.query(UsuarioDB).filter(UsuarioDB.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificar que la configuración existe
    config = db.query(LLMConfigDB).filter(LLMConfigDB.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuración LLM no encontrada")
    
    # Eliminar cualquier configuración por defecto existente
    db.query(UsuarioLLMConfigDB)\
        .filter(UsuarioLLMConfigDB.usuario_id == usuario_id)\
        .filter(UsuarioLLMConfigDB.is_default == True)\
        .update({"is_default": False})
    
    # Buscar si ya existe una relación usuario-config
    user_config = db.query(UsuarioLLMConfigDB)\
        .filter(UsuarioLLMConfigDB.usuario_id == usuario_id)\
        .filter(UsuarioLLMConfigDB.llm_config_id == config_id)\
        .first()
    
    if user_config:
        user_config.is_default = True
    else:
        # Crear nueva relación usuario-config
        user_config = UsuarioLLMConfigDB(
            usuario_id=usuario_id,
            llm_config_id=config_id,
            is_default=True
        )
        db.add(user_config)
    
    db.commit()
    return {"mensaje": "Configuración por defecto actualizada"}
