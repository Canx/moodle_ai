import sqlite3
import json
import os
import time
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "moodle_cache.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Tabla de metadatos (fechas de sync)
    c.execute('''CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    # Tabla de cursos
    c.execute('''CREATE TABLE IF NOT EXISTS cursos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        moodle_id INTEGER,
        nombre TEXT,
        url TEXT UNIQUE,
        alias TEXT
    )''')
    
    # Tabla de tareas
    c.execute('''CREATE TABLE IF NOT EXISTS tareas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        moodle_id INTEGER,
        curso_url TEXT,
        titulo TEXT,
        url TEXT,
        details_json TEXT,
        alias TEXT,
        UNIQUE(url)
    )''')
    
    conn.commit()
    conn.close()

def get_last_sync(alias: str) -> Optional[str]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM meta WHERE key = ?", (f"last_sync_{alias}",))
    row = cur.fetchone()
    conn.close()
    return row['value'] if row else None

def set_last_sync(alias: str):
    conn = get_db()
    cur = conn.cursor()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (f"last_sync_{alias}", now))
    conn.commit()
    conn.close()

def save_courses(alias: str, cursos: List[Dict]):
    conn = get_db()
    cur = conn.cursor()
    # Limpiamos cursos viejos de este alias para evitar duplicados/basura
    cur.execute("DELETE FROM cursos WHERE alias = ?", (alias,))
    
    for c in cursos:
        # Extraer moodle_id de la URL si es posible
        import re
        m_id = None
        match = re.search(r"id=(\d+)", c.get("url", ""))
        if match: m_id = int(match.group(1))
        
        cur.execute('''INSERT INTO cursos (moodle_id, nombre, url, alias) 
                       VALUES (?, ?, ?, ?)''', 
                       (m_id, c["nombre"], c["url"], alias))
    conn.commit()
    conn.close()

def save_tasks(alias: str, course_url: str, tareas: List[Dict]):
    conn = get_db()
    cur = conn.cursor()
    # Limpiamos tareas viejas de este curso
    cur.execute("DELETE FROM tareas WHERE curso_url = ? AND alias = ?", (course_url, alias))
    
    for t in tareas:
        details = json.dumps(t.get("detalles", {}))
        cur.execute('''INSERT INTO tareas (moodle_id, curso_url, titulo, url, details_json, alias)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                       (t.get("id"), course_url, t["titulo"], t["url"], details, alias))
    conn.commit()
    conn.close()

def get_courses(alias: str) -> List[Dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM cursos WHERE alias = ?", (alias,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_tasks(alias: str, course_url: str) -> List[Dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tareas WHERE alias = ? AND curso_url = ?", (alias, course_url))
    rows = cur.fetchall()
    conn.close()
    return [{
        "id": r["moodle_id"],
        "titulo": r["titulo"],
        "url": r["url"],
        "detalles": json.loads(r["details_json"]) if r["details_json"] else {}
    } for r in rows]
