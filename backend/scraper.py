from playwright.sync_api import sync_playwright
import re

def login_moodle(page, moodle_url, usuario, contrasena):
    login_url = f"{moodle_url}/login/index.php"
    print("[INFO] Accediendo a:", login_url)
    page.goto(login_url, wait_until="networkidle")
    # Esperar form y token de validación
    try:
        page.wait_for_selector("form#login", timeout=5000)
        # El input logintoken es hidden, esperamos a que esté en el DOM
        page.wait_for_selector("input[name='logintoken']", state="attached", timeout=5000)
    except Exception as e:
        print(f"[ERROR] No apareció formulario de login o logintoken: {e}")
        raise
    print(f"[INFO] Introduciendo credenciales: usuario={usuario}, contraseña={'*' * len(contrasena)}")
    page.fill("input[name='username']", usuario)
    page.fill("input[name='password']", contrasena)
    # Clic en botón de login
    try:
        page.click("button#loginbtn")
    except Exception as e:
        print(f"[ERROR] No se pudo hacer clic en loginbtn: {e}")
        raise
    # Esperar resultado de login
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except:
        pass
    if page.is_visible("#loginerrormessage"):
        mensaje_error = page.inner_text("#loginerrormessage")
        print(f"[ERROR] Login fallido: {mensaje_error}")
        raise Exception(mensaje_error)

def get_cursos_moodle(page, moodle_url):
    print("[INFO] Navegando a la tabla de cursos personalizada")
    try:
        page.goto(f"{moodle_url}/local/gvaaules/view.php", wait_until="networkidle")
    except Exception as e:
        print(f"[ERROR] No se pudo acceder a /local/gvaaules/view.php: {e}")
        raise Exception("No se pudo acceder a la lista de cursos personalizada")
    print("[INFO] Buscando cursos en la tabla personalizada")
    cursos = []
    filas = page.query_selector_all("table tbody tr")
    for fila in filas:
        enlace = fila.query_selector("td.c2 a")
        if enlace:
            nombre = enlace.inner_text()
            href = enlace.get_attribute("href")
            cursos.append({"nombre": nombre, "url": href})
    print(f"[DEBUG] Cursos encontrados: {len(cursos)}")
    for c in cursos:
        print(f"[DEBUG] Curso: {c['nombre']} - {c['url']}")
    return cursos

def get_tareas_de_curso(browser, page, moodle_url, cuenta_id, curso):
    match = re.search(r"id=(\d+)", curso["url"])
    if not match:
        return []
    curso_id = int(match.group(1))
    tareas_dict = {}
    try:
        page.goto(f"{moodle_url}/course/view.php?id={curso_id}", wait_until="networkidle")
    except Exception as e:
        print(f"[ERROR] No se pudo acceder al curso {curso_id}: {e}")
        return []
    actividades = page.query_selector_all(".modtype_assign")
    print(f"[DEBUG] Curso {curso_id}: {len(actividades)} actividades tipo 'assign' encontradas")
    for actividad in actividades:
        enlace_elem = actividad.query_selector("a.aalink")
        nombre_elem = actividad.query_selector(".instancename")
        if enlace_elem and nombre_elem:
            url_tarea = enlace_elem.get_attribute("href")
            nombre_tarea = nombre_elem.inner_text().strip()
            tarea_id_match = re.search(r"id=(\d+)", url_tarea)
            if tarea_id_match:
                tarea_id = int(tarea_id_match.group(1))
                if tarea_id not in tareas_dict:
                    tareas_dict[tarea_id] = {
                        "cuenta_id": cuenta_id,
                        "tarea_id": tarea_id,
                        "titulo": nombre_tarea,
                        "url": url_tarea
                    }
                    print(f"[DEBUG] Tarea encontrada: {nombre_tarea} - {url_tarea}")
    tareas = list(tareas_dict.values())
    print(f"[DEBUG] Total tareas únicas para curso {curso_id}: {len(tareas)}")

    # Scraping de entregas pendientes para cada tarea
    for tarea in tareas:
        # Scraping de calificación máxima
        try:
            edit_url = f"{moodle_url}/course/modedit.php?update={tarea['tarea_id']}"
            page.goto(edit_url, wait_until="networkidle")
            try:
                # Esperar solo a que el input esté en el DOM, no necesariamente visible
                page.wait_for_selector('#id_grade_modgrade_point', timeout=5000, state='attached')
                input_elem = page.query_selector('#id_grade_modgrade_point')
                calif_val = input_elem.get_attribute('value') if input_elem else None
                tarea['calificacion_maxima'] = float(calif_val) if calif_val else None
                print(f"[DEBUG] Calificación máxima para tarea '{tarea['titulo']}': {tarea['calificacion_maxima']}")
            except Exception as e:
                print(f"[WARN] No se pudo obtener calificación máxima para tarea {tarea['titulo']}: {e}")
                tarea['calificacion_maxima'] = None
        except Exception as e:
            print(f"[WARN] No se pudo acceder a la página de edición para tarea {tarea['titulo']}: {e}")
            tarea['calificacion_maxima'] = None
        # Scraping de entregas pendientes
        try:
            grading_url = f"{moodle_url}/mod/assign/view.php?id={tarea['tarea_id']}&action=grading"
            # Evitar bloqueo: establecer timeout y cargar DOM básico
            page.goto(grading_url, timeout=15000, wait_until="domcontentloaded")
            page.wait_for_selector("table.generaltable", timeout=5000)
            # Seleccionar 'Sin filtro' para mostrar todas las entregas
            page.wait_for_selector("select#id_filter", timeout=5000)
            page.select_option("select#id_filter", "")
            # Esperar recarga de la tabla de entregas
            page.wait_for_selector("table.generaltable tbody tr", timeout=5000)
            entregas = get_entregas_pendientes(page, tarea['tarea_id'])
            tarea['entregas_pendientes'] = entregas
            print(f"[DEBUG] Entregas pendientes para tarea {tarea['titulo']}: {len(entregas)}")
        except Exception as e:
            print(f"[WARN] No se pudo scrapear entregas para tarea {tarea['titulo']}: {e}")
            tarea['entregas_pendientes'] = []
    return tareas

