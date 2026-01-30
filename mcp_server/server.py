from fastmcp import FastMCP
import sys
import os
import json
import logging
import asyncio
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from playwright.async_api import async_playwright

# Fuzzy matching
try:
    from rapidfuzz import fuzz, process as fuzz_process
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    logging.warning("rapidfuzz no disponible, fuzzy matching desactivado")

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

mcp = FastMCP("Moodle AI Assistant (Cached) - Improved")

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

# --- Parsear fecha de Moodle ---
def parse_moodle_date(date_str: str) -> Optional[datetime]:
    """Convierte strings de fecha de Moodle a datetime"""
    if not date_str or date_str.strip() == "":
        return None
    
    # Formato común: "26 de enero de 2026, 13:02"
    # O: "26 January 2026, 13:02"
    # O: "26/01/2026 13:02"
    
    formats = [
        "%d de %B de %Y, %H:%M",  # español
        "%d de %b de %Y, %H:%M",
        "%d %B %Y, %H:%M",
        "%d %b %Y, %H:%M", 
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except:
            continue
    
    logger.warning(f"No se pudo parsear fecha: {date_str}")
    return None

# --- Helpers de Scraping (iguales a antes) ---

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

# --- Helpers de Análisis de Documentos (igual) ---

def extract_text_from_docx(file_path):
    import docx
    try:
        doc = docx.Document(file_path)
        text = []
        for para in doc.paragraphs:
            text.append(para.text)
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

async def convert_office_to_html(file_path):
    """Convierte DOCX/ODT a HTML usando LibreOffice. Devuelve (html_content, text_content) o None si falla."""
    import uuid as _uuid
    try:
        out_dir = os.path.join(os.path.dirname(file_path), f"convert_{_uuid.uuid4()}")
        os.makedirs(out_dir, exist_ok=True)

        cmd = f"libreoffice --headless --convert-to html --outdir '{out_dir}' '{file_path}'"
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

        if proc.returncode != 0:
            logger.warning(f"LibreOffice falló (código {proc.returncode}): {stderr.decode()}")
            return None

        html_files = [f for f in os.listdir(out_dir) if f.endswith(".html")]
        if not html_files:
            logger.warning("LibreOffice no generó archivo HTML")
            return None

        html_path = os.path.join(out_dir, html_files[0])
        with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
            html_raw = f.read()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_raw, "html.parser")
        text_content = soup.get_text(separator="\n\n")

        return {"html_raw": html_raw, "text": text_content}
    except asyncio.TimeoutError:
        logger.warning("LibreOffice timeout (60s)")
        return None
    except Exception as e:
        logger.warning(f"Error conversión LibreOffice: {e}")
        return None

def extract_text_from_pdf(file_path):
    """Extrae texto de PDF usando PyMuPDF o pdfplumber"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        text = []
        for page in doc:
            text.append(page.get_text())
        doc.close()
        return "\n".join(text)
    except ImportError:
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text = []
                for page in pdf.pages:
                    text.append(page.extract_text() or "")
                return "\n".join(text)
        except ImportError:
            return "Error: No hay librería de PDF disponible (instala pymupdf o pdfplumber)"
    except Exception as e:
        return f"Error leyendo PDF: {e}"

def extract_text_from_html(file_path):
    """Extrae texto de HTML"""
    try:
        from bs4 import BeautifulSoup
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
            # Eliminar scripts y styles
            for tag in soup(['script', 'style']):
                tag.decompose()
            return soup.get_text(separator='\n', strip=True)
    except ImportError:
        # Fallback sin BeautifulSoup
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            import re
            content = f.read()
            # Eliminar tags HTML básico
            clean = re.sub(r'<[^>]+>', ' ', content)
            return re.sub(r'\s+', ' ', clean).strip()
    except Exception as e:
        return f"Error leyendo HTML: {e}"

def extract_text_from_txt(file_path):
    """Lee archivo de texto plano"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"Error leyendo TXT: {e}"

def extract_text_from_ods(file_path):
    """Extrae texto de hojas de cálculo ODS/XLSX"""
    try:
        import openpyxl
        # openpyxl no lee ODS directamente, pero odfpy sí
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".ods":
            from odf.opendocument import load
            from odf import text, table, teletype
            doc = load(file_path)
            all_text = []
            for t in doc.getElementsByType(table.Table):
                table_name = t.getAttribute("name") or "Hoja"
                all_text.append(f"--- {table_name} ---")
                for row in t.getElementsByType(table.TableRow):
                    cells = []
                    for cell in row.getElementsByType(table.TableCell):
                        cell_text = ""
                        for p in cell.getElementsByType(text.P):
                            cell_text += teletype.extractText(p)
                        cells.append(cell_text)
                    if any(c.strip() for c in cells):
                        all_text.append(" | ".join(cells))
            return "\n".join(all_text)
        else:
            # XLSX
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            all_text = []
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                all_text.append(f"--- {sheet_name} ---")
                for row in ws.iter_rows(values_only=True):
                    cells = [str(c) if c is not None else "" for c in row]
                    if any(c.strip() for c in cells):
                        all_text.append(" | ".join(cells))
            wb.close()
            return "\n".join(all_text)
    except Exception as e:
        return f"Error leyendo hoja de cálculo: {e}"

