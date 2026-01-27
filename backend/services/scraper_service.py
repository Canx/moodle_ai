import re
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
import asyncio
from urllib.parse import urljoin, urlparse, parse_qs
import logging

# Configurar logger a archivo para debug
file_handler = logging.FileHandler('/tmp/scraper_debug.log')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

# Servicio puro de scraping de Moodle: sin lógica de BD ni endpoints.

def login_moodle(page, moodle_url, usuario, contrasena):
    login_url = f"{moodle_url}/login/index.php"
    logger.info(f"LOGIN SYNC: navegando a {login_url}")
    try:
        page.goto(login_url, wait_until="networkidle")
        logger.info("LOGIN SYNC: esperando selector 'form#login'")
        # esperar form y token
        page.wait_for_selector("form#login", timeout=15000)
        logger.info("LOGIN SYNC: 'form#login' visible")
        page.wait_for_selector("input[name='logintoken']", state="attached", timeout=15000)
        logger.info("LOGIN SYNC: 'logintoken' attached")
        page.fill("input[name='username']", usuario)
        logger.info("LOGIN SYNC: username llenado")
        page.fill("input[name='password']", contrasena)
        logger.info("LOGIN SYNC: password llenado")
        page.click("button#loginbtn")
        logger.info("LOGIN SYNC: clic en loginbtn")
        
        # Esperar a que aparezca cualquiera de los elementos comunes post-login de Moodle
        success = False
        try:
            # Intentar diferentes selectores comunes de Moodle
            for selector in [".navbar-menu-aules", ".navbar-nav", "#nav-drawer", ".usermenu"]:
                try:
                    page.wait_for_selector(selector, timeout=5000)
                    success = True
                    break
                except:
                    continue
            
            if not success:
                # Si no encontramos ningún elemento de navegación, esperar a que desaparezca el formulario
                page.wait_for_selector("form#login", state="hidden", timeout=5000)
                success = True
        except:
            pass

        # Comprobar mensaje de error incluso si parece que el login fue exitoso
        error_el = page.query_selector("#loginerrormessage")
        if error_el:
            mensaje = error_el.inner_text()
            raise Exception(f"Login fallido: {mensaje}")
            
        if not success:
            raise Exception("No se pudo confirmar login exitoso")
            
        logger.info("LOGIN SYNC: login exitoso")
    except Exception as e:
        logger.error(f"LOGIN SYNC: error durante el login: {str(e)}")
        raise


def get_cursos_moodle(page, moodle_url):
    # Intentar primero la vista específica de GVA Aules
    try:
        page.goto(f"{moodle_url}/local/gvaaules/view.php", wait_until="networkidle", timeout=10000)
        cursos = []
        filas = page.query_selector_all("table tbody tr")
        for fila in filas:
            enlace = fila.query_selector("td.c2 a")
            if enlace:
                cursos.append({
                    "nombre": enlace.inner_text(),
                    "url": enlace.get_attribute("href")
                })
        if cursos:
            return cursos
    except Exception as e:
        logger.warning(f"No se pudieron obtener cursos desde vista GVA Aules: {e}")

    # Si no funciona, intentar la vista estándar de Moodle
    try:
        # Intentar la página de dashboard primero
        page.goto(f"{moodle_url}/my/", wait_until="networkidle", timeout=10000)
        
        cursos = []
        # Buscar cursos en el dashboard
        for selector in [".courses .coursename a", ".course-info-container .coursename a", ".dashboard-card a.aalink"]:
            try:
                enlaces = page.query_selector_all(selector)
                for enlace in enlaces:
                    try:
                        url = enlace.get_attribute("href")
                        # Asegurarse de que es un enlace a curso válido
                        if "course/view.php" in url:
                            cursos.append({
                                "nombre": enlace.inner_text().strip(),
                                "url": url
                            })
                    except:
                        continue
            except:
                continue
                
        if cursos:
            return cursos
            
        # Si no hay cursos en el dashboard, intentar la página de cursos
        page.goto(f"{moodle_url}/course/", wait_until="networkidle", timeout=10000)
        for selector in [".coursename a", ".course-info-container h3 a", ".coursebox .info h3.coursename a"]:
            try:
                enlaces = page.query_selector_all(selector)
                for enlace in enlaces:
                    try:
                        url = enlace.get_attribute("href")
                        if "course/view.php" in url:
                            cursos.append({
                                "nombre": enlace.inner_text().strip(),
                                "url": url
                            })
                    except:
                        continue
            except:
                continue
                
        return cursos
            
    except Exception as e:
        logger.error(f"Error obteniendo cursos: {e}")
        raise Exception("No se pudieron obtener los cursos. El login puede haber fallado o la estructura del sitio es diferente.")


