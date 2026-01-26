from fastmcp import FastMCP
import sys
import os
import json
import logging
import asyncio
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("moodle-mcp")

# Paths e Imports
BACKEND_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.append(BACKEND_PATH)

try:
    from services.scraper_service import login_moodle_async, scrape_task_details_async
except ImportError:
    logger.error(f"No se pudo importar scraper_service.")
    raise

# Importar DB manager
try:
    import db
except ImportError:
    sys.path.append(os.path.dirname(__file__))
    import db

# Inicializar DB
db.init_db()

mcp = FastMCP("Moodle AI Assistant (Cached)")

CONFIG_FILE = "/home/ruben/clawd/moodle_ai/mcp_config.json"

def get_credentials(alias: str = "default") -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                if alias in config: return config[alias]
                if alias == "default" and config: return config[next(iter(config))]
        except: pass
    
    if alias == "default":
        return {
            "url": os.environ.get("MOODLE_URL") or "https://aules.edu.gva.es/eso46",
            "username": os.environ.get("MOODLE_USER") or "20242579A",
            "password": os.environ.get("MOODLE_PASSWORD") or "Alamierda6&"
        }
    return None

# --- Helpers de Scraping ---

async def _scrape_courses_impl(page, moodle_url):
    logger.info(f"Scraping courses from {moodle_url}")
    try:
        await page.goto(f"{moodle_url}/local/gvaaules/view.php", wait_until="networkidle", timeout=5000)
        cursos = []
        filas = await page.query_selector_all("table tbody tr")
        for fila in filas:
            enlace = await fila.query_selector("td.c2 a")
            if enlace:
                cursos.append({
                    "nombre": await enlace.inner_text(),
                    "url": await enlace.get_attribute("href")
                })
        if cursos: return cursos
    except: pass
    try:
        await page.goto(f"{moodle_url}/my/", wait_until="networkidle", timeout=5000)
        cursos = []
        for selector in [".courses .coursename a", ".course-info-container .coursename a", ".dashboard-card a.aalink"]:
            enlaces = await page.query_selector_all(selector)
            for enlace in enlaces:
                url = await enlace.get_attribute("href")
                if "course/view.php" in url:
                    cursos.append({
                        "nombre": (await enlace.inner_text()).strip(),
                        "url": url
                    })
        return cursos
    except Exception as e:
        logger.error(f"Error scraping dashboard: {e}")
        return []

async def _scrape_tasks_impl(page, moodle_url, course_url):
    import re
    logger.info(f"Scraping tasks from {course_url}")
    match = re.search(r"id=(\d+)", course_url)
    if not match: return []
    cid = match.group(1)
    await page.goto(f"{moodle_url}/course/view.php?id={cid}", wait_until="networkidle")
    tareas_info = []
    seen = set()
    elements = await page.query_selector_all(".modtype_assign")
    for el in elements:
        link_el = await el.query_selector("a.aalink")
        name_el = await el.query_selector(".instancename")
        if not (link_el and name_el): continue
        url = await link_el.get_attribute("href")
        nm = (await name_el.inner_text()).strip()
        m2 = re.search(r"id=(\d+)", url)
        if not m2: continue
        tid = int(m2.group(1))
        if tid in seen: continue
        seen.add(tid)
        tareas_info.append({"id": tid, "titulo": nm, "url": url})
    return tareas_info

# --- Helpers de Análisis de Documentos ---

def extract_text_from_docx(file_path):
    import docx
    try:
        doc = docx.Document(file_path)
        text = []
        for para in doc.paragraphs:
            text.append(para.text)
        # Tablas
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text for cell in row.cells]
                text.append(" | ".join(row_text))
        return "\n".join(text)
    except Exception as e:
        return f"Error leyendo DOCX: {e}"

def extract_text_from_odt(file_path):
    from odf.opendocument import load
    from odf import text, teletype
    try:
        doc = load(file_path)
        all_text = []
        for p in doc.getElementsByType(text.P):
            all_text.append(teletype.extractText(p))
        return "\n".join(all_text)
    except Exception as e:
        return f"Error leyendo ODT: {e}"

# --- Herramientas MCP ---

@mcp.tool()
async def sync_moodle(moodle_alias: str = "default", sync_courses: bool = True, sync_all_tasks: bool = False) -> str:
    creds = get_credentials(moodle_alias)
    if not creds: return "Error: Credenciales no encontradas"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        try:
            await login_moodle_async(page, creds["url"], creds["username"], creds["password"])
            if sync_courses:
                cursos = await _scrape_courses_impl(page, creds["url"])
                db.save_courses(moodle_alias, cursos)
                count_cursos = len(cursos)
            else: count_cursos = 0
            count_tareas = 0
            if sync_all_tasks:
                cursos_db = db.get_courses(moodle_alias)
                for c in cursos_db:
                    try:
                        tareas = await _scrape_tasks_impl(page, creds["url"], c["url"])
                        db.save_tasks(moodle_alias, c["url"], tareas)
                        count_tareas += len(tareas)
                    except: pass
            db.set_last_sync(moodle_alias)
            return f"Sincronización completada. {count_cursos} cursos, {count_tareas} tareas."
        finally: await browser.close()