def extract_scratch_project(file_path):
    """
    Extrae información y código de un proyecto Scratch (.sb3).
    Devuelve pseudocódigo legible de cada sprite/escenario.
    """
    import zipfile

    # Mapeo de opcodes a texto legible
    OPCODE_MAP = {
        # Eventos
        "event_whenflagclicked": "al presionar bandera verde",
        "event_whenkeypressed": "al presionar tecla {KEY_OPTION}",
        "event_whenthisspriteclicked": "al hacer clic en este sprite",
        "event_whenbackdropswitchesto": "al cambiar fondo a {BACKDROP}",
        "event_whengreaterthan": "cuando {WHENGREATERTHANMENU} > {VALUE}",
        "event_whenbroadcastreceived": "al recibir {BROADCAST_OPTION}",
        "event_broadcast": "enviar mensaje {BROADCAST_INPUT}",
        "event_broadcastandwait": "enviar mensaje {BROADCAST_INPUT} y esperar",
        # Movimiento
        "motion_movesteps": "mover {STEPS} pasos",
        "motion_turnright": "girar ↻ {DEGREES} grados",
        "motion_turnleft": "girar ↺ {DEGREES} grados",
        "motion_goto": "ir a {TO}",
        "motion_gotoxy": "ir a x:{X} y:{Y}",
        "motion_glideto": "deslizar en {SECS}s a {TO}",
        "motion_glidesecstoxy": "deslizar en {SECS}s a x:{X} y:{Y}",
        "motion_pointindirection": "apuntar en dirección {DIRECTION}",
        "motion_pointtowards": "apuntar hacia {TOWARDS}",
        "motion_changexby": "cambiar x en {DX}",
        "motion_setx": "fijar x a {X}",
        "motion_changeyby": "cambiar y en {DY}",
        "motion_sety": "fijar y a {Y}",
        "motion_ifonedgebounce": "si toca el borde, rebotar",
        "motion_setrotationstyle": "fijar estilo de rotación {STYLE}",
        # Apariencia
        "looks_sayforsecs": "decir {MESSAGE} durante {SECS}s",
        "looks_say": "decir {MESSAGE}",
        "looks_thinkforsecs": "pensar {MESSAGE} durante {SECS}s",
        "looks_think": "pensar {MESSAGE}",
        "looks_switchcostumeto": "cambiar disfraz a {COSTUME}",
        "looks_nextcostume": "siguiente disfraz",
        "looks_switchbackdropto": "cambiar fondo a {BACKDROP}",
        "looks_changesizeby": "cambiar tamaño en {CHANGE}",
        "looks_setsizeto": "fijar tamaño a {SIZE}%",
        "looks_show": "mostrar",
        "looks_hide": "esconder",
        "looks_changeeffectby": "cambiar efecto {EFFECT} en {CHANGE}",
        "looks_seteffectto": "fijar efecto {EFFECT} a {VALUE}",
        "looks_cleargraphiceffects": "quitar efectos gráficos",
        "looks_gotofrontback": "ir a capa {FRONT_BACK}",
        # Sonido
        "sound_playuntildone": "tocar sonido {SOUND_MENU} hasta terminar",
        "sound_play": "tocar sonido {SOUND_MENU}",
        "sound_stopallsounds": "detener todos los sonidos",
        "sound_changevolumeby": "cambiar volumen en {VOLUME}",
        "sound_setvolumeto": "fijar volumen a {VOLUME}%",
        # Control
        "control_wait": "esperar {DURATION}s",
        "control_repeat": "repetir {TIMES} veces",
        "control_forever": "por siempre",
        "control_if": "si {CONDITION} entonces",
        "control_if_else": "si {CONDITION} entonces / si no",
        "control_wait_until": "esperar hasta que {CONDITION}",
        "control_repeat_until": "repetir hasta que {CONDITION}",
        "control_stop": "detener {STOP_OPTION}",
        "control_start_as_clone": "al comenzar como clon",
        "control_create_clone_of": "crear clon de {CLONE_OPTION}",
        "control_delete_this_clone": "eliminar este clon",
        # Sensores
        "sensing_touchingobject": "¿tocando {TOUCHINGOBJECTMENU}?",
        "sensing_touchingcolor": "¿tocando color {COLOR}?",
        "sensing_distanceto": "distancia a {DISTANCETOMENU}",
        "sensing_askandwait": "preguntar {QUESTION} y esperar",
        "sensing_answer": "respuesta",
        "sensing_keypressed": "¿tecla {KEY_OPTION} presionada?",
        "sensing_mousedown": "¿ratón presionado?",
        "sensing_mousex": "posición x del ratón",
        "sensing_mousey": "posición y del ratón",
        "sensing_timer": "cronómetro",
        "sensing_resettimer": "reiniciar cronómetro",
        # Operadores
        "operator_add": "{NUM1} + {NUM2}",
        "operator_subtract": "{NUM1} - {NUM2}",
        "operator_multiply": "{NUM1} * {NUM2}",
        "operator_divide": "{NUM1} / {NUM2}",
        "operator_random": "número al azar entre {FROM} y {TO}",
        "operator_gt": "{OPERAND1} > {OPERAND2}",
        "operator_lt": "{OPERAND1} < {OPERAND2}",
        "operator_equals": "{OPERAND1} = {OPERAND2}",
        "operator_and": "{OPERAND1} y {OPERAND2}",
        "operator_or": "{OPERAND1} o {OPERAND2}",
        "operator_not": "no {OPERAND}",
        "operator_join": "unir {STRING1} {STRING2}",
        "operator_length": "longitud de {STRING}",
        "operator_mod": "{NUM1} módulo {NUM2}",
        "operator_round": "redondear {NUM}",
        "operator_mathop": "{OPERATOR} de {NUM}",
        # Variables
        "data_setvariableto": "fijar {VARIABLE} a {VALUE}",
        "data_changevariableby": "cambiar {VARIABLE} en {VALUE}",
        "data_showvariable": "mostrar variable {VARIABLE}",
        "data_hidevariable": "esconder variable {VARIABLE}",
        "data_addtolist": "añadir {ITEM} a {LIST}",
        "data_deleteoflist": "borrar {INDEX} de {LIST}",
        "data_deletealloflist": "borrar todo de {LIST}",
        "data_insertatlist": "insertar {ITEM} en {INDEX} de {LIST}",
        "data_replaceitemoflist": "reemplazar elemento {INDEX} de {LIST} con {ITEM}",
        "data_itemoflist": "elemento {INDEX} de {LIST}",
        "data_lengthoflist": "longitud de {LIST}",
        "data_listcontainsitem": "¿{LIST} contiene {ITEM}?",
        # Mis bloques
        "procedures_definition": "definir {custom_block}",
        "procedures_call": "llamar {proccode}",
    }

    def _get_input_value(inputs, key, blocks_dict):
        """Extrae el valor de un input de un bloque Scratch"""
        if key not in inputs:
            return "?"
        inp = inputs[key]
        if isinstance(inp, list) and len(inp) >= 2:
            val = inp[1]
            if isinstance(val, list) and len(val) >= 2:
                return str(val[1])
            elif isinstance(val, str) and val in blocks_dict:
                # Es una referencia a otro bloque
                sub = blocks_dict[val]
                if isinstance(sub, dict):
                    return _block_to_text(sub, blocks_dict, depth=0)
                return str(val)
            return str(val) if val else "?"
        return "?"

    def _get_field_value(fields, key):
        """Extrae el valor de un field de un bloque"""
        if key not in fields:
            return "?"
        field = fields[key]
        if isinstance(field, list) and len(field) >= 1:
            return str(field[0])
        return str(field)

    def _block_to_text(block, blocks_dict, depth=0):
        """Convierte un bloque a texto legible"""
        if not isinstance(block, dict):
            return str(block)

        opcode = block.get('opcode', '')
        inputs = block.get('inputs', {})
        fields = block.get('fields', {})

        template = OPCODE_MAP.get(opcode, opcode)

        # Rellenar template con valores reales
        import re
        def replace_placeholder(match):
            key = match.group(1)
            # Buscar en fields primero, luego inputs
            val = _get_field_value(fields, key)
            if val == "?":
                val = _get_input_value(inputs, key, blocks_dict)
            return val

        text = re.sub(r'\{(\w+)\}', replace_placeholder, template)

        # Procedimientos personalizados
        if opcode == "procedures_definition":
            proto_id = _get_input_value(inputs, "custom_block", blocks_dict)
            text = f"definir bloque personalizado"
        elif opcode == "procedures_call":
            proccode = block.get('mutation', {}).get('proccode', '?')
            text = f"llamar [{proccode}]"

        return text

    def _build_script(start_block_id, blocks_dict, indent=0):
        """Construye un script completo siguiendo la cadena de bloques"""
        lines = []
        current_id = start_block_id
        prefix = "  " * indent

        while current_id and current_id in blocks_dict:
            block = blocks_dict[current_id]
            if not isinstance(block, dict):
                break

            text = _block_to_text(block, blocks_dict)
            opcode = block.get('opcode', '')
            lines.append(f"{prefix}{text}")

            # Bloques con cuerpo (if, repeat, forever)
            inputs = block.get('inputs', {})
            if opcode in ['control_forever', 'control_repeat', 'control_repeat_until']:
                substack = inputs.get('SUBSTACK', [None, None])
                if isinstance(substack, list) and len(substack) >= 2 and substack[1]:
                    sub_lines = _build_script(substack[1], blocks_dict, indent + 1)
                    lines.extend(sub_lines)
                lines.append(f"{prefix}fin")

            elif opcode in ['control_if']:
                substack = inputs.get('SUBSTACK', [None, None])
                if isinstance(substack, list) and len(substack) >= 2 and substack[1]:
                    sub_lines = _build_script(substack[1], blocks_dict, indent + 1)
                    lines.extend(sub_lines)
                lines.append(f"{prefix}fin si")

            elif opcode in ['control_if_else']:
                substack = inputs.get('SUBSTACK', [None, None])
                if isinstance(substack, list) and len(substack) >= 2 and substack[1]:
                    sub_lines = _build_script(substack[1], blocks_dict, indent + 1)
                    lines.extend(sub_lines)
                lines.append(f"{prefix}si no")
                substack2 = inputs.get('SUBSTACK2', [None, None])
                if isinstance(substack2, list) and len(substack2) >= 2 and substack2[1]:
                    sub_lines = _build_script(substack2[1], blocks_dict, indent + 1)
                    lines.extend(sub_lines)
                lines.append(f"{prefix}fin si")

            current_id = block.get('next')

        return lines

    try:
        result = {"sprites": [], "blocks_count": 0, "costumes": [], "sounds": []}
        text_parts = []

        with zipfile.ZipFile(file_path, 'r') as zf:
            if 'project.json' not in zf.namelist():
                return "Error: No se encontró project.json en el SB3", {}

            project = json.loads(zf.read('project.json'))
            targets = project.get('targets', [])

            text_parts.append("# Proyecto Scratch (.sb3)\n")

            for target in targets:
                name = target.get('name', '?')
                is_stage = target.get('isStage', False)
                blocks = target.get('blocks', {})
                costumes = target.get('costumes', [])
                sounds = target.get('sounds', [])
                variables = target.get('variables', {})
                lists = target.get('lists', {})

                tipo = "Escenario" if is_stage else "Sprite"
                text_parts.append(f"\n## {tipo}: {name}")
                text_parts.append(f"Disfraces: {', '.join(c.get('name', '?') for c in costumes)}")
                if sounds:
                    text_parts.append(f"Sonidos: {', '.join(s.get('name', '?') for s in sounds)}")
                if variables:
                    var_names = [v[0] for v in variables.values()]
                    text_parts.append(f"Variables: {', '.join(var_names)}")
                if lists:
                    list_names = [l[0] for l in lists.values()]
                    text_parts.append(f"Listas: {', '.join(list_names)}")

                # Encontrar bloques raíz (top-level, sin parent)
                top_blocks = []
                for block_id, block in blocks.items():
                    if isinstance(block, dict) and block.get('topLevel', False):
                        top_blocks.append(block_id)

                # Generar código de cada script
                if top_blocks:
                    text_parts.append(f"\n### Código de {name}:\n")
                    for i, start_id in enumerate(top_blocks):
                        script_lines = _build_script(start_id, blocks)
                        if script_lines:
                            text_parts.append(f"```")
                            text_parts.extend(script_lines)
                            text_parts.append(f"```")
                            text_parts.append("")
                else:
                    text_parts.append(f"(Sin código)")

                sprite_info = {
                    'nombre': name,
                    'bloques': len(blocks),
                    'disfraces': len(costumes),
                    'sonidos': len(sounds),
                    'es_escenario': is_stage,
                    'variables': [v[0] for v in variables.values()],
                    'scripts': len(top_blocks)
                }
                result['sprites'].append(sprite_info)
                result['blocks_count'] += len(blocks)

            # Categorías de bloques
            block_types = set()
            for target in targets:
                for block_id, block in target.get('blocks', {}).items():
                    if isinstance(block, dict):
                        opcode = block.get('opcode', '')
                        category = opcode.split('_')[0] if '_' in opcode else opcode
                        block_types.add(category)
            result['categorias_bloques'] = sorted(block_types)
            result['archivos'] = zf.namelist()

        text = "\n".join(text_parts)

        # Resumen al final
        text += f"\n\n## Resumen"
        text += f"\nTotal bloques: {result['blocks_count']}"
        text += f"\nSprites: {len([s for s in result['sprites'] if not s['es_escenario']])}"
        text += f"\nCategorías: {', '.join(result['categorias_bloques'])}"

        return text, result

    except Exception as e:
        return f"Error leyendo SB3: {e}", {}


