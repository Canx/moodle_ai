"""Servicio para gestionar descargas de archivos de Moodle."""

from pathlib import Path
import logging
from typing import List, Dict, Any
from playwright.async_api import Page
from services.scraper_service import login_moodle_async
from endpoints.cursos import download_submission_file
from sqlalchemy.orm import Session
from models_db import EntregaDB

logger = logging.getLogger(__name__)

async def download_submission_files(
    page: Page,
    moodle_url: str,
    usuario: str,
    contrasena: str,
    downloads: List[Dict[str, Any]],
    db: Session
) -> None:
    """
    Descarga múltiples archivos de entrega usando una única sesión de navegador.
    
    Args:
        page: Página de Playwright con sesión activa
        moodle_url: URL base de Moodle
        usuario: Usuario de Moodle
        contrasena: Contraseña de Moodle
        downloads: Lista de diccionarios con información de descarga
        db: Sesión de base de datos
    """
    try:
        # Login una sola vez para todas las descargas
        await login_moodle_async(page, moodle_url, usuario, contrasena)
        
        # Configurar navegador para descargas
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.set_extra_http_headers({
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br"
        })
        
        for download in downloads:
            try:
                # Asegurar que el directorio existe
                base_download_dir = Path("downloads")
                base_download_dir.mkdir(mode=0o755, exist_ok=True)
                
                download_dir = base_download_dir / str(download['tarea_id']) / str(download['entrega_id'])
                download_dir.mkdir(parents=True, mode=0o755, exist_ok=True)
                
                # Descargar archivo
                local_file_path = await download_submission_file(
                    page, 
                    download['file_url'],
                    download['tarea_id'],
                    download['entrega_id'],
                    download['nombre_archivo']
                )
                
                if local_file_path and Path(local_file_path).exists():
                    # Establecer permisos correctos
                    Path(local_file_path).chmod(0o644)
                    
                    # Actualizar ruta en base de datos
                    db.query(EntregaDB).filter(
                        EntregaDB.tarea_id == download['tarea_id'],
                        EntregaDB.alumno_id == download['entrega_id']
                    ).update({"local_file_path": str(local_file_path)})
                    db.commit()
                    
                    logger.info(f"Archivo descargado correctamente: {download['nombre_archivo']}")
                else:
                    logger.error(f"Error descargando archivo: {download['nombre_archivo']}")
                    
            except Exception as e:
                logger.error(f"Error procesando descarga {download['nombre_archivo']}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error en el proceso de descarga: {e}")
        raise
