import re
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
import asyncio
from urllib.parse import urljoin, urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)

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
    archivo_col_idx = texto_col_idx = nota_col_idx = None
    for idx, th in enumerate(header_cells):
        try:
            txt = th.inner_text().strip()
        except Exception as e:
            logger.warning(f"SYNC SCRAPE: error leyendo encabezado idx {idx}: {e}")
            continue
        if "Archivos enviados" in txt:
            archivo_col_idx = idx
        if "Texto en línea" in txt:
            texto_col_idx = idx
        if ("Nota" in txt or "Calificación" in txt) and nota_col_idx is None:
            nota_col_idx = idx
    filas = page.query_selector_all("table.generaltable tbody tr")
    for fila in filas:
        cb = fila.query_selector("input[name='selectedusers']")
        if not cb:
            continue
        alumno_id = cb.get_attribute("value").strip()
        nombre = fila.query_selector("td.c2 a").inner_text().strip() if fila.query_selector("td.c2 a") else ""
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
        tareas_info.append({"tarea_id": tid, "titulo": nm, "url": url})
    return tareas_info


def scrape_courses(moodle_url, usuario, contrasena):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, devtools=True, slow_mo=500, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()
        login_moodle(page, moodle_url, usuario, contrasena)
        print("SCRAPER: Login realizado")
        logger.info(" Login realizado")
        cursos = get_cursos_moodle(page, moodle_url)
        browser.close()
        return cursos


def scrape_tasks(moodle_url, usuario, contrasena, curso_url, hidden_ids=None):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, devtools=True, slow_mo=500, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()
        page.on("console", lambda msg: logger.info(f"[browser] {msg.text}"))
        login_moodle(page, moodle_url, usuario, contrasena)
        print("SCRAPER: Login realizado")
        logger.info(" Login realizado")
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
    # Navegar y obtener entregas pendientes de la tarea
    logger.info(f"SYNC SCRAPE: obteniendo entregas pendientes para tarea {tarea_id}")
    grading_url = f"{moodle_url}/mod/assign/view.php?id={tarea_id}&action=grading"
    logger.info(f"SYNC SCRAPE: navegando a grading page {grading_url}")
    try:
        # Usar domcontentloaded en lugar de networkidle para evitar esperas indefinidas
        page.goto(grading_url, wait_until="domcontentloaded", timeout=30000)
        logger.info("SYNC SCRAPE: navegación básica completada")
        
        # Esperar la tabla con timeout aumentado
        page.wait_for_selector("table.generaltable", timeout=20000)
        logger.info("SYNC SCRAPE: tabla encontrada")
        
        # Intentar resetear el filtro si existe
        try:
            filter_sel = page.wait_for_selector("select#id_filter", timeout=10000)
            if filter_sel:
                page.select_option("select#id_filter", "")
                logger.info("SYNC SCRAPE: filtro reseteado")
                # Breve espera para que se actualice la tabla
                page.wait_for_timeout(2000)
        except Exception as e:
            logger.info(f"SYNC SCRAPE: no se encontró filtro o no se pudo resetear: {e}")
        
        # Esperar al menos una fila en la tabla
        page.wait_for_selector("table.generaltable tbody tr", timeout=20000)
        logger.info("SYNC SCRAPE: al menos una fila encontrada")
        
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
    header_cells = await page.query_selector_all("table.generaltable thead th")
    archivo_col_idx = texto_col_idx = nota_col_idx = None
    for idx, th in enumerate(header_cells):
        txt = await th.inner_text()
        if "Archivos enviados" in txt:
            archivo_col_idx = idx
        if "Texto en línea" in txt:
            texto_col_idx = idx
        if ("Nota" in txt or "Calificación" in txt) and nota_col_idx is None:
            nota_col_idx = idx
    filas = await page.query_selector_all("table.generaltable tbody tr")
    for fila in filas:
        cb = await fila.query_selector("input[name='selectedusers']")
        if not cb:
            continue
        alumno_id = (await cb.get_attribute("value")).strip()
        nombre_el = await fila.query_selector("td.c2 a")
        nombre = (await nombre_el.inner_text()).strip() if nombre_el else ""
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
    # Navigate to module settings to retrieve context
    await page.goto(f"{moodle_url}/course/modedit.php?update={tarea_id}", wait_until="networkidle")
    hidden = await page.query_selector("input[name='context']")
    if hidden:
        return await hidden.get_attribute("value")
    link = await page.wait_for_selector("a[href*='/grade/grading/manage.php']", timeout=5000)
    href = await link.get_attribute("href")
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    return qs.get('contextid', [None])[0]


async def _get_advanced_grading_async(page, moodle_url, contextid):
    # Scrape grading type and preview from manage.php
    url = f"{moodle_url}/grade/grading/manage.php?contextid={contextid}&component=mod_assign&area=submissions"
    await page.goto(url, wait_until="networkidle")
    select = await page.wait_for_selector("select[name='setmethod']", timeout=5000)
    # list options for debug
    opts = await select.query_selector_all("option")
    for o in opts:
        val = await o.evaluate("el => el.value")
        txt = await o.evaluate("el => el.textContent")
        sel = await o.get_attribute("selected")
        print(f"DEBUG option: value={val!r}, selected={sel!r}, text={txt!r}")
    tipo = await select.evaluate("el => el.value")
    preview_sel = ".definition-preview"
    detalles = None
    if await page.query_selector(preview_sel):
        detalles = await page.inner_html(preview_sel)
    return tipo, detalles


async def _get_task_description_async(page, moodle_url, tarea_id):
    # Scrape task description
    await page.goto(f"{moodle_url}/mod/assign/view.php?id={tarea_id}", wait_until="domcontentloaded")
    try:
        await page.wait_for_selector("div.activity-description#intro", timeout=5000)
        return await page.inner_html("div.activity-description#intro")
    except:
        return None


async def scrape_task_details_async(page, moodle_url, tarea_id):
    """
    Version of scrape_task_details that reuses an existing logged-in page.
    This eliminates redundant logins during task synchronization.
    """
    # Advanced grading: get contextid and scrape details
    contextid = await _get_contextid_async(page, moodle_url, tarea_id)
    config_tipo, detalles_calificacion = await _get_advanced_grading_async(page, moodle_url, contextid)

    # Task description
    desc = await _get_task_description_async(page, moodle_url, tarea_id)

    # Entregas
    await page.goto(f"{moodle_url}/mod/assign/view.php?id={tarea_id}&action=grading", wait_until="networkidle")
    await page.wait_for_selector("table.generaltable", timeout=10000)
    try:
        await page.wait_for_selector("select#id_filter", timeout=5000)
        await page.select_option("select#id_filter", "")
        await page.wait_for_selector("table.generaltable tbody tr", timeout=10000)
    except:
        pass
        
    entregas = await get_entregas_pendientes_async(page, tarea_id)
    
    # Obtener calificación máxima si está disponible
    max_grade = None
    try:
        await page.goto(f"{moodle_url}/course/modedit.php?update={tarea_id}&return=1", wait_until="networkidle")
        input_grade = await page.query_selector("input#id_grade_modgrade_point")
        if input_grade:
            value = await input_grade.get_attribute("value")
            if value:
                max_grade = float(value.replace(',', '.'))
    except Exception as e:
        logger.warning(f"No se pudo obtener calificación máxima: {e}")

    return {
        "descripcion": desc,
        "entregas_pendientes": entregas,
        "tipo_calificacion": config_tipo,
        "detalles_calificacion": detalles_calificacion,
        "calificacion_maxima": max_grade
    }