# --- Gestión de sesión persistente ---

class MoodleSession:
    """
    Gestiona una sesión de Playwright reutilizable para Moodle.
    Mantiene browser + página autenticada entre llamadas MCP.
    Se auto-renueva si la sesión caduca o el browser se cierra.
    """
    SESSION_TIMEOUT = 600  # 10 minutos sin usar → cerrar

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None
        self._download_context = None
        self._download_page = None
        self._alias = None
        self._last_used = None
        self._lock = asyncio.Lock()

    async def get_page(self, moodle_alias: str = "default") -> "Page":
        """Obtiene una página autenticada, reutilizando sesión si es posible."""
        async with self._lock:
            now = asyncio.get_event_loop().time()

            # Si hay sesión activa, verificar que sigue viva
            if self._page and self._alias == moodle_alias:
                try:
                    # Timeout check
                    if self._last_used and (now - self._last_used) > self.SESSION_TIMEOUT:
                        logger.info("Sesión Moodle expirada por timeout, reconectando...")
                        await self._cleanup()
                    else:
                        # Verificar que la página sigue respondiendo
                        await self._page.evaluate("1")
                        self._last_used = now
                        return self._page
                except Exception:
                    logger.info("Sesión Moodle caída, reconectando...")
                    await self._cleanup()

            # Crear nueva sesión
            return await self._create_session(moodle_alias)

    async def get_download_page(self, moodle_alias: str = "default") -> "Page":
        """Obtiene una página con contexto de descarga (accept_downloads=True)."""
        async with self._lock:
            now = asyncio.get_event_loop().time()

            if self._download_page and self._alias == moodle_alias:
                try:
                    if self._last_used and (now - self._last_used) > self.SESSION_TIMEOUT:
                        await self._cleanup_download()
                    else:
                        await self._download_page.evaluate("1")
                        self._last_used = now
                        return self._download_page
                except Exception:
                    await self._cleanup_download()

            return await self._create_download_session(moodle_alias)

    async def _create_session(self, moodle_alias: str) -> "Page":
        """Crea browser + página y hace login."""
        creds = get_credentials(moodle_alias)
        if not creds:
            raise ValueError("Credenciales no encontradas")

        if not self._playwright:
            self._playwright = await async_playwright().start()

        if not self._browser:
            self._browser = await self._playwright.chromium.launch(
                headless=True, args=["--no-sandbox"]
            )

        self._page = await self._browser.new_page()
        await login_moodle_async(
            self._page, creds["url"], creds["username"], creds["password"]
        )
        self._alias = moodle_alias
        self._last_used = asyncio.get_event_loop().time()
        logger.info("Nueva sesión Moodle creada y autenticada")
        return self._page

    async def _create_download_session(self, moodle_alias: str) -> "Page":
        """Crea contexto con descargas habilitadas."""
        creds = get_credentials(moodle_alias)
        if not creds:
            raise ValueError("Credenciales no encontradas")

        if not self._playwright:
            self._playwright = await async_playwright().start()

        if not self._browser:
            self._browser = await self._playwright.chromium.launch(
                headless=True, args=["--no-sandbox"]
            )

        self._download_context = await self._browser.new_context(accept_downloads=True)
        self._download_page = await self._download_context.new_page()
        await login_moodle_async(
            self._download_page, creds["url"], creds["username"], creds["password"]
        )
        self._last_used = asyncio.get_event_loop().time()
        logger.info("Sesión de descarga Moodle creada")
        return self._download_page

    async def _cleanup(self):
        """Limpia la página principal."""
        try:
            if self._page:
                await self._page.close()
        except Exception:
            pass
        self._page = None

    async def _cleanup_download(self):
        """Limpia el contexto de descarga."""
        try:
            if self._download_context:
                await self._download_context.close()
        except Exception:
            pass
        self._download_page = None
        self._download_context = None

    async def close(self):
        """Cierra todo."""
        await self._cleanup()
        await self._cleanup_download()
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        self._browser = None
        self._playwright = None
        self._alias = None
        logger.info("Sesión Moodle cerrada completamente")