def get_entregas_pendientes(page, tarea_id):
    entregas = []
    # Detección dinámica de índices de columnas de archivos y texto en línea
    header_cells = page.query_selector_all("table.generaltable thead th")
    # DEBUG: mostrar textos de cabeceras para identificar índices
    for idx, th in enumerate(header_cells):
        hdr = th.inner_text().strip()
        print(f"[DEBUG] Header col {idx}: '{hdr}'")
    archivo_col_idx = None
    texto_col_idx = None
    nota_col_idx = None
    for idx, th in enumerate(header_cells):
        header_text = th.inner_text().strip()
        if "Archivos enviados" in header_text:
            archivo_col_idx = idx
        if "Texto en línea" in header_text:
            texto_col_idx = idx
        if "Nota" in header_text or "Calificación" in header_text:
            nota_col_idx = idx
    print(f"[DEBUG] Column indices -> archivos: {archivo_col_idx}, texto: {texto_col_idx}, nota: {nota_col_idx}")
    filas = page.query_selector_all("table.generaltable tbody tr")
    for fila in filas:
        # Extraer alumno_id desde el checkbox de selección
        checkbox = fila.query_selector("input[name='selectedusers']")
        if checkbox:
            alumno_id = checkbox.get_attribute("value").strip()
        else:
            # no es fila de alumno, saltar
            continue
        # Nombre completo del alumno
        nombre_a = fila.query_selector("td.c2 a")
        nombre = nombre_a.inner_text().strip() if nombre_a else ""
        email_td = fila.query_selector("td.c3")
        email = email_td.inner_text().strip() if email_td else ""
        estado_div = fila.query_selector("td.c4 div")
        estado = estado_div.inner_text().strip() if estado_div else ""
        fecha_entrega_td = fila.query_selector("td.c7")
        fecha_entrega = fecha_entrega_td.inner_text().strip() if fecha_entrega_td else ""
        archivos = []
        texto_en_linea = None
        nota_text = None
        # Seleccionar celdas de texto y archivos según índices detectados
        tds = fila.query_selector_all("td")
        # Obtener celda de texto en línea antes de extraer texto
        texto_td = tds[texto_col_idx] if (texto_col_idx is not None and texto_col_idx < len(tds)) else None
        texto_en_linea = texto_td.inner_text().strip() if texto_td else None
        # Extraer nota buscando en cada celda el input.quickgrade
        nota_text = None
        for cell in tds:
            qinput = cell.query_selector("input.quickgrade")
            if qinput:
                nota_text = qinput.get_attribute("value").strip()
                break
        # Fallback: buscar valor numérico en la columna de nota si está presente
        if nota_text is None and nota_col_idx is not None and nota_col_idx < len(tds):
            raw = tds[nota_col_idx].inner_text().strip()
            match = re.search(r"\d+[\.,]\d+", raw)
            if match:
                nota_text = match.group()
                print(f"[DEBUG] Extracted grade='{nota_text}' from nota column raw='{raw}'")
        archivos_td = tds[archivo_col_idx] if (archivo_col_idx is not None and archivo_col_idx < len(tds)) else None
        if archivos_td:
            enlaces = archivos_td.query_selector_all("a")
            for enlace in enlaces:
                archivo_nombre = enlace.inner_text().strip()
                archivo_url = enlace.get_attribute("href")
                archivos.append({"nombre": archivo_nombre, "url": archivo_url})
        # Enlace de calificación manual
        link_calificar_a = fila.query_selector("td.c5 a.btn.btn-primary")
        link_calificar = link_calificar_a.get_attribute("href") if link_calificar_a else None
        # Añadir entrega si hay estado, archivo, nota o texto en línea
        if nombre or archivos or estado or nota_text or texto_en_linea:
            entregas.append({
                "alumno_id": alumno_id,
                "nombre": nombre,
                "email": email,
                "estado": estado,
                "fecha_entrega": fecha_entrega,
                "nota": nota_text,
                "texto": texto_en_linea,
                "archivos": archivos,
                "link_calificar": link_calificar
            })
        print(f"[DEBUG] Fila alumno_id={alumno_id}, nombre={nombre}, texto='{texto_en_linea}', nota='{nota_text}', archivos_count={len(archivos)}")
    return entregas