def get_entregas_pendientes(page, tarea_id):
    entregas = []
    # Obtener encabezados de la tabla de entregas con manejo de error
    try:
        header_cells = page.query_selector_all("table.generaltable thead th")
    except Exception as e:
        logger.warning(f"SYNC SCRAPE: no se encontró tabla de encabezados: {e}")
        header_cells = []
    
    archivo_col_idx = texto_col_idx = nota_col_idx = nombre_col_idx = None
    
    for idx, th in enumerate(header_cells):
        try:
            txt = th.inner_text().strip()
            logger.info(f"DEBUG: Columna {idx}: '{txt}'")
        except Exception as e:
            logger.warning(f"SYNC SCRAPE: error leyendo encabezado idx {idx}: {e}")
            continue
            
        if "Archivos enviados" in txt:
            archivo_col_idx = idx
        if "Texto en línea" in txt:
            texto_col_idx = idx
        if ("Nota" in txt or "Calificación" in txt) and nota_col_idx is None:
            nota_col_idx = idx
        if "Nombre" in txt or "Apellidos" in txt:
            nombre_col_idx = idx
            logger.info(f"DEBUG: Columna nombre detectada en índice {idx}")
            
    filas = page.query_selector_all("table.generaltable tbody tr")
    for fila in filas:
        cb = fila.query_selector("input[name='selectedusers']")
        if not cb:
            continue
        alumno_id = cb.get_attribute("value").strip()
        
        # Extracción mejorada de nombre
        nombre = ""
        tds = fila.query_selector_all("td")
        
        # 1. Por columna detectada
        if nombre_col_idx is not None and nombre_col_idx < len(tds):
            try:
                nombre = tds[nombre_col_idx].inner_text().strip()
            except: pass
            
        # 2. Fallback: buscar link de usuario en columnas comunes (c2) o cualquier link a /user/view.php
        if not nombre:
            try:
                # Intentar selector clásico c2
                link = fila.query_selector("td.c2 a")
                if link and "user/view.php" in (link.get_attribute("href") or ""):
                    nombre = link.inner_text().strip()
                
                # Si falla, buscar cualquier link de usuario en la fila
                if not nombre:
                    links = fila.query_selector_all("a[href*='user/view.php']")
                    for l in links:
                        txt = l.inner_text().strip()
                        if txt and len(txt) > 2: # Evitar iniciales o iconos
                            nombre = txt
                            break
                            
                # Fallback final: buscar imagen de perfil (userpicture)
                if not nombre:
                    img = fila.query_selector("img.userpicture")
                    if img:
                        alt = img.get_attribute("alt")
                        if alt and "Imagen de" not in alt: # A veces dice "Imagen de Juan"
                            nombre = alt.replace("Imagen de", "").strip()
            except: pass

        estado = fila.query_selector("td.c4 div").inner_text().strip() if fila.query_selector("td.c4 div") else ""
        fecha_entrega = fila.query_selector("td.c7").inner_text().strip() if fila.query_selector("td.c7") else ""
        tds = fila.query_selector_all("td")
        texto = None
        if texto_col_idx is not None and texto_col_idx < len(tds):
            texto = tds[texto_col_idx].inner_text().strip()
        # nota desde input.quickgrade
        nota = None
        for cell in tds:
            qin = cell.query_selector("input.quickgrade")
            if qin:
                nota = qin.get_attribute("value").strip()
                break
        # fallback en columna de nota
        if nota is None and nota_col_idx is not None and nota_col_idx < len(tds):
            raw = tds[nota_col_idx].inner_text().strip()
            # intentar extraer patrón 'nota / máxima'
            m = re.search(r"(\d+[\.,]\d+)\s*/\s*(\d+[\.,]\d+)", raw)
            if m:
                nota = m.group(1)
            else:
                # fallback si no hay '/', extraer primer número decimal
                m2 = re.search(r"\d+[\.,]\d+", raw)
                if m2:
                    nota = m2.group()
        archivos = []
        if archivo_col_idx is not None and archivo_col_idx < len(tds):
            for a in tds[archivo_col_idx].query_selector_all("a"):
                archivos.append({
                    "nombre": a.inner_text().strip(),
                    "url": a.get_attribute("href")
                })
        # Obtener enlace de calificación usando el índice dinámico de nota
        link = None
        if nota_col_idx is not None and nota_col_idx < len(tds):
            grade_cell = tds[nota_col_idx]
            sel = grade_cell.query_selector("a.btn.btn-primary")
            if sel:
                link = sel.get_attribute("href")
        entregas.append({
            "alumno_id": alumno_id,
            "nombre": nombre,
            "estado": estado,
            "fecha_entrega": fecha_entrega,
            "nota": nota,
            "texto": texto,
            "archivos": archivos,
            "link_calificar": link
        })
    return entregas


