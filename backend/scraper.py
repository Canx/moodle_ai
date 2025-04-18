from playwright.sync_api import sync_playwright
import re

def login_moodle(page, moodle_url, usuario, contrasena):
    print("[INFO] Accediendo a:", f"{moodle_url}/login/index.php")
    page.goto(f"{moodle_url}/login/index.php")
    print(f"[INFO] Introduciendo credenciales: usuario={usuario}, contraseña={'*' * len(contrasena)}")
    page.fill("input[name='username']", usuario)
    page.fill("input[name='password']", contrasena)
    print("[INFO] Buscando botón de login")
    botones = page.query_selector_all("button[type='submit']")
    print(f"[INFO] Botones encontrados: {len(botones)}")
    boton_pulsado = None
    for i, b in enumerate(botones):
        texto = b.inner_text()
        visible = b.is_visible()
        print(f" - Botón {i+1}: '{texto}', visible={visible}")
        if visible and boton_pulsado is None:
            try:
                b.click()
                boton_pulsado = texto
            except Exception as e:
                print(f"[ERROR] No se pudo hacer clic en el botón {i+1}: {e}")
    if boton_pulsado:
        print(f"[INFO] Botón pulsado: '{boton_pulsado}'")
    else:
        print("[ERROR] No se pudo pulsar ningún botón visible")
    print("[INFO] Esperando que cargue la página tras login")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception as e:
        print(f"[ERROR] Timeout esperando carga tras login: {e}")
    if page.is_visible("#loginerrormessage"):
        mensaje_error = page.inner_text("#loginerrormessage")
        print(f"[ERROR] Login fallido: {mensaje_error}")
        raise Exception("Credenciales incorrectas")

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
    return tareas

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

def get_descripcion_tarea(browser, moodle_url, usuario, contrasena, url_tarea):
    """
    Hace login y obtiene la descripción HTML de una tarea concreta.
    """
    page = browser.new_page()
    login_moodle(page, moodle_url, usuario, contrasena)
    descripcion_html = None
    try:
        page.goto(url_tarea, wait_until="networkidle")
        page.wait_for_selector('div.activity-description#intro', timeout=5000)
        descripcion_html = page.inner_html('div.activity-description#intro')
    except Exception as e:
        print(f"[WARN] No se pudo obtener descripción para tarea en {url_tarea}: {e}")
    finally:
        page.close()
    return descripcion_html