def sincronizar_cursos_y_tareas(cuenta_id, usuario, contrasena, moodle_url):
    tareas_por_curso = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        login_moodle(page, moodle_url, usuario, contrasena)
        cursos = get_cursos_moodle(page, moodle_url)
        for curso in cursos:
            match = re.search(r"id=(\d+)", curso["url"])
            if not match:
                continue
            curso_id = int(match.group(1))
            tareas = get_tareas_de_curso(browser, page, moodle_url, cuenta_id, curso)
            tareas_por_curso[curso_id] = tareas
        browser.close()
    return cursos, tareas_por_curso

def get_tarea(browser, moodle_url, usuario, contrasena, tarea_id):
    """
    Hace login y obtiene tanto la descripción HTML como las entregas pendientes de una tarea concreta.
    """
    # Crear un nuevo contexto independiente para evitar cookies de sesiones previas
    context = browser.new_context()
    page = context.new_page()
    # Configurar timeouts de navegación y operaciones para evitar hangs
    page.set_default_navigation_timeout(15000)
    page.set_default_timeout(15000)
    login_moodle(page, moodle_url, usuario, contrasena)
    descripcion_html = None
    entregas_pendientes = []
    try:
        url_tarea = f"{moodle_url}/mod/assign/view.php?id={tarea_id}"
        page.goto(url_tarea, timeout=15000, wait_until="domcontentloaded")
        try:
            page.wait_for_selector('div.activity-description#intro', timeout=5000)
            descripcion_html = page.inner_html('div.activity-description#intro')
        except Exception as e:
            print(f"[WARN] No se pudo obtener descripción para tarea en {url_tarea}: {e}")
        # Ir a la vista de grading para las entregas
        grading_url = f"{moodle_url}/mod/assign/view.php?id={tarea_id}&action=grading"
        page.goto(grading_url, timeout=15000, wait_until="domcontentloaded")
        try:
            page.wait_for_selector("table.generaltable", timeout=5000)
            # Seleccionar 'Sin filtro' para mostrar todas las entregas
            page.wait_for_selector("select#id_filter", timeout=5000)
            page.select_option("select#id_filter", "")
            # Esperar recarga de la tabla de entregas
            page.wait_for_selector("table.generaltable tbody tr", timeout=5000)
            entregas_pendientes = get_entregas_pendientes(page, tarea_id)
        except Exception as e:
            print(f"[WARN] No se pudo obtener entregas para tarea en {grading_url}: {e}")
    finally:
        # Cerrar página y contexto para no acumular cookies
        page.close()
        context.close()
    return {"descripcion": descripcion_html, "entregas_pendientes": entregas_pendientes}