# Instancia global
_session = MoodleSession()


async def get_authenticated_page(moodle_alias: str = "default"):
    """Atajo para obtener página autenticada reutilizable."""
    return await _session.get_page(moodle_alias)


async def get_download_page(moodle_alias: str = "default"):
    """Atajo para obtener página con descargas habilitadas."""
    return await _session.get_download_page(moodle_alias)


# --- Herramientas MCP ---

@mcp.tool()
async def sync_moodle(moodle_alias: str = "default", sync_courses: bool = True, sync_all_tasks: bool = False) -> str:
    creds = get_credentials(moodle_alias)
    if not creds: return "Error: Credenciales no encontradas"
    page = await get_authenticated_page(moodle_alias)
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

@mcp.tool()
async def sync_course_tasks(course_url: str, moodle_alias: str = "default") -> str:
    creds = get_credentials(moodle_alias)
    if not creds: return "Error: Credenciales no encontradas"
    page = await get_authenticated_page(moodle_alias)
    tareas = await _scrape_tasks_impl(page, creds["url"], course_url)
    db.save_tasks(moodle_alias, course_url, tareas)
    return f"Curso actualizado. {len(tareas)} tareas."

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
def search_courses(query: str, moodle_alias: str = "default") -> Dict[str, Any]:
    """
    Busca cursos por nombre en la base de datos local (caché).
    """
    cursos = db.get_courses(moodle_alias)
    last = db.get_last_sync(moodle_alias)
    if not cursos: return {"info": "Sin caché", "cursos": []}
    
    query = query.lower()
    resultados = [c for c in cursos if query in c.get("nombre", "").lower()]
    
    return {
        "info": f"Búsqueda para '{query}' en datos cacheados ({last})",
        "total_encontrados": len(resultados),
        "cursos": resultados
    }

@mcp.tool()
async def get_task_details(task_id: int, moodle_alias: str = "default") -> Dict[str, Any]:
    """
    Obtiene detalles de una tarea con información enriquecida:
    - Alumnos sin calificación
    - Reentregas detectadas
    - Timestamps de entrega y calificación
    """
    creds = get_credentials(moodle_alias)
    if not creds: return {"error": "Credenciales no encontradas"}
    page = await get_authenticated_page(moodle_alias)
    detalles = await scrape_task_details_async(page, creds["url"], task_id)

    # Enriquecer datos: agregar status y timestamps
    key_entregas = "entregas_pendientes" if "entregas_pendientes" in detalles else "entregas"
    if key_entregas in detalles:
        for entrega in detalles[key_entregas]:
            entrega["sin_calificacion"] = not entrega.get("nota") or str(entrega.get("nota")).strip() == ""
            fecha_entrega = parse_moodle_date(entrega.get("fecha_entrega", ""))
            entrega["fecha_entrega_parsed"] = fecha_entrega.isoformat() if fecha_entrega else None
            archivos = entrega.get("archivos", [])
            entrega["potencial_reentrega"] = len(archivos) > 1

    return detalles

@mcp.tool()
async def list_pending_students(task_id: int, moodle_alias: str = "default") -> Dict[str, Any]:
    """
    Lista SOLO los alumnos sin calificación en una tarea.
    Útil para identificar rápidamente quién falta calificar.
    """
    creds = get_credentials(moodle_alias)
    if not creds: return {"error": "Credenciales no encontradas"}
    page = await get_authenticated_page(moodle_alias)
    detalles = await scrape_task_details_async(page, creds["url"], task_id)

    sin_calificacion = []
    key_entregas = "entregas_pendientes" if "entregas_pendientes" in detalles else "entregas"
    if key_entregas in detalles:
        for entrega in detalles[key_entregas]:
            if not entrega.get("nota") or str(entrega.get("nota")).strip() == "":
                sin_calificacion.append({
                    "alumno_id": entrega.get("alumno_id"),
                    "nombre": entrega.get("nombre"),
                    "estado": entrega.get("estado"),
                    "fecha_entrega": entrega.get("fecha_entrega"),
                    "archivos": entrega.get("archivos", []),
                    "link_calificar": entrega.get("link_calificar")
                })

    return {
        "tarea_id": task_id,
        "total_sin_calificacion": len(sin_calificacion),
        "alumnos_pendientes": sin_calificacion
    }

@mcp.tool()
async def list_resubmitted_students(task_id: int, moodle_alias: str = "default") -> Dict[str, Any]:
    """
    Detecta alumnos que han REENTREGADO después de una calificación anterior.
    Retorna lista de alumnos con múltiples entregas.
    """
    creds = get_credentials(moodle_alias)
    if not creds: return {"error": "Credenciales no encontradas"}
    page = await get_authenticated_page(moodle_alias)
    detalles = await scrape_task_details_async(page, creds["url"], task_id)

    reentregados = []
    key_entregas = "entregas_pendientes" if "entregas_pendientes" in detalles else "entregas"
    if key_entregas in detalles:
        for entrega in detalles[key_entregas]:
            archivos = entrega.get("archivos", [])
            if len(archivos) > 1:
                reentregados.append({
                    "alumno_id": entrega.get("alumno_id"),
                    "nombre": entrega.get("nombre"),
                    "nota_actual": entrega.get("nota"),
                    "num_archivos": len(archivos),
                    "archivos": [{"nombre": a.get("nombre")} for a in archivos],
                    "link_calificar": entrega.get("link_calificar"),
                    "observacion": "Múltiples archivos detectados - verificar si es reentrega"
                })

    return {
        "tarea_id": task_id,
        "total_reentregados": len(reentregados),
        "alumnos_reentregados": reentregados
    }

@mcp.tool()
async def get_grading_summary(task_id: int, moodle_alias: str = "default") -> Dict[str, Any]:
    """
    Resumen de calificación de una tarea:
    - Total de alumnos
    - Calificados / Sin calificar
    - Con reentrega
    - Estadísticas de notas
    """
    creds = get_credentials(moodle_alias)
    if not creds: return {"error": "Credenciales no encontradas"}
    page = await get_authenticated_page(moodle_alias)
    detalles = await scrape_task_details_async(page, creds["url"], task_id)

    total = 0
    calificados = 0
    sin_calificar = 0
    reentregados = 0
    notas = []

    key_entregas = "entregas_pendientes" if "entregas_pendientes" in detalles else "entregas"
    if key_entregas in detalles:
        for entrega in detalles[key_entregas]:
            total += 1
            nota = entrega.get("nota")
            if nota and str(nota).strip() != "":
                calificados += 1
                try:
                    notas.append(float(nota.replace(",", ".")))
                except:
                    pass
            else:
                sin_calificar += 1
            if len(entrega.get("archivos", [])) > 1:
                reentregados += 1

    promedio = sum(notas) / len(notas) if notas else 0
    return {
        "tarea_id": task_id,
        "total_alumnos": total,
        "calificados": calificados,
        "sin_calificar": sin_calificar,
        "con_reentrega_potencial": reentregados,
        "estadisticas_notas": {
            "cantidad": len(notas),
            "promedio": round(promedio, 2),
            "minima": min(notas) if notas else None,
            "maxima": max(notas) if notas else None
        },
        "porcentaje_completado": round((calificados / total * 100) if total > 0 else 0, 1)
    }

