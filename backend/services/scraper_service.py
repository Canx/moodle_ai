import re
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright

# Servicio puro de scraping de Moodle: sin lógica de BD ni endpoints.

def login_moodle(page, moodle_url, usuario, contrasena):
    login_url = f"{moodle_url}/login/index.php"
    page.goto(login_url, wait_until="networkidle")
    # esperar form y token
    page.wait_for_selector("form#login", timeout=5000)
    page.wait_for_selector("input[name='logintoken']", state="attached", timeout=5000)
    page.fill("input[name='username']", usuario)
    page.fill("input[name='password']", contrasena)
    page.click("button#loginbtn")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except:
        pass
    if page.is_visible("#loginerrormessage"):
        mensaje = page.inner_text("#loginerrormessage")
        raise Exception(f"Login fallido: {mensaje}")


def get_cursos_moodle(page, moodle_url):
    page.goto(f"{moodle_url}/local/gvaaules/view.php", wait_until="networkidle")
    cursos = []
    filas = page.query_selector_all("table tbody tr")
    for fila in filas:
        enlace = fila.query_selector("td.c2 a")
        if enlace:
            cursos.append({
                "nombre": enlace.inner_text(),
                "url": enlace.get_attribute("href")
            })
    return cursos


def get_entregas_pendientes(page, tarea_id):
    entregas = []
    header_cells = page.query_selector_all("table.generaltable thead th")
    archivo_col_idx = texto_col_idx = nota_col_idx = None
    for idx, th in enumerate(header_cells):
        txt = th.inner_text().strip()
        if "Archivos enviados" in txt:
            archivo_col_idx = idx
        if "Texto en línea" in txt:
            texto_col_idx = idx
        if "Nota" in txt or "Calificación" in txt:
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
            m = re.search(r"\d+[\.,]\d+", raw)
            if m:
                nota = m.group()
        archivos = []
        if archivo_col_idx is not None and archivo_col_idx < len(tds):
            for a in tds[archivo_col_idx].query_selector_all("a"):
                archivos.append({
                    "nombre": a.inner_text().strip(),
                    "url": a.get_attribute("href")
                })
        link = None
        sel = fila.query_selector("td.c5 a.btn.btn-primary")
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
    match = re.search(r"id=(\d+)", curso.get("url", ""))
    if not match:
        return []
    cid = int(match.group(1))
    page.goto(f"{moodle_url}/course/view.php?id={cid}", wait_until="networkidle")
    # Extraer lista estática de tareas antes de navegar entre páginas
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
        if tid in seen:
            continue
        seen.add(tid)
        tareas_info.append({"tarea_id": tid, "titulo": nm, "url": url})
    # Procesar cada tarea individualmente
    tareas = []
    for info in tareas_info:
        tid = info["tarea_id"]
        # Omitir tareas ocultas si se proporcionaron
        if hidden_ids and tid in hidden_ids:
            continue
        nm = info["titulo"]
        url = info["url"]
        # Obtener calificación máxima
        calif_max = None
        try:
            page.goto(f"{moodle_url}/course/modedit.php?update={tid}", wait_until="networkidle")
            page.wait_for_selector("#id_grade_modgrade_point", timeout=5000)
            val = page.query_selector("#id_grade_modgrade_point").get_attribute("value")
            calif_max = float(val) if val else None
        except:
            calif_max = None
        # Obtener entregas pendientes
        page.goto(f"{moodle_url}/mod/assign/view.php?id={tid}&action=grading", timeout=15000, wait_until="domcontentloaded")
        page.wait_for_selector("table.generaltable", timeout=10000)
        # Seleccionar "Sin filtro" en el selector de filtro
        try:
            page.wait_for_selector("select#id_filter", timeout=5000)
            page.select_option("select#id_filter", "")
            # Esperar que la tabla se recargue con el filtro aplicado
            page.wait_for_selector("table.generaltable tbody tr", timeout=10000)
        except Exception:
            # Fallback si no existe el selector de filtro
            pass
        entregas = get_entregas_pendientes(page, tid)
        tareas.append({
            "cuenta_id": cuenta_id,
            "tarea_id": tid,
            "titulo": nm,
            "url": url,
            "calificacion_maxima": calif_max,
            "entregas_pendientes": entregas
        })
    return tareas