def get_tareas_de_curso(browser, page, moodle_url, cuenta_id, curso, hidden_ids=None):
    # Extraer sólo lista mínima de tareas (id, título, url)
    match = re.search(r"id=(\d+)", curso.get("url", ""))
    if not match:
        return []
    cid = int(match.group(1))
    page.goto(f"{moodle_url}/course/view.php?id={cid}", wait_until="networkidle")
    tareas_info = []
    seen = set()
    for el in page.query_selector_all(".modtype_assign"):
        link_el = el.query_selector("a.aalink")
        name_el = el.query_selector(".instancename")
        if not (link_el and name_el):
            continue
        url = link_el.get_attribute("href")
        nm = name_el.inner_text().strip()
        m2 = re.search(r"id=(\d+)", url)
        if not m2:
            continue
        tid = int(m2.group(1))
        if hidden_ids and tid in hidden_ids:
            continue
        if tid in seen:
            continue
        seen.add(tid)
        logger.info(f"SCRAPER: encontrada tarea '{nm}' con cmid={tid} en URL: {url}")
        tareas_info.append({"tarea_id": tid, "titulo": nm, "url": url})
    return tareas_info


def scrape_courses(moodle_url, usuario, contrasena):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, devtools=True, slow_mo=500, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()
        login_moodle(page, moodle_url, usuario, contrasena)
        logger.info("SCRAPER: Login realizado")
        cursos = get_cursos_moodle(page, moodle_url)
        browser.close()
        return cursos


def scrape_tasks(moodle_url, usuario, contrasena, curso_url, hidden_ids=None):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, devtools=True, slow_mo=500, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()
        page.on("console", lambda msg: logger.info(f"[browser] {msg.text}"))
        login_moodle(page, moodle_url, usuario, contrasena)
        logger.info("SCRAPER: Login realizado")
        curso = {"url": curso_url}
        tareas = get_tareas_de_curso(browser, page, moodle_url, None, curso, hidden_ids)
        # incluir tipo y detalles avanzados en cada tarea
        for t in tareas:
            try:
                # Usar la implementación unificada async para detalles de tarea
                details = scrape_task_details(moodle_url, usuario, contrasena, t["tarea_id"])
                t["tipo_calificacion"] = details.get("tipo_calificacion")
                t["detalles_calificacion"] = details.get("detalles_calificacion")
            except:
                t["tipo_calificacion"] = None
                t["detalles_calificacion"] = None
        browser.close()
        return tareas


def scrape_task_details(moodle_url, usuario, contrasena, tarea_id):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()
        page.on("console", lambda msg: logger.info(f"[browser] {msg.text}"))
        
        # Login
        login_moodle(page, moodle_url, usuario, contrasena)
        logger.info("SYNC SCRAPE: login realizado")
        
        # Descripción
        desc = _get_task_description_sync(page, moodle_url, tarea_id)
        
        # Advanced grading
        tipo_calificacion, detalles_calificacion = _get_advanced_grading_sync(page, moodle_url, tarea_id)
        
        # Calificacion maxima
        calificacion_maxima = _get_max_grade_sync(page, moodle_url, tarea_id)

        # Entregas
        entregas = _get_pending_submissions_sync(page, moodle_url, tarea_id)

        browser.close()
        return {
            "descripcion": desc,
            "entregas_pendientes": entregas,
            "tipo_calificacion": tipo_calificacion,
            "detalles_calificacion": detalles_calificacion,
            "calificacion_maxima": calificacion_maxima
        }