@mcp.tool()
async def download_all_submissions(task_id: int, moodle_alias: str = "default") -> Dict[str, Any]:
    """
    Descarga todas las entregas de una tarea en un archivo ZIP.
    Retorna la ruta del ZIP y la carpeta de extracción.
    """
    creds = get_credentials(moodle_alias)
    if not creds: return {"error": "Credenciales no encontradas"}

    import tempfile
    tmp_dir = os.path.join(tempfile.gettempdir(), "moodle_downloads")

    page = await get_download_page(moodle_alias)
    try:
        sys.path.append(os.path.dirname(__file__))
        from fixes import download_all_submissions_zip_fixed
        resultado = await download_all_submissions_zip_fixed(page, creds, task_id, tmp_dir)
        return resultado
    except Exception as e:
        logger.error(f"Error en download_all_submissions: {e}", exc_info=True)
        return {"error": str(e)}

@mcp.tool()
async def analyze_submission_file(file_url: str, moodle_alias: str = "default") -> Dict[str, Any]:
    """
    Descarga y analiza un archivo entregado por un alumno.

    Formatos soportados:
    - Documentos: PDF, DOCX, ODT
    - Hojas de cálculo: ODS, XLSX
    - Web: HTML, CSS, JS
    - Código: PY, TXT, JSON, XML, MD
    - Scratch: SB3 (analiza bloques y sprites)
    - Archivos: ZIP, TAR.GZ (extrae y analiza contenidos)
    - Imágenes: PNG, JPG, GIF, SVG (descarga para análisis visual)

    Devuelve el contenido extraído para su corrección.
    """
    creds = get_credentials(moodle_alias)
    if not creds: return {"error": "Credenciales no encontradas"}

    import tempfile
    import uuid

    tmp_dir = os.path.join(tempfile.gettempdir(), "moodle_downloads")
    os.makedirs(tmp_dir, exist_ok=True)

    page = await get_download_page(moodle_alias)
    try:
            logger.info(f"Descargando archivo desde: {file_url}")

            async with page.expect_download() as download_info:
                try:
                    await page.goto(file_url, wait_until="networkidle", timeout=15000)
                except:
                    pass

            download = await download_info.value
            filename = download.suggested_filename
            ext = os.path.splitext(filename)[1].lower()
            if filename.lower().endswith(".tar.gz"):
                ext = ".tar.gz"

            # Guardar con nombre único pero extensión original
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(tmp_dir, unique_filename)

            await download.save_as(file_path)
            logger.info(f"Archivo guardado en: {file_path} ({ext})")

            # === DOCUMENTOS ===
            if ext == ".pdf":
                content = extract_text_from_pdf(file_path)
                return _submission_result(filename, "pdf", content, file_path)

            elif ext in [".docx", ".odt", ".doc"]:
                # Intentar conversión a HTML con LibreOffice (preserva formato)
                converted = await convert_office_to_html(file_path)
                if converted:
                    return {
                        "filename": filename,
                        "type": f"{ext.lstrip('.')}_converted",
                        "content": converted["text"],
                        "html_raw": converted["html_raw"][:30000],
                        "file_path": file_path,
                        "info": "Documento convertido a HTML con LibreOffice"
                    }
                # Fallback: extracción de texto plano
                if ext == ".docx":
                    content = extract_text_from_docx(file_path)
                elif ext == ".odt":
                    content = extract_text_from_odt(file_path)
                else:
                    content = "Formato .doc no soportado sin LibreOffice"
                return _submission_result(filename, ext.lstrip("."), content, file_path)

            # === HOJAS DE CÁLCULO ===
            elif ext in [".ods", ".xlsx"]:
                content = extract_text_from_ods(file_path)
                return _submission_result(filename, ext.lstrip("."), content, file_path)

            # === WEB Y CÓDIGO ===
            elif ext in [".html", ".htm"]:
                text_content = extract_text_from_html(file_path)
                # También guardar HTML raw para análisis de estructura
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    html_raw = f.read()
                return {
                    "filename": filename,
                    "type": "html",
                    "content": text_content,
                    "html_raw": html_raw[:30000],
                    "full_content": text_content,
                    "path": file_path,
                    "char_count": len(text_content),
                    "html_char_count": len(html_raw)
                }

            elif ext in [".css", ".js", ".py", ".txt", ".md", ".json", ".xml",
                         ".csv", ".sql", ".yaml", ".yml", ".ts", ".sh", ".java",
                         ".c", ".cpp", ".h", ".rb", ".php"]:
                content = extract_text_from_txt(file_path)
                return _submission_result(filename, ext.lstrip("."), content, file_path)

            # === SCRATCH ===
            elif ext == ".sb3":
                text, data = extract_scratch_project(file_path)
                return {
                    "filename": filename,
                    "type": "scratch",
                    "content": text,
                    "full_content": text,
                    "scratch_data": data,
                    "path": file_path,
                    "char_count": len(text)
                }

            # === ARCHIVOS COMPRIMIDOS ===
            elif ext in [".zip", ".tar.gz", ".tgz"]:
                extract_dir = os.path.join(tmp_dir, f"extract_{uuid.uuid4()}")
                os.makedirs(extract_dir, exist_ok=True)

                try:
                    if ext == ".zip":
                        import zipfile
                        with zipfile.ZipFile(file_path, 'r') as zf:
                            zf.extractall(extract_dir)
                            all_files = zf.namelist()
                    else:
                        import tarfile
                        with tarfile.open(file_path, 'r') as tf:
                            tf.extractall(extract_dir)
                            all_files = tf.getnames()

                    # Categorizar archivos extraídos
                    images = []
                    text_files = []
                    code_files = []
                    docs = []
                    contents = []

                    for root, dirs, files in os.walk(extract_dir):
                        for file in files:
                            fpath = os.path.join(root, file)
                            f_ext = os.path.splitext(file)[1].lower()
                            rel_path = os.path.relpath(fpath, extract_dir)

                            if f_ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']:
                                images.append(fpath)
                            elif f_ext in ['.html', '.htm']:
                                text_files.append(rel_path)
                                text = extract_text_from_html(fpath)
                                with open(fpath, 'r', encoding='utf-8', errors='ignore') as hf:
                                    html_raw = hf.read()
                                contents.append(f"--- {rel_path} ---\n{html_raw[:5000]}")
                            elif f_ext in ['.py', '.js', '.ts', '.css', '.json', '.md', '.txt']:
                                code_files.append(rel_path)
                                text = extract_text_from_txt(fpath)
                                contents.append(f"--- {rel_path} ---\n{text[:5000]}")
                            elif f_ext == '.pdf':
                                docs.append(rel_path)
                                text = extract_text_from_pdf(fpath)
                                contents.append(f"--- {rel_path} ---\n{text[:5000]}")
                            elif f_ext == '.docx':
                                docs.append(rel_path)
                                text = extract_text_from_docx(fpath)
                                contents.append(f"--- {rel_path} ---\n{text[:5000]}")

                    return {
                        "filename": filename,
                        "type": "archive",
                        "total_files": len(all_files),
                        "text_files": text_files,
                        "code_files": code_files,
                        "documents": docs,
                        "images": images[:20],
                        "content": "\n\n".join(contents)[:30000],
                        "full_content": "\n\n".join(contents),
                        "extract_path": extract_dir,
                        "path": file_path
                    }

                except Exception as e:
                    return {"error": f"Error descomprimiendo: {e}", "path": file_path}

            # === IMÁGENES ===
            elif ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]:
                return {
                    "filename": filename,
                    "type": "image",
                    "path": file_path,
                    "info": "Imagen descargada. Usa análisis visual para evaluar."
                }

            # === FORMATO NO RECONOCIDO ===
            else:
                # Intentar leer como texto
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    if content and len(content.strip()) > 0:
                        return _submission_result(filename, "text", content, file_path)
                except:
                    pass

                return {
                    "error": f"Formato no soportado: {ext}",
                    "path": file_path,
                    "filename": filename,
                    "info": "Archivo descargado pero no se pudo extraer contenido."
                }

    except Exception as e:
        return {"error": str(e)}