def get_tarea(browser, moodle_url, usuario, contrasena, tarea_id):
    with sync_playwright() as p:
        browser2 = p.chromium.launch(headless=True)
        context = browser2.new_context()
        page = context.new_page()
        login_moodle(page, moodle_url, usuario, contrasena)
        # descripción
        page.goto(f"{moodle_url}/mod/assign/view.php?id={tarea_id}", wait_until="domcontentloaded")
        desc = None
        try:
            page.wait_for_selector("div.activity-description#intro", timeout=5000)
            desc = page.inner_html("div.activity-description#intro")
        except:
            desc = None
        # entregas
        page.goto(f"{moodle_url}/mod/assign/view.php?id={tarea_id}&action=grading", timeout=15000, wait_until="networkidle")
        page.wait_for_selector("table.generaltable", timeout=10000)
        # Seleccionar "Sin filtro" para mostrar todos los registros
        try:
            page.wait_for_selector("select#id_filter", timeout=5000)
            page.select_option("select#id_filter", "")
            page.wait_for_selector("table.generaltable tbody tr", timeout=10000)
        except Exception:
            # Fallback si no existe el selector de filtro
            pass
        entregas = get_entregas_pendientes(page, tarea_id)
        browser2.close()
        return {"descripcion": desc, "entregas_pendientes": entregas}


def scrape_courses(moodle_url, usuario, contrasena):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        login_moodle(page, moodle_url, usuario, contrasena)
        cursos = get_cursos_moodle(page, moodle_url)
        browser.close()
        return cursos


def scrape_tasks(moodle_url, usuario, contrasena, curso_url, hidden_ids=None):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        login_moodle(page, moodle_url, usuario, contrasena)
        curso = {"url": curso_url}
        tareas = get_tareas_de_curso(browser, page, moodle_url, None, curso, hidden_ids)
        browser.close()
        return tareas


def scrape_task_details(moodle_url, usuario, contrasena, tarea_id):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        result = get_tarea(browser, moodle_url, usuario, contrasena, tarea_id)
        browser.close()
        return result


# Async Playwright implementation to avoid sync API in event loop
async def login_moodle_async(page, moodle_url, usuario, contrasena):
    login_url = f"{moodle_url}/login/index.php"
    await page.goto(login_url, wait_until="networkidle")
    await page.wait_for_selector("form#login", timeout=5000)
    await page.wait_for_selector("input[name='logintoken']", state="attached", timeout=5000)
    await page.fill("input[name='username']", usuario)
    await page.fill("input[name='password']", contrasena)
    await page.click("button#loginbtn")
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except:
        pass
    if await page.is_visible("#loginerrormessage"):
        mensaje = await page.inner_text("#loginerrormessage")
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
        if "Nota" in txt or "Calificación" in txt:
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
            m = re.search(r"\d+[\.,]\d+", raw)
            if m:
                nota = m.group()
        archivos = []
        if archivo_col_idx is not None and archivo_col_idx < len(tds):
            links = await tds[archivo_col_idx].query_selector_all("a")
            for a in links:
                archivos.append({
                    "nombre": (await a.inner_text()).strip(),
                    "url": await a.get_attribute("href")
                })
        sel = await fila.query_selector("td.c5 a.btn.btn-primary")
        link = await sel.get_attribute("href") if sel else None
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


async def scrape_task_details_async(moodle_url, usuario, contrasena, tarea_id):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await login_moodle_async(page, moodle_url, usuario, contrasena)
        # descripción
        desc = None
        await page.goto(f"{moodle_url}/mod/assign/view.php?id={tarea_id}", wait_until="domcontentloaded")
        try:
            await page.wait_for_selector("div.activity-description#intro", timeout=5000)
            desc = await page.inner_html("div.activity-description#intro")
        except:
            desc = None
        # entregas
        await page.goto(f"{moodle_url}/mod/assign/view.php?id={tarea_id}&action=grading", timeout=15000, wait_until="networkidle")
        await page.wait_for_selector("table.generaltable", timeout=10000)
        try:
            await page.wait_for_selector("select#id_filter", timeout=5000)
            await page.select_option("select#id_filter", "")
            await page.wait_for_selector("table.generaltable tbody tr", timeout=10000)
        except:
            pass
        entregas = await get_entregas_pendientes_async(page, tarea_id)
        await browser.close()
        return {"descripcion": desc, "entregas_pendientes": entregas}
