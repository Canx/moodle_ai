from sqlalchemy import create_engine, text, inspect
from pathlib import Path

# Configuración de la base de datos
db_path = Path(__file__).parent.parent / 'moodle_llm.db'
engine = create_engine(f'sqlite:///{db_path}')

def check_schema():
    inspector = inspect(engine)
    columns = inspector.get_columns('sincronizaciones')
    print("\nEstructura actual de la tabla sincronizaciones:")
    for column in columns:
        print(f"- {column['name']}: {column['type']}")

if __name__ == '__main__':
    check_schema()