def _submission_result(filename: str, file_type: str, content: str, path: str) -> Dict[str, Any]:
    """Helper para formatear resultado de extracción de entrega"""
    return {
        "filename": filename,
        "type": file_type,
        "content": content[:5000],
        "full_content": content,
        "path": path,
        "char_count": len(content),
        "truncated_in_content": len(content) > 5000
    }

@mcp.tool()
async def submit_grade(task_id: int, student_id: int, grade: float, feedback: str, moodle_alias: str = "default") -> str:
    """
    Envía la calificación y feedback para un alumno en una tarea.
    """
    creds = get_credentials(moodle_alias)
    if not creds: return "Error: Credenciales no encontradas"

    page = await get_authenticated_page(moodle_alias)
    try:
        grade_url = f"{creds['url']}/mod/assign/view.php?id={task_id}&action=grade&userid={student_id}"
        logger.info(f"Navegando a calificación: {grade_url}")

        await page.goto(grade_url, wait_until="networkidle")

        if "action=grade" not in page.url and "action=grader" not in page.url:
            return f"Error: No se pudo acceder a la página de calificación directa. URL final: {page.url}"

        # 1. Poner Nota
        try:
            await page.wait_for_selector("#id_grade", state="visible", timeout=5000)
            await page.fill("#id_grade", str(grade))
        except:
            logger.warning("Input #id_grade no visible, intentando forzar value con JS")
            await page.evaluate(f"document.querySelector('#id_grade').value = '{grade}'")

        # 2. Poner Feedback
        feedback_set = False

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

        if not feedback_set:
            try:
                atto = await page.query_selector("div.editor_atto_content_wrap div[contenteditable='true']")
                if atto:
                    await atto.fill(feedback)
                    logger.info("Feedback establecido vía Atto")
                    feedback_set = True
            except: pass

        if not feedback_set:
            try:
                await page.fill("#id_assignfeedbackcomments_editor", feedback)
                logger.info("Feedback establecido vía Textarea directo")
            except:
                await page.evaluate(f"""
                    var el = document.getElementById('id_assignfeedbackcomments_editor');
                    if(el) {{ el.value = `{feedback}`; }}
                """)

        await page.wait_for_timeout(1000)

        # 3. Guardar cambios
        save_btn = await page.query_selector("input[name='savegrade']")
        if not save_btn:
             save_btn = await page.get_by_role("button", name="Guardar cambios")

        if save_btn:
            await save_btn.click()
            await page.wait_for_load_state("networkidle")
            return f"Calificación enviada correctamente para alumno {student_id}: Nota {grade}"
        else:
            return "Error: No se encontró el botón de guardar (savegrade)."

    except Exception as e:
        return f"Error enviando calificación: {str(e)}"

@mcp.tool()
async def debug_grading_page(task_id: int, student_id: int, moodle_alias: str = "default") -> str:
    """
    Descarga el HTML de la página de calificación para inspeccionar selectores.
    """
    creds = get_credentials(moodle_alias)
    if not creds: return "Error: Credenciales no encontradas"

    page = await get_authenticated_page(moodle_alias)
    try:
        grade_url = f"{creds['url']}/mod/assign/view.php?id={task_id}&action=grade&userid={student_id}"
        await page.goto(grade_url, wait_until="networkidle")

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

        relevant = [i for i in inputs if 'grade' in (i['name'] or '') or 'grade' in (i['id'] or '') or 'save' in (i['name'] or '') or 'feedback' in (i['name'] or '')]

        return json.dumps(relevant, indent=2)

    except Exception as e:
        return f"Error debug: {str(e)}"


# =============================================================================
# NUEVAS HERRAMIENTAS (Skills de alto nivel)
# =============================================================================

@mcp.tool()
async def find_student(
    name: str,
    task_id: int = None,
    course_url: str = None,
    moodle_alias: str = "default"
) -> Dict[str, Any]:
    """
    Busca un alumno por nombre usando fuzzy matching.

    Args:
        name: Nombre parcial o completo del alumno
        task_id: ID de tarea para buscar en sus entregas
        course_url: URL del curso para buscar en sus alumnos
        moodle_alias: Alias de credenciales

    Returns:
        Mejor coincidencia con score y alternativas si hay ambigüedad
    """
    if not FUZZY_AVAILABLE:
        return {"error": "rapidfuzz no instalado. Ejecuta: pip install rapidfuzz"}

    if not task_id and not course_url:
        return {"error": "Debes especificar task_id o course_url"}

    alumnos = []
    alumnos_data = {}  # nombre -> datos completos

    if task_id:
        creds = get_credentials(moodle_alias)
        if not creds:
            return {"error": "Credenciales no encontradas"}

        page = await get_authenticated_page(moodle_alias)
        detalles = await scrape_task_details_async(page, creds["url"], task_id)

        key_entregas = "entregas_pendientes" if "entregas_pendientes" in detalles else "entregas"
        for entrega in detalles.get(key_entregas, []):
            nombre = entrega.get("nombre", "")
            if nombre:
                alumnos.append(nombre)
                alumnos_data[nombre] = {
                    "alumno_id": entrega.get("alumno_id"),
                    "nombre": nombre,
                    "estado": entrega.get("estado"),
                    "tiene_entrega": bool(entrega.get("archivos"))
                }

    if not alumnos:
        return {"error": "No se encontraron alumnos en el contexto especificado"}

    # Normalizar a minúsculas para comparación
    name_norm = name.strip().lower()
    alumnos_norm = [a.lower() for a in alumnos]
    # Mapeo normalizado → original
    norm_to_orig = {a.lower(): a for a in alumnos}

    # Fuzzy matching - usar múltiples estrategias
    # 1. partial_ratio: bueno para nombres parciales ("ruben" en "ruben cancho gasulla")
    # 2. token_sort_ratio: bueno para orden diferente ("garcía maría" vs "maría garcía")
    matches_partial = fuzz_process.extract(
        name_norm, alumnos_norm, scorer=fuzz.partial_ratio, limit=5
    )
    matches_token = fuzz_process.extract(
        name_norm, alumnos_norm, scorer=fuzz.token_sort_ratio, limit=5
    )

    # Combinar: para cada alumno, tomar el mejor score (usar nombre original)
    score_map = {}
    for m in matches_partial + matches_token:
        nombre_norm = m[0]
        nombre_orig = norm_to_orig.get(nombre_norm, nombre_norm)
        score_m = m[1]
        if nombre_orig not in score_map or score_m > score_map[nombre_orig]:
            score_map[nombre_orig] = score_m

    # Ordenar por score descendente
    matches = sorted(score_map.items(), key=lambda x: x[1], reverse=True)[:5]

    if not matches:
        return {"error": f"No se encontró ningún alumno similar a '{name}'"}

    best_nombre, best_score_raw = matches[0]
    best_score = best_score_raw / 100.0

    # Umbral de 0.6 (más permisivo para nombres parciales)
    if best_score >= 0.6:
        result = {
            "encontrado": True,
            "match_score": round(best_score, 2),
            **alumnos_data.get(best_nombre, {"nombre": best_nombre})
        }

        # Añadir alternativas si hay otras buenas
        alternativas = []
        for m in matches[1:]:
            if m[1] >= 60:
                alt_nombre = m[0]
                alternativas.append({
                    "match_score": round(m[1] / 100.0, 2),
                    **alumnos_data.get(alt_nombre, {"nombre": alt_nombre})
                })

        if alternativas:
            result["alternativas"] = alternativas

        return result
    else:
        return {
            "encontrado": False,
            "mensaje": f"No se encontró coincidencia clara para '{name}'",
            "sugerencias": [
                {
                    "match_score": round(m[1] / 100.0, 2),
                    **alumnos_data.get(m[0], {"nombre": m[0]})
                }
                for m in matches if m[1] >= 40
            ]
        }


