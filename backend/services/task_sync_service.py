from sqlalchemy.orm import Session
from models_db import TareaDB, EntregaDB, CuentaMoodleDB
from services.scraper_service import scrape_task_details_async
from tasks import download_submission_file_task
from datetime import datetime
import logging
from typing import Dict, Any, List
from playwright.async_api import Page
import asyncio
from services.download_manager import download_submission_files

logger = logging.getLogger(__name__)

async def sync_single_task(
    db: Session,
    task_info: Dict[str, Any],
    page: Page,
    cuenta_id: int,
    curso_id: int,
    moodle_url: str,
    existing_task: TareaDB | None = None,
    was_hidden: bool = False
) -> TareaDB:
    """
    Sincroniza una tarea individual usando una sesión de Playwright existente.
    
    Args:
        db: Sesión de base de datos
        task_info: Diccionario con información básica de la tarea (tarea_id, titulo, url)
        page: Página de Playwright con una sesión activa
        cuenta_id: ID de la cuenta de Moodle
        curso_id: ID del curso
        moodle_url: URL base de Moodle
        existing_task: Instancia existente de TareaDB si la tarea ya existe
        was_hidden: Si la tarea estaba oculta anteriormente
    
    Returns:
        TareaDB: La tarea actualizada o creada
    """
    logger.info(f"Sincronizando tarea individual {task_info.get('tarea_id')}")
    
    # Obtener detalles de la tarea usando la sesión existente
    details = await scrape_task_details_async(page, moodle_url, task_info['tarea_id'])
    entregas = details.get('entregas_pendientes', [])
    
    # Determinar estado según entregas
    if not entregas:
        estado = 'sin_entregas'
    elif any(e.get('estado','').lower().startswith('enviado') or e.get('estado','').lower().startswith('pendiente') for e in entregas):
        estado = 'pendiente_calificar'
    else:
        estado = 'sin_pendientes'
    
    # Preparar datos de la tarea
    tarea_data = {
        'cuenta_id': cuenta_id,
        'curso_id': curso_id,
        'tarea_id': task_info['tarea_id'],
        'titulo': task_info['titulo'],
        'descripcion': details.get('descripcion'),
        'estado': estado,
        'calificacion_maxima': details.get('calificacion_maxima'),
        'tipo_calificacion': details.get('tipo_calificacion'),
        'detalles_calificacion': details.get('detalles_calificacion'),
        'fecha_sincronizacion': datetime.utcnow().isoformat()
    }
    
    if existing_task:
        # Si existe y estaba oculta, mantener ese estado
        if was_hidden:
            tarea_data['oculto'] = True
        # Actualizar la tarea existente
        for key, value in tarea_data.items():
            setattr(existing_task, key, value)
        tarea = existing_task
    else:
        # Crear nueva tarea
        tarea = TareaDB(**tarea_data)
        db.add(tarea)
    
    db.commit()
    db.refresh(tarea)

    # Eliminar entregas antiguas
    db.query(EntregaDB).filter(EntregaDB.tarea_id == tarea.id).delete(synchronize_session=False)
    db.commit()

    # Acumular información de descargas
    downloads_to_process = []
    nuevas_entregas = []

    # Procesar entregas
    for entrega in entregas:
        archivos = entrega.get('archivos', [])
        file_url = archivos[0]['url'] if archivos else None
        file_name = archivos[0]['nombre'] if archivos else None
        texto = entrega.get('texto')
        nota_text = entrega.get('nota')
        
        try:
            nota = float(str(nota_text).replace(',', '.')) if nota_text else None
        except:
            nota = None

        nueva_entrega = EntregaDB(
            tarea_id=tarea.id,
            alumno_id=entrega.get('alumno_id'),
            fecha_entrega=entrega.get('fecha_entrega'),
            contenido=texto,
            file_url=file_url,
            file_name=file_name,
            estado=entrega.get('estado'),
            nombre=entrega.get('nombre'),
            nota=nota
        )
        nuevas_entregas.append(nueva_entrega)

        # Acumular información de descarga si hay archivo
        if file_url and file_name:
            downloads_to_process.append({
                'file_url': file_url,
                'tarea_id': tarea.id,
                'entrega_id': entrega.get('alumno_id'),
                'nombre_archivo': file_name
            })

    # Guardar todas las entregas
    db.bulk_save_objects(nuevas_entregas)
    db.commit()

    # Si hay archivos para descargar, procesarlos en lote
    if downloads_to_process:
        cuenta = db.query(CuentaMoodleDB).filter(CuentaMoodleDB.id == cuenta_id).first()
        if cuenta:
            # Procesar todas las descargas usando una única sesión
            await download_submission_files(
                page,
                moodle_url,
                cuenta.usuario_moodle,
                cuenta.contrasena_moodle,
                downloads_to_process,
                db
            )

    return tarea
