import os
import sys
import logging

# Añadir backend al path para importar el servicio
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.scraper_service import scrape_courses, scrape_tasks

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_scraper")

def main():
    # Leer credenciales de variables de entorno o input
    url = os.environ.get("MOODLE_URL")
    user = os.environ.get("MOODLE_USER")
    password = os.environ.get("MOODLE_PASSWORD")

    if not all([url, user, password]):
        logger.error("Faltan credenciales. Configura MOODLE_URL, MOODLE_USER y MOODLE_PASSWORD.")
        return

    logger.info(f"Probando conexión a {url} con usuario {user}...")

    try:
        # 1. Probar Login y obtener cursos
        logger.info("--- Iniciando scrape_courses ---")
        cursos = scrape_courses(url, user, password)
        
        if not cursos:
            logger.warning("No se encontraron cursos (o login falló silenciosamente).")
            return

        logger.info(f"✅ Éxito! Se encontraron {len(cursos)} cursos.")
        for c in cursos[:3]: # Mostrar los primeros 3
            logger.info(f" - {c['nombre']} ({c['url']})")

        # 2. Probar scrape de tareas del primer curso (opcional)
        if cursos:
            primer_curso = cursos[0]
            logger.info(f"\n--- Probando scrape_tasks en '{primer_curso['nombre']}' ---")
            tareas = scrape_tasks(url, user, password, primer_curso['url'])
            logger.info(f"✅ Éxito! Se encontraron {len(tareas)} tareas.")
            for t in tareas[:3]:
                logger.info(f" - {t['titulo']} (ID: {t['tarea_id']})")

    except Exception as e:
        logger.error(f"❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