@mcp.tool()
async def get_submission(
    student_id: int,
    task_id: int,
    moodle_alias: str = "default"
) -> Dict[str, Any]:
    """
    Obtiene la entrega de UN alumno específico en una tarea.

    Args:
        student_id: ID del alumno en Moodle
        task_id: ID de la tarea
        moodle_alias: Alias de credenciales

    Returns:
        Datos de la entrega: archivos, estado, nota actual, feedback
    """
    creds = get_credentials(moodle_alias)
    if not creds:
        return {"error": "Credenciales no encontradas"}

    page = await get_authenticated_page(moodle_alias)
    detalles = await scrape_task_details_async(page, creds["url"], task_id)

    key_entregas = "entregas_pendientes" if "entregas_pendientes" in detalles else "entregas"
    student_id_str = str(student_id)
    for entrega in detalles.get(key_entregas, []):
        entrega_id = str(entrega.get("alumno_id", ""))
        if entrega_id == student_id_str:
            return {
                "encontrado": True,
                "alumno_id": student_id,
                "nombre": entrega.get("nombre"),
                "estado": entrega.get("estado"),
                "fecha_entrega": entrega.get("fecha_entrega"),
                "archivos": entrega.get("archivos", []),
                "nota_actual": entrega.get("nota"),
                "feedback_actual": entrega.get("feedback"),
                "link_calificar": entrega.get("link_calificar")
            }

    ids_disponibles = [str(e.get("alumno_id", "?")) for e in detalles.get(key_entregas, [])[:5]]
    return {
        "encontrado": False,
        "error": f"No se encontró entrega para alumno {student_id} en tarea {task_id}",
        "ids_disponibles_muestra": ids_disponibles
    }