def _get_task_description_sync(page, moodle_url, tarea_id):
    view_url = f"{moodle_url}/mod/assign/view.php?id={tarea_id}"
    logger.info(f"SYNC SCRAPE: navegando a task page {view_url}")
    try:
        page.goto(view_url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_selector("div.activity-description#intro", timeout=10000)
        desc = page.inner_html("div.activity-description#intro")
        logger.info("SYNC SCRAPE: descripción extraída")
        return desc
    except Exception as e:
        logger.warning(f"SYNC SCRAPE: no se encontró descripción: {e}")
        return None


def _get_advanced_grading_sync(page, moodle_url, tarea_id):
    # Obtener contextid para advanced grading
    edit_url = f"{moodle_url}/course/modedit.php?update={tarea_id}&return=1"
    logger.info(f"SYNC SCRAPE: obteniendo contextid desde {edit_url}")
    try:
        page.goto(edit_url, wait_until="domcontentloaded", timeout=30000)
        hidden = page.query_selector("input[name='context']")
        contextid = hidden.get_attribute("value") if hidden else None
        if not contextid:
            link = page.query_selector("a[href*='/grade/grading/manage.php']")
            href = link.get_attribute("href") if link else None
            if href:
                parsed = urlparse(href)
                contextid = parse_qs(parsed.query).get('contextid',[None])[0]
    except Exception as e:
        logger.warning(f"SYNC SCRAPE: error obteniendo contextid: {e}")
        return None, None

    if not contextid:
        logger.warning("SYNC SCRAPE: no se pudo obtener contextid")
        return None, None

    # Navegar a la gestión de grading
    mg_url = f"{moodle_url}/grade/grading/manage.php?contextid={contextid}&component=mod_assign&area=submissions"
    logger.info(f"SYNC SCRAPE: navegando a advanced grading page {mg_url}")
    try:
        page.goto(mg_url, wait_until="domcontentloaded", timeout=30000)
        sel = page.wait_for_selector("select[name='setmethod']", timeout=10000)
        tipo = sel.evaluate("el => el.value") if sel else None
        detalles = None
        preview = page.query_selector(".definition-preview")
        if preview:
            detalles = preview.inner_html()
        logger.info(f"SYNC SCRAPE: tipo_calificacion='{tipo}' extraído")
        return tipo, detalles
    except Exception as e:
        logger.warning(f"SYNC SCRAPE: error advanced grading: {e}")
        return None, None


def _get_max_grade_sync(page, moodle_url, tarea_id):
    url = f"{moodle_url}/course/modedit.php?update={tarea_id}&return=1"
    logger.info(f"SYNC SCRAPE: obteniendo calificacion_maxima desde {url}")
    try:
        logger.info("SYNC SCRAPE: iniciando navegación a página de calificación")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        logger.info("SYNC SCRAPE: navegación completada, buscando campo de calificación")
        
        # Intentar encontrar el campo con timeout más corto
        try:
            inp = page.wait_for_selector("input#id_grade_modgrade_point", timeout=10000)
            if inp:
                val = inp.get_attribute("value")
                cg = float(val.replace(',', '.')) if val else None
                logger.info(f"SYNC SCRAPE: calificacion_maxima={cg}")
                return cg
        except Exception as e:
            logger.warning(f"SYNC SCRAPE: no se encontró campo de calificación: {e}")
            return None
            
    except Exception as e:
        logger.warning(f"SYNC SCRAPE: error max_grade en navegación: {e}")
    return None


def _get_pending_submissions_sync(page, moodle_url, tarea_id):
    """
    Try to get pending submissions from the grading interface.
    Uses defensive navigation and multiple fallback strategies.
    """
    logger.info(f"SYNC SCRAPE: obteniendo entregas pendientes para tarea {tarea_id}")
    grading_url = f"{moodle_url}/mod/assign/view.php?id={tarea_id}&action=grading"
    logger.info(f"SYNC SCRAPE: navegando a grading page {grading_url}")
    
    try:
        # Navigate with domcontentloaded to avoid timeouts
        page.goto(grading_url, wait_until="domcontentloaded", timeout=30000)
        logger.info("SYNC SCRAPE: navegación básica completada")
        
        # Look for the submissions table with increased timeout
        have_table = False
        try:
            page.wait_for_selector("table.generaltable", timeout=20000)
            have_table = True
            logger.info("SYNC SCRAPE: tabla encontrada")
        except:
            logger.warning("SYNC SCRAPE: tabla no encontrada directamente")
        
        # If no table, try finding and clicking a grading link
        if not have_table:
            try:
                grade_links = page.query_selector_all("a[href*='grading'], button[title*='calificar' i], button[title*='grading' i]")
                for link in grade_links:
                    try:
                        link_text = link.get_attribute("title") or link.inner_text()
                        if any(word.lower() in link_text.lower() for word in ["grade", "grading", "calificar", "evaluar"]):
                            link.click()
                            page.wait_for_load_state("networkidle", timeout=10000)
                            if page.query_selector("table.generaltable"):
                                have_table = True
                                break
                    except:
                        continue
            except Exception as e:
                logger.warning(f"SYNC SCRAPE: error buscando enlaces alternativos: {e}")
        
        if not have_table:
            logger.warning("SYNC SCRAPE: no se pudo encontrar tabla de entregas")
            return []
            
        # Try resetting the filter if it exists
        try:
            filter_sel = page.wait_for_selector("select#id_filter", timeout=10000)
            if filter_sel:
                page.select_option("select#id_filter", "")
                logger.info("SYNC SCRAPE: filtro reseteado")
                # Brief wait for table refresh
                page.wait_for_timeout(2000)
        except Exception as e:
            logger.info(f"SYNC SCRAPE: no se encontró filtro o no se pudo resetear: {e}")
        
        # Get submissions
        entregas = get_entregas_pendientes(page, tarea_id)
        logger.info(f"SYNC SCRAPE: {len(entregas)} entregas extraídas")
        return entregas
        
    except Exception as e:
        logger.warning(f"SYNC SCRAPE: error obteniendo entregas pendientes: {e}")
        return []


async def login_moodle_async(page, moodle_url, usuario, contrasena):
    login_url = f"{moodle_url}/login/index.php"
    logger.info(f"LOGIN ASYNC: navegando a {login_url}")
    await page.goto(login_url, wait_until="networkidle")
    logger.info("LOGIN ASYNC: esperando selector 'form#login'")
    await page.wait_for_selector("form#login", timeout=15000)
    logger.info("LOGIN ASYNC: 'form#login' visible")
    logger.info("LOGIN ASYNC: esperando selector 'input[name=logintoken]'")
    await page.wait_for_selector("input[name='logintoken']", state="attached", timeout=15000)
    logger.info("LOGIN ASYNC: 'logintoken' attached")
    await page.fill("input[name='username']", usuario)
    logger.info("LOGIN ASYNC: username llenado")
    await page.fill("input[name='password']", contrasena)
    logger.info("LOGIN ASYNC: password llenado")
    await page.click("button#loginbtn")
    logger.info("LOGIN ASYNC: clic en loginbtn")
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except:
        pass
    # Comprobar rápidamente si hay mensaje de error de login sin esperar
    error_el = await page.query_selector("#loginerrormessage")
    if error_el:
        mensaje = await error_el.inner_text()
        raise Exception(f"Login fallido: {mensaje}")


async def get_entregas_pendientes_async(page, tarea_id):
    entregas = []
    
    try:
        header_cells = await page.query_selector_all("table.generaltable thead th")
    except Exception as e:
        logger.warning(f"ASYNC SCRAPE: no se encontró tabla de encabezados: {e}")
        header_cells = []
        
    archivo_col_idx = texto_col_idx = nota_col_idx = nombre_col_idx = None
    
    for idx, th in enumerate(header_cells):
        try:
            txt = (await th.inner_text()).strip()
            logger.info(f"DEBUG ASYNC: Columna {idx}: '{txt}'")
        except:
            continue
            
        if "Archivos enviados" in txt:
            archivo_col_idx = idx
        if "Texto en línea" in txt:
            texto_col_idx = idx
        if ("Nota" in txt or "Calificación" in txt) and nota_col_idx is None:
            nota_col_idx = idx
        if "Nombre" in txt or "Apellidos" in txt:
            nombre_col_idx = idx
            logger.info(f"DEBUG ASYNC: Columna nombre detectada en índice {idx}")
            
    filas = await page.query_selector_all("table.generaltable tbody tr")
    for fila in filas:
        cb = await fila.query_selector("input[name='selectedusers']")
        if not cb:
            continue
        alumno_id = (await cb.get_attribute("value")).strip()
        
        # Extracción mejorada de nombre (Async)
        nombre = ""
        tds = await fila.query_selector_all("td")
        
        # 1. Por columna detectada
        if nombre_col_idx is not None and nombre_col_idx < len(tds):
            try:
                nombre = (await tds[nombre_col_idx].inner_text()).strip()
            except: pass
            
        # 2. Fallback: buscar link de usuario en columnas comunes o cualquier link a /user/view.php
        if not nombre:
            try:
                # Intentar selector clásico c2
                link = await fila.query_selector("td.c2 a")
                if link:
                    href = await link.get_attribute("href")
                    if href and "user/view.php" in href:
                        nombre = (await link.inner_text()).strip()
                
                # Si falla, buscar cualquier link de usuario en la fila
                if not nombre:
                    links = await fila.query_selector_all("a[href*='user/view.php']")
                    for l in links:
                        txt = (await l.inner_text()).strip()
                        if txt and len(txt) > 2:
                            nombre = txt
                            break
                            
                # Fallback final: buscar imagen de perfil
                if not nombre:
                    img = await fila.query_selector("img.userpicture")
                    if img:
                        alt = await img.get_attribute("alt")
                        if alt and "Imagen de" not in alt:
                            nombre = alt.replace("Imagen de", "").strip()
            except: pass

        estado_el = await fila.query_selector("td.c4 div")
        estado = (await estado_el.inner_text()).strip() if estado_el else ""
        fecha_el = await fila.query_selector("td.c7")
        fecha_entrega = (await fecha_el.inner_text()).strip() if fecha_el else ""
        tds = await fila.query_selector_all("td")
        texto = None
        if texto_col_idx is not None and texto_col_idx < len(tds):
            texto = (await tds[texto_col_idx].inner_text()).strip()
        nota = None
        for cell in tds:
            qin = await cell.query_selector("input.quickgrade")
            if qin:
                nota = (await qin.get_attribute("value")).strip()
                break
        if nota is None and nota_col_idx is not None and nota_col_idx < len(tds):
            raw = (await tds[nota_col_idx].inner_text()).strip()
            # intentar extraer patrón 'nota / máxima'
            m = re.search(r"(\d+[\.,]\d+)\s*/\s*(\d+[\.,]\d+)", raw)
            if m:
                nota = m.group(1)
            else:
                # fallback si no hay '/', extraer primer número decimal
                m2 = re.search(r"\d+[\.,]\d+", raw)
                if m2:
                    nota = m2.group()
        archivos = []
        if archivo_col_idx is not None and archivo_col_idx < len(tds):
            links = await tds[archivo_col_idx].query_selector_all("a")
            for a in links:
                archivos.append({
                    "nombre": (await a.inner_text()).strip(),
                    "url": await a.get_attribute("href")
                })
        # Obtener enlace de calificación usando el índice dinámico de nota
        link = None
        if nota_col_idx is not None and nota_col_idx < len(tds):
            grade_cell = tds[nota_col_idx]
            sel = await grade_cell.query_selector("a.btn.btn-primary")
            if sel:
                link = await sel.get_attribute("href")
        entregas.append({
            "alumno_id": alumno_id,
            "nombre": nombre,
            "estado": estado,
            "fecha_entrega": fecha_entrega,
            "nota": nota,
            "texto": texto,
            "archivos": archivos,
            "link_calificar": link
        })
    return entregas


async def _get_contextid_async(page, moodle_url, tarea_id):
    """
    Attempts to get the context ID for advanced grading in multiple ways.
    Returns None if advanced grading is not available.
    """
    try:
        # Navigate to module settings to retrieve context
        logger.info(f"SCRAPER: buscando contextid para cmid={tarea_id}")
        await page.goto(f"{moodle_url}/course/modedit.php?update={tarea_id}", wait_until="domcontentloaded")
        
        # First try the hidden input (fastest)
        try:
            hidden = await page.query_selector("input[name='context']")
            if hidden:
                value = await hidden.get_attribute("value")
                if value:
                    return value
        except:
            pass
            
        # Then try finding the grading link (alternative method)
        try:
            links = await page.query_selector_all("a[href*='/grade/grading/manage.php']")
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    parsed = urlparse(href)
                    qs = parse_qs(parsed.query)
                    contextid = qs.get('contextid', [None])[0]
                    if contextid:
                        return contextid
        except:
            pass
            
        # If we get here, no context ID was found
        logger.info(f"No advanced grading context found for task {tarea_id}")
        return None
            
    except Exception as e:
        logger.warning(f"Error getting context ID for task {tarea_id}: {e}")
        return None


async def _get_advanced_grading_async(page, moodle_url, contextid):
    """
    Gets the advanced grading configuration if available.
    Returns (None, None) if advanced grading is not configured.
    """
    if not contextid:
        return None, None
        
    try:
        # Navigate to grading management page
        url = f"{moodle_url}/grade/grading/manage.php?contextid={contextid}&component=mod_assign&area=submissions"
        await page.goto(url, wait_until="domcontentloaded")
        
        # Look for grading method selector with shorter timeout
        try:
            select = await page.wait_for_selector("select[name='setmethod']", timeout=5000)
            if not select:
                return None, None
                
            # Get selected grading type
            tipo = await select.evaluate("el => el.value")
            
            # Try to get preview content if available
            detalles = None
            try:
                preview = await page.query_selector(".definition-preview")
                if preview:
                    detalles = await preview.inner_html()
            except:
                pass
                
            return tipo, detalles
            
        except Exception as e:
            logger.info(f"No grading method selector found: {e}")
            return None, None
            
    except Exception as e:
        logger.warning(f"Error accessing advanced grading page: {e}")
        return None, None


async def _get_task_description_async(page, moodle_url, tarea_id):
    """
    Get task description with improved error handling and multiple selector attempts.
    """
    logger.info(f"SCRAPER: obteniendo descripción para tarea {tarea_id}")
    view_url = f"{moodle_url}/mod/assign/view.php?id={tarea_id}"
    
    logger.info(f"SCRAPER: ID de tarea procesado: cmid={tarea_id}")
    
    try:
        await page.goto(view_url, wait_until="domcontentloaded", timeout=15000)
        logger.info(f"SCRAPER: navegación a {view_url} completada")

        # Try multiple selector strategies
        description = None
        

        # Estrategia 1: Buscar cualquier div con clase activity-description (sin esperar visibilidad)
        try:
            desc_els = await page.query_selector_all("div.activity-description")
            for desc_el in desc_els:
                html = await desc_el.inner_html()
                if html and html.strip():
                    description = html
                    logger.info("SCRAPER: descripción encontrada con .activity-description (query_selector_all)")
                    break
        except Exception as e:
            logger.info(f"SCRAPER: .activity-description (query_selector_all) no encontró descripción: {e}")

        # Estrategia 2: Buscar por id intro (sin esperar visibilidad)
        if not description:
            try:
                desc_el = await page.query_selector("#intro")
                if desc_el:
                    html = await desc_el.inner_html()
                    if html and html.strip():
                        description = html
                        logger.info("SCRAPER: descripción encontrada con #intro (query_selector)")
            except Exception as e:
                logger.info(f"SCRAPER: #intro (query_selector) no encontró descripción: {e}")

        # Estrategia 3: Otros contenedores comunes
        if not description:
            for selector in [
                "div.assignment-description",
                "div.box.generalbox",
                "div.assign-intro",
                "div[role='main'] .no-overflow"
            ]:
                try:
                    desc_els = await page.query_selector_all(selector)
                    for desc_el in desc_els:
                        html = await desc_el.inner_html()
                        if html and html.strip():
                            description = html
                            logger.info(f"SCRAPER: descripción encontrada con selector alternativo: {selector}")
                            break
                    if description:
                        break
                except Exception as e:
                    logger.info(f"SCRAPER: {selector} (query_selector_all) no encontró descripción: {e}")

        if description:
            return description
        else:
            logger.warning(f"SCRAPER: no se encontró descripción para tarea {tarea_id}")
            return None

    except Exception as e:
        logger.error(f"SCRAPER: error accediendo a descripción de tarea {tarea_id}: {e}")
        return None


async def scrape_task_details_async(page, moodle_url, tarea_id):
    """
    Version of scrape_task_details that reuses an existing logged-in page.
    This eliminates redundant logins during task synchronization.
    
    Args:
        tarea_id: El cmid (course module id) de la tarea en Moodle, NO el id interno de la BD
    """
    logger.info(f"SCRAPER: comenzando scraping de detalles para tarea con cmid={tarea_id}")
    
    # Task description first (most likely to succeed)
    desc = await _get_task_description_async(page, moodle_url, tarea_id)
    
    # Get calificación máxima if available
    max_grade = None
    try:
        await page.goto(f"{moodle_url}/course/modedit.php?update={tarea_id}&return=1", wait_until="domcontentloaded")
        input_grade = await page.query_selector("input#id_grade_modgrade_point")
        if input_grade:
            value = await input_grade.get_attribute("value")
            if value:
                max_grade = float(value.replace(',', '.'))
    except Exception as e:
        logger.warning(f"No se pudo obtener calificación máxima: {e}")

    # Advanced grading: get contextid and scrape details (optional)
    config_tipo = None
    detalles_calificacion = None
    contextid = await _get_contextid_async(page, moodle_url, tarea_id)
    if contextid:
        config_tipo, detalles_calificacion = await _get_advanced_grading_async(page, moodle_url, contextid)

    # Entregas (with improved navigation and error handling)
    try:
        # Navigate to submissions grading page
        logger.info(f"SCRAPER: navegando a vista de calificación para tarea {tarea_id}")
        grading_url = f"{moodle_url}/mod/assign/view.php?id={tarea_id}&action=grading"
        await page.goto(grading_url, wait_until="domcontentloaded")
        
        # Strategy 1: Try to find and use the grading table directly
        have_grading_table = False
        try:
            table = await page.wait_for_selector("table.generaltable", timeout=5000)
            if table:
                have_grading_table = True
        except:
            logger.info("SCRAPER: tabla de calificaciones no encontrada inmediatamente")

        # Strategy 2: If no table, look for and click a grading/calificar link
        if not have_grading_table:
            try:
                grade_links = await page.query_selector_all("a[href*='grading'], button[title*='calificar' i], button[title*='grading' i]")
                for link in grade_links:
                    link_text = (await link.get_attribute("title")) or (await link.inner_text())
                    if any(word.lower() in link_text.lower() for word in ["grade", "grading", "calificar", "evaluar"]):
                        await link.click()
                        await page.wait_for_load_state("networkidle")
                        # Check if we found the table after clicking
                        try:
                            table = await page.wait_for_selector("table.generaltable", timeout=5000)
                            if table:
                                have_grading_table = True
                                break
                        except:
                            continue
            except Exception as e:
                logger.warning(f"SCRAPER: error buscando enlaces de calificación: {e}")

        # If we still don't have the table, return empty submissions
        if not have_grading_table:
            logger.info(f"SCRAPER: no se encontró tabla de calificaciones para tarea {tarea_id}")
            return {
                "descripcion": desc,
                "tipo_calificacion": config_tipo,
                "detalles_calificacion": detalles_calificacion,
                "entregas_pendientes": [],
                "calificacion_maxima": max_grade
            }

        # We have the table - try to reset filter if present
        try:
            select = await page.query_selector("select#id_filter")
            if select:
                await page.select_option("select#id_filter", "")
                await page.wait_for_timeout(2000)  # Give it time to refresh
        except Exception as e:
            logger.info(f"SCRAPER: reset de filtro falló (no crítico): {e}")
            
        # Get submissions whether filter worked or not
        entregas = await get_entregas_pendientes_async(page, tarea_id)
        logger.info(f"SCRAPER: encontradas {len(entregas)} entregas para tarea {tarea_id}")
        
        return {
            "descripcion": desc,
            "entregas_pendientes": entregas,
            "tipo_calificacion": config_tipo,
            "detalles_calificacion": detalles_calificacion,
            "calificacion_maxima": max_grade
        }
            
    except Exception as e:
        logger.error(f"SCRAPER: error procesando entregas para tarea {tarea_id}: {e}")
        return {
            "descripcion": desc,
            "tipo_calificacion": config_tipo,
            "detalles_calificacion": detalles_calificacion,
            "entregas_pendientes": [],
            "calificacion_maxima": max_grade
        }
