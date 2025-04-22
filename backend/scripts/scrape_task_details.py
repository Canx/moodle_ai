#!/usr/bin/env python3
import sys
import json
from services.scraper_service import scrape_task_details

def main():
    if len(sys.argv) != 5:
        print("Usage: scrape_task_details.py moodle_url usuario contrasena tarea_id", file=sys.stderr)
        sys.exit(1)
    moodle_url = sys.argv[1]
    usuario = sys.argv[2]
    contrasena = sys.argv[3]
    tarea_id = int(sys.argv[4])
    result = scrape_task_details(moodle_url, usuario, contrasena, tarea_id)
    print(json.dumps(result))

if __name__ == "__main__":
    main()