@mcp.tool()
async def submit_grades_batch(
    task_id: int,
    grades: List[Dict[str, Any]],
    moodle_alias: str = "default",
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Envía múltiples calificaciones a Moodle con gestión de errores.

    Args:
        task_id: ID de la tarea
        grades: Lista de {"student_id": int, "grade": float, "feedback": str}
        moodle_alias: Alias de credenciales
        max_retries: Reintentos por calificación fallida

    Returns:
        Resumen de éxitos, fallos y errores detallados
    """
    # Si llega como JSON string (vía protocolo MCP), parsear
    if isinstance(grades, str):
        try:
            grades = json.loads(grades)
        except json.JSONDecodeError:
            return {"error": "El parámetro grades no es JSON válido"}

    if not grades:
        return {"error": "Lista de calificaciones vacía"}

    resultados = []
    exitosos = 0
    fallidos = 0
    errores = []

    for entry in grades:
        student_id = entry.get("student_id")
        grade = entry.get("grade")
        feedback = entry.get("feedback", "")

        if student_id is None or grade is None:
            fallidos += 1
            errores.append({
                "student_id": student_id,
                "error": "Faltan campos requeridos (student_id, grade)"
            })
            continue

        # Intentar con reintentos
        success = False
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                result = await submit_grade.fn(
                    task_id=task_id,
                    student_id=student_id,
                    grade=float(grade),
                    feedback=feedback,
                    moodle_alias=moodle_alias
                )

                if "Error" not in result:
                    exitosos += 1
                    resultados.append({
                        "student_id": student_id,
                        "grade": grade,
                        "success": True
                    })
                    success = True
                    break
                else:
                    last_error = result
            except Exception as e:
                last_error = str(e)

            # Esperar antes de reintentar
            if attempt < max_retries:
                await asyncio.sleep(1)

        if not success:
            fallidos += 1
            errores.append({
                "student_id": student_id,
                "grade": grade,
                "error": last_error,
                "intentos": max_retries + 1
            })

    return {
        "task_id": task_id,
        "total": len(grades),
        "exitosos": exitosos,
        "fallidos": fallidos,
        "porcentaje_exito": round((exitosos / len(grades) * 100) if grades else 0, 1),
        "errores": errores if errores else None,
        "resultados": resultados
    }


@mcp.tool()
async def extract_content(
    file_path: str,
    max_chars: int = 50000
) -> Dict[str, Any]:
    """
    Extrae contenido de un archivo local.

    Formatos soportados:
    - Texto: .txt, .md, .py, .js, .html, .css, .json
    - Documentos: .docx, .odt, .pdf
    - Archivos: .zip, .tar.gz (lista contenidos)

    Args:
        file_path: Ruta al archivo local
        max_chars: Máximo de caracteres a retornar

    Returns:
        Contenido extraído con metadata
    """
    import os

    if not os.path.exists(file_path):
        return {"error": f"Archivo no encontrado: {file_path}"}

    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()

    # Detectar .tar.gz
    if filename.lower().endswith(".tar.gz"):
        ext = ".tar.gz"

    file_size = os.path.getsize(file_path)

    content = ""
    file_type = ext.lstrip(".")
    metadata = {
        "filename": filename,
        "size_bytes": file_size,
        "extension": ext
    }

    try:
        # Documentos Office
        if ext in [".docx", ".odt", ".doc"]:
            converted = await convert_office_to_html(file_path)
            if converted:
                content = converted["text"]
                file_type = f"{ext.lstrip('.')}_converted"
                metadata["html_raw"] = converted["html_raw"][:10000]
            elif ext == ".docx":
                content = extract_text_from_docx(file_path)
                file_type = "docx"
            elif ext == ".odt":
                content = extract_text_from_odt(file_path)
                file_type = "odt"
            else:
                content = "Formato .doc no soportado sin LibreOffice"
                file_type = "doc"

        # PDF
        elif ext == ".pdf":
            content = extract_text_from_pdf(file_path)
            file_type = "pdf"

        # HTML
        elif ext in [".html", ".htm"]:
            content = extract_text_from_html(file_path)
            file_type = "html"
            # También guardar HTML raw para análisis de estructura
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                metadata["html_raw"] = f.read()[:10000]  # Primeros 10k chars

        # Hojas de cálculo
        elif ext in [".ods", ".xlsx"]:
            content = extract_text_from_ods(file_path)
            file_type = ext.lstrip(".")

        # Texto plano y código
        elif ext in [".txt", ".md", ".py", ".js", ".ts", ".css", ".json", ".xml",
                     ".csv", ".sql", ".sh", ".yaml", ".yml", ".java", ".c", ".cpp",
                     ".h", ".rb", ".php"]:
            content = extract_text_from_txt(file_path)
            file_type = ext.lstrip(".")

        # Scratch
        elif ext == ".sb3":
            text, data = extract_scratch_project(file_path)
            return {
                "type": "scratch",
                "filename": filename,
                "content": text,
                "scratch_data": data,
                "metadata": metadata
            }

        # Archivos comprimidos
        elif ext in [".zip", ".tar.gz", ".tgz"]:
            import tempfile
            import uuid

            extract_dir = os.path.join(tempfile.gettempdir(), f"extract_{uuid.uuid4()}")
            os.makedirs(extract_dir, exist_ok=True)

            files_list = []

            if ext in [".zip", ".sb3"]:
                import zipfile
                with zipfile.ZipFile(file_path, 'r') as zf:
                    files_list = zf.namelist()
                    zf.extractall(extract_dir)
            else:
                import tarfile
                with tarfile.open(file_path, 'r') as tf:
                    files_list = tf.getnames()
                    tf.extractall(extract_dir)

            # Buscar archivos interesantes
            text_files = []
            image_files = []
            code_files = []

            for f in files_list:
                f_lower = f.lower()
                if f_lower.endswith(('.txt', '.md', '.html', '.htm')):
                    text_files.append(f)
                elif f_lower.endswith(('.py', '.js', '.ts', '.css', '.json')):
                    code_files.append(f)
                elif f_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
                    image_files.append(f)

            return {
                "type": "archive",
                "filename": filename,
                "total_files": len(files_list),
                "files_list": files_list[:50],  # Primeros 50
                "text_files": text_files,
                "code_files": code_files,
                "image_files": image_files,
                "extract_path": extract_dir,
                "metadata": metadata
            }

        # Imágenes
        elif ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]:
            return {
                "type": "image",
                "filename": filename,
                "path": file_path,
                "metadata": metadata,
                "info": "Imagen lista para análisis visual"
            }

        else:
            return {
                "error": f"Formato no soportado: {ext}",
                "path": file_path,
                "metadata": metadata
            }

        # Truncar si es muy largo
        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars] + "\n\n[... contenido truncado ...]"

        return {
            "type": file_type,
            "filename": filename,
            "content": content,
            "char_count": len(content),
            "truncated": truncated,
            "metadata": metadata
        }

    except Exception as e:
        return {
            "error": f"Error procesando archivo: {str(e)}",
            "path": file_path,
            "metadata": metadata
        }


@mcp.tool()
async def get_task_rubric(
    task_id: int,
    moodle_alias: str = "default"
) -> Dict[str, Any]:
    """
    Extrae la rúbrica configurada en Moodle para una tarea.

    Args:
        task_id: ID de la tarea
        moodle_alias: Alias de credenciales

    Returns:
        Rúbrica con criterios, niveles y pesos
    """
    creds = get_credentials(moodle_alias)
    if not creds:
        return {"error": "Credenciales no encontradas"}

    page = await get_authenticated_page(moodle_alias)
    try:
        task_url = f"{creds['url']}/mod/assign/view.php?id={task_id}"
        await page.goto(task_url, wait_until="networkidle")

        rubric_data = {
            "task_id": task_id,
            "tipo": None,
            "criterios": [],
            "nota_maxima": 10
        }

        # Buscar nota máxima
        try:
            grade_info = await page.query_selector(".gradingtable, .gradingsummary")
            if grade_info:
                text = await grade_info.inner_text()
                match = re.search(r'(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)', text)
                if match:
                    rubric_data["nota_maxima"] = float(match.group(2).replace(",", "."))
        except:
            pass

        # Buscar rúbrica en configuración avanzada
        rubric_url = f"{creds['url']}/grade/grading/manage.php?areaid={task_id}&component=mod_assign"
        await page.goto(rubric_url, wait_until="networkidle", timeout=10000)

        page_content = await page.content()

        if "rubric" in page_content.lower():
            rubric_data["tipo"] = "rubrica"
            criterios = await page.query_selector_all(".rubric-criteria tr, .criterion")
            for criterio in criterios:
                try:
                    nombre = await criterio.query_selector(".criterion-name, .description")
                    if nombre:
                        nombre_text = await nombre.inner_text()
                        niveles = []
                        level_els = await criterio.query_selector_all(".level, td.level")
                        for level in level_els:
                            try:
                                level_text = await level.inner_text()
                                pts_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:puntos?|pts?|points?)', level_text, re.I)
                                puntos = float(pts_match.group(1).replace(",", ".")) if pts_match else 0
                                niveles.append({
                                    "descripcion": level_text.strip()[:200],
                                    "puntos": puntos
                                })
                            except:
                                pass
                        if nombre_text.strip():
                            rubric_data["criterios"].append({
                                "nombre": nombre_text.strip(),
                                "niveles": niveles
                            })
                except:
                    pass

        elif "guide" in page_content.lower():
            rubric_data["tipo"] = "guia_calificacion"
            guides = await page.query_selector_all(".guide-criteria tr, .criterion")
            for guide in guides:
                try:
                    nombre = await guide.query_selector(".criterion-name, .description")
                    if nombre:
                        nombre_text = await nombre.inner_text()
                        max_pts = await guide.query_selector(".maxscore, .maxmark")
                        puntos = 0
                        if max_pts:
                            pts_text = await max_pts.inner_text()
                            pts_match = re.search(r'(\d+(?:[.,]\d+)?)', pts_text)
                            if pts_match:
                                puntos = float(pts_match.group(1).replace(",", "."))
                        rubric_data["criterios"].append({
                            "nombre": nombre_text.strip(),
                            "puntos_maximos": puntos
                        })
                except:
                    pass
        else:
            rubric_data["tipo"] = "simple"
            rubric_data["observacion"] = "Esta tarea usa calificación simple (sin rúbrica)"

        if not rubric_data["criterios"]:
            await page.goto(task_url, wait_until="networkidle")
            descripcion_el = await page.query_selector(".activity-description, .intro")
            if descripcion_el:
                descripcion = await descripcion_el.inner_text()
                rubric_data["descripcion_tarea"] = descripcion[:2000]

        return rubric_data

    except Exception as e:
        logger.error(f"Error extrayendo rúbrica: {e}", exc_info=True)
        return {"error": str(e), "task_id": task_id}


@mcp.tool()
async def search_tasks(
    query: str,
    course_url: str = None,
    moodle_alias: str = "default"
) -> Dict[str, Any]:
    """
    Busca tareas por nombre en uno o todos los cursos.

    Args:
        query: Texto a buscar en nombres de tareas
        course_url: URL del curso (si None, busca en todos los cursos cacheados)
        moodle_alias: Alias de credenciales

    Returns:
        Lista de tareas que coinciden con la búsqueda
    """
    query_lower = query.lower()
    resultados = []

    if course_url:
        # Buscar solo en este curso
        tareas = db.get_tasks(moodle_alias, course_url)
        for t in tareas:
            if query_lower in t.get("titulo", "").lower():
                resultados.append({
                    **t,
                    "course_url": course_url
                })
    else:
        # Buscar en todos los cursos
        cursos = db.get_courses(moodle_alias)
        for curso in cursos:
            tareas = db.get_tasks(moodle_alias, curso["url"])
            for t in tareas:
                if query_lower in t.get("titulo", "").lower():
                    resultados.append({
                        **t,
                        "curso": curso["nombre"],
                        "course_url": curso["url"]
                    })

    return {
        "query": query,
        "total_encontradas": len(resultados),
        "tareas": resultados
    }


if __name__ == "__main__":
    mcp.run()
