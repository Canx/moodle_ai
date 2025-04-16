# backend/scraper.py
from playwright.sync_api import sync_playwright


def obtener_cursos_desde_moodle(usuario, contrasena, moodle_url):
    cursos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

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
            browser.close()
            raise Exception("Credenciales incorrectas")

        print("[INFO] Navegando a la tabla de cursos personalizada")
        try:
            page.goto(f"{moodle_url}/local/gvaaules/view.php", wait_until="networkidle")
        except Exception as e:
            print(f"[ERROR] No se pudo acceder a /local/gvaaules/view.php: {e}")
            browser.close()
            raise Exception("No se pudo acceder a la lista de cursos personalizada")

        print("[INFO] Buscando cursos en la tabla personalizada")
        filas = page.query_selector_all("table tbody tr")
        for fila in filas:
            enlace = fila.query_selector("td.c2 a")
            if enlace:
                nombre = enlace.inner_text()
                href = enlace.get_attribute("href")
                cursos.append({"nombre": nombre, "url": href})

        browser.close()
    return cursos


def obtener_tareas_desde_moodle(usuario: str, contrasena: str, moodle_url: str, curso_id: int):
    """
    Función de scraping para obtener las tareas de un curso específico desde Moodle.
    """
    import requests
    from bs4 import BeautifulSoup

    # Simular inicio de sesión en Moodle
    session = requests.Session()
    login_url = f"{moodle_url}/login/index.php"
    login_response = session.post(login_url, data={"username": usuario, "password": contrasena})

    if login_response.status_code != 200 or "login" in login_response.url:
        raise Exception("Inicio de sesión fallido. Verifica las credenciales.")

    # Acceder a la página del curso
    curso_url = f"{moodle_url}/course/view.php?id={curso_id}"
    response = session.get(curso_url)
    if response.status_code != 200:
        raise Exception("No se pudo acceder al curso. Verifica el ID del curso.")

    # Parsear la página para obtener las tareas
    soup = BeautifulSoup(response.text, "html.parser")
    tareas = []
    for tarea in soup.select(".activity.assign"):
        nombre = tarea.select_one(".instancename").text.strip()
        enlace = tarea.find("a")["href"]
        tareas.append({"nombre": nombre, "enlace": enlace})

    return tareas