@mcp.tool()
async def sync_course_tasks(course_url: str, moodle_alias: str = "default") -> str:
    creds = get_credentials(moodle_alias)
    if not creds: return "Error: Credenciales no encontradas"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        try:
            await login_moodle_async(page, creds["url"], creds["username"], creds["password"])
            tareas = await _scrape_tasks_impl(page, creds["url"], course_url)
            db.save_tasks(moodle_alias, course_url, tareas)
            return f"Curso actualizado. {len(tareas)} tareas."
        finally: await browser.close()

@mcp.tool()
def list_courses(moodle_alias: str = "default") -> Dict[str, Any]:
    cursos = db.get_courses(moodle_alias)
    last = db.get_last_sync(moodle_alias)
    if not cursos: return {"info": "Sin caché", "cursos": []}
    return {"info": f"Datos cacheados ({last})", "cursos": cursos}

@mcp.tool()
def list_tasks(course_url: str, moodle_alias: str = "default") -> Dict[str, Any]:
    tareas = db.get_tasks(moodle_alias, course_url)
    last = db.get_last_sync(moodle_alias)
    if not tareas: return {"info": "Sin caché para este curso", "tareas": []}
    return {"info": f"Datos cacheados ({last})", "tareas": tareas}

@mcp.tool()
async def get_task_details(task_id: int, moodle_alias: str = "default") -> Dict[str, Any]:
    creds = get_credentials(moodle_alias)
    if not creds: return {"error": "Credenciales no encontradas"}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        try:
            await login_moodle_async(page, creds["url"], creds["username"], creds["password"])
            detalles = await scrape_task_details_async(page, creds["url"], task_id)
            return detalles
        finally: await browser.close()

