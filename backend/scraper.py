# backend/scraper.py
from playwright.sync_api import sync_playwright


def obtener_cursos_desde_moodle(usuario, contrasena, moodle_url):
    cursos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # CAMBIADO: headless=False para ver qué hace
        page = browser.new_page()

        print("[INFO] Accediendo a:", f"{moodle_url}/login/index.php")
        page.goto(f"{moodle_url}/login/index.php")

        print("[INFO] Rellenando formulario")
        page.fill("input[name='username']", usuario)
        page.fill("input[name='password']", contrasena)

        print("[INFO] Buscando botón de login")
        # Mostrar los botones detectados
        botones = page.query_selector_all("button[type='submit']")
        print(f"[INFO] Botones encontrados: {len(botones)}")
        for i, b in enumerate(botones):
            print(f" - Botón {i+1}:", b.inner_text())

        # Intentamos hacer click al primer botón visible
        for boton in botones:
            try:
                if boton.is_visible():
                    boton.click()
                    break
            except:
                continue

        print("[INFO] Esperando que cargue la página tras login")
        page.wait_for_load_state("networkidle")

        print("[INFO] Navegando al panel principal")
        page.goto(f"{moodle_url}/my/", wait_until="networkidle")

        print("[INFO] Buscando cursos")
        enlaces_cursos = page.query_selector_all(".coursebox .coursename a")
        for enlace in enlaces_cursos:
            href = enlace.get_attribute("href")
            nombre = enlace.inner_text()
            cursos.append({"nombre": nombre, "url": href})

        browser.close()
    return cursos
