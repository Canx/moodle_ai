import sqlite3

conn = sqlite3.connect("moodle_llm.db", check_same_thread=False)
cursor = conn.cursor()