@mcp.tool()
async def analyze_submission_file(file_url: str, moodle_alias: str = "default") -> Dict[str, Any]:
    """
    Descarga y analiza un archivo entregado (docx, odt).
    Devuelve el texto extraído para su corrección.
    """
    creds = get_credentials(moodle_alias)
    if not creds: return {"error": "Credenciales no encontradas"}
    
    # Crear carpeta temporal
    import tempfile
    import uuid
    
    tmp_dir = os.path.join(tempfile.gettempdir(), "moodle_downloads")
    os.makedirs(tmp_dir, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        
        try:
            await login_moodle_async(page, creds["url"], creds["username"], creds["password"])
            
            logger.info(f"Descargando archivo desde: {file_url}")
            
            # Gestionar la descarga
            async with page.expect_download() as download_info:
                # Navegar a la URL del archivo (Moodle forzará descarga o mostrará prompt)
                # Si Moodle usa un redirect raro, quizás necesitemos clickear, pero file_url suele ser directo
                try:
                    await page.goto(file_url, wait_until="networkidle", timeout=15000)
                except:
                    pass # A veces timeout porque la descarga empieza antes
            
            download = await download_info.value
            ext = os.path.splitext(download.suggested_filename)[1].lower()
            filename = f"{uuid.uuid4()}{ext}"
            file_path = os.path.join(tmp_dir, filename)
            
            await download.save_as(file_path)
            logger.info(f"Archivo guardado en: {file_path}")
            
            # Analizar según extensión
            content = ""
            if ext == ".docx":
                content = extract_text_from_docx(file_path)
            elif ext == ".odt":
                content = extract_text_from_odt(file_path)
            else:
                return {"error": f"Formato no soportado: {ext}", "path": file_path}
            
            # Limpiar archivo (o dejarlo para debug)
            # os.remove(file_path) 
            
            return {
                "filename": download.suggested_filename,
                "type": ext,
                "content_preview": content[:2000] + "..." if len(content)>2000 else content,
                "full_content": content # Para que el LLM lo tenga todo
            }

        except Exception as e:
            return {"error": str(e)}
        finally:
            await browser.close()

@mcp.tool()
async def submit_grade(task_id: int, student_id: int, grade: float, feedback: str, moodle_alias: str = "default") -> str:
    """
    Envía la calificación y feedback para un alumno en una tarea.
    """
    creds = get_credentials(moodle_alias)
    if not creds: return "Error: Credenciales no encontradas"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        try:
            await login_moodle_async(page, creds["url"], creds["username"], creds["password"])
            
            # Construir URL de calificación directa
            # Moodle suele usar action=grader&userid=...
            # O action=grade&userid=... dependiendo de la versión y plugin
            
            # Intentamos la vista de "Calificación individual"
            grade_url = f"{creds['url']}/mod/assign/view.php?id={task_id}&action=grade&userid={student_id}"
            logger.info(f"Navegando a calificación: {grade_url}")
            
            await page.goto(grade_url, wait_until="networkidle")
            
            # Verificar si estamos en la página correcta
            if "action=grade" not in page.url and "action=grader" not in page.url:
                # Fallback: ir a la tabla y buscar al alumno (más lento/complejo)
                return f"Error: No se pudo acceder a la página de calificación directa. URL final: {page.url}"
            
            # 1. Poner Nota (id_grade)
            try:
                await page.wait_for_selector("#id_grade", state="visible", timeout=5000)
                await page.fill("#id_grade", str(grade))
            except:
                logger.warning("Input #id_grade no visible, intentando forzar value con JS")
                # Fallback JS si el elemento está tapado u oculto
                await page.evaluate(f"document.querySelector('#id_grade').value = '{grade}'")

            # 2. Poner Feedback (Estrategia híbrida Atto/TinyMCE/Textarea)
            feedback_set = False
            
            # Intento 1: API de TinyMCE (si existe)
            try:
                await page.evaluate(f"""
                    if (typeof tinyMCE !== 'undefined' && tinyMCE.activeEditor) {{
                        tinyMCE.activeEditor.setContent(`{feedback}`);
                        tinyMCE.triggerSave();
                    }} else {{
                        throw new Error('No TinyMCE');
                    }}
                """)
                logger.info("Feedback establecido vía TinyMCE API")
                feedback_set = True
            except:
                pass

            # Intento 2: Editor Atto (div contenteditable)
            if not feedback_set:
                try:
                    atto = await page.query_selector("div.editor_atto_content_wrap div[contenteditable='true']")
                    if atto:
                        await atto.fill(feedback)
                        logger.info("Feedback establecido vía Atto")
                        feedback_set = True
                except: pass

            # Intento 3: Textarea directo (fallback)
            if not feedback_set:
                try:
                    await page.fill("#id_assignfeedbackcomments_editor", feedback)
                    logger.info("Feedback establecido vía Textarea directo")
                except:
                    # Fallback JS final
                    await page.evaluate(f"""
                        var el = document.getElementById('id_assignfeedbackcomments_editor');
                        if(el) {{ el.value = `{feedback}`; }}
                    """)

            # Esperar un poco para asegurar que los eventos de JS se propaguen
            await page.wait_for_timeout(1000)

            # 3. Guardar cambios (savegrade)
            save_btn = await page.query_selector("input[name='savegrade']")
            if not save_btn:
                 # Fallback por texto si el name cambia
                 save_btn = await page.get_by_role("button", name="Guardar cambios")
            
            if save_btn:
                await save_btn.click()
                await page.wait_for_load_state("networkidle")
                return f"Calificación enviada correctamente para alumno {student_id}: Nota {grade}"
            else:
                return "Error: No se encontró el botón de guardar (savegrade)."

        except Exception as e:
            return f"Error enviando calificación: {str(e)}"
        finally:
            await browser.close()

@mcp.tool()
async def debug_grading_page(task_id: int, student_id: int, moodle_alias: str = "default") -> str:
    """
    Descarga el HTML de la página de calificación para inspeccionar selectores.
    """
    creds = get_credentials(moodle_alias)
    if not creds: return "Error: Credenciales no encontradas"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        try:
            await login_moodle_async(page, creds["url"], creds["username"], creds["password"])
            
            grade_url = f"{creds['url']}/mod/assign/view.php?id={task_id}&action=grade&userid={student_id}"
            await page.goto(grade_url, wait_until="networkidle")
            
            # Extraer información de inputs relevantes
            inputs = await page.evaluate('''() => {
                const els = document.querySelectorAll('input, textarea, select, button');
                return Array.from(els).map(el => ({
                    tag: el.tagName.toLowerCase(),
                    id: el.id,
                    name: el.name,
                    class: el.className,
                    type: el.type,
                    placeholder: el.placeholder,
                    value: el.value
                }));
            }''')
            
            # Filtrar solo los que parezcan de calificación
            relevant = [i for i in inputs if 'grade' in (i['name'] or '') or 'grade' in (i['id'] or '') or 'save' in (i['name'] or '') or 'feedback' in (i['name'] or '')]
            
            return json.dumps(relevant, indent=2)

        except Exception as e:
            return f"Error debug: {str(e)}"
        finally:
            await browser.close()

if __name__ == "__main__":
    mcp.run()
