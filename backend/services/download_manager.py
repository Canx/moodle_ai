"""Servicio para gestionar descargas de archivos de Moodle."""

from pathlib import Path
import logging
from typing import List, Dict, Any
from playwright.async_api import Page
from services.scraper_service import login_moodle_async
from sqlalchemy.orm import Session
from models_db import EntregaDB
import asyncio

logger = logging.getLogger(__name__)

async def _download_single_file(context, file_url: str, local_path: Path, timeout: int = 120000) -> bool:
    """
    Descarga un archivo individual usando un nuevo contexto.
    
    Args:
        context: Contexto del navegador con cookies de sesión
        file_url: URL del archivo a descargar
        local_path: Ruta local donde guardar el archivo
        timeout: Tiempo máximo de espera en ms
    
    Returns:
        bool: True si la descarga fue exitosa, False si falló
    """
    try:
        download_page = await context.new_page()
        try:
            # Configurar comportamiento optimizado para descargas
            await download_page.route("**/*", lambda route: route.continue_(
                headers={
                    "Accept": "*/*",
                    "Accept-Encoding": "identity",
                    "Connection": "keep-alive"
                }
            ))
            
            # Asegurar que la URL tiene el parámetro forcedownload
            download_url = file_url
            if "forcedownload=1" not in download_url:
                download_url += ("&" if "?" in download_url else "?") + "forcedownload=1"
            
            logger.info(f"Iniciando descarga desde: {download_url}")

            async with download_page.expect_download(timeout=timeout) as download_info:
                await download_page.goto("about:blank")
                await download_page.evaluate(f"window.location.href = '{download_url}'")
                download = await download_info.value
                await asyncio.sleep(2)
                await download.save_as(local_path)
                
                if not local_path.exists() or local_path.stat().st_size == 0:
                    raise Exception("Archivo descargado inválido o vacío")
                    
                logger.info(f"Descarga completada: {local_path.name} ({local_path.stat().st_size} bytes)")
                return True

        finally:
            await download_page.close()
            
    except Exception as e:
        logger.error(f"Error descargando archivo {file_url}: {e}")
        if local_path.exists():
            local_path.unlink()
        return False

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
        # Usar el contexto existente para las descargas
        context = page.context
        
        # Configurar opciones de descarga
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
                
                local_path = download_dir / download['nombre_archivo']
                
                # Intentar descargar el archivo
                success = await _download_single_file(
                    context=context,
                    file_url=download['file_url'],
                    local_path=local_path
                )
                
                # Actualizar path en la base de datos si la descarga fue exitosa
                if success:
                    entrega = db.query(EntregaDB).filter(
                        EntregaDB.tarea_id == download['tarea_id'],
                        EntregaDB.alumno_id == download['entrega_id']
                    ).first()
                    if entrega:
                        entrega.local_file_path = str(local_path)
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
