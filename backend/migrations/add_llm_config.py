from sqlalchemy import create_engine, text
import os

# Create engine with absolute path
db_path = '/home/ruben/Desarrollo/moodle_ai/moodle_llm.db'
if not os.path.exists(db_path):
    db_path = '/home/ruben/Desarrollo/moodle_ai/backend/moodle_llm.db'

engine = create_engine(f'sqlite:///{db_path}')

print(f"Running LLM config migration on database: {db_path}")

# Run migration
try:
    with engine.connect() as conn:
        # Create tables
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS llm_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                url_template TEXT NOT NULL,
                descripcion TEXT
            );
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS usuario_llm_config (
                usuario_id INTEGER NOT NULL,
                llm_config_id INTEGER NOT NULL,
                is_default BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (usuario_id, llm_config_id),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                FOREIGN KEY (llm_config_id) REFERENCES llm_configs(id)
            );
        """))
        
        # Insert default configurations
        conn.execute(text("""
            INSERT INTO llm_configs (nombre, url_template, descripcion) 
            VALUES 
                ('Google AI Studio', 'https://aistudio.google.com/prompts/new_chat', 'Google AI Studio chat'),
                ('OpenAI ChatGPT', 'https://chat.openai.com', 'OpenAI ChatGPT'),
                ('Claude', 'https://claude.ai', 'Anthropic Claude'),
                ('Gemini', 'https://gemini.google.com', 'Google Gemini'),
                ('Copilot', 'https://copilot.microsoft.com', 'Microsoft Copilot')
            ON CONFLICT (nombre) DO NOTHING;
        """))
        
        conn.commit()
        print("LLM config migration successful!")
except Exception as e:
    print(f"Error during LLM config migration: {e}")
