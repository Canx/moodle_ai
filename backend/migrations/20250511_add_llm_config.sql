-- Create table for LLM configurations
CREATE TABLE IF NOT EXISTS llm_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    url_template TEXT NOT NULL,
    descripcion TEXT
);

-- Create table to store user preferences for LLMs
CREATE TABLE IF NOT EXISTS usuario_llm_config (
    usuario_id INTEGER NOT NULL,
    llm_config_id INTEGER NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (usuario_id, llm_config_id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (llm_config_id) REFERENCES llm_configs(id)
);

-- Insert some default LLM configurations
INSERT INTO llm_configs (nombre, url_template, descripcion) VALUES
    ('Google AI Studio', 'https://aistudio.google.com/prompts/new_chat', 'Google AI Studio chat'),
    ('OpenAI ChatGPT', 'https://chat.openai.com', 'OpenAI ChatGPT'),
    ('Claude', 'https://claude.ai', 'Anthropic Claude'),
    ('Gemini', 'https://gemini.google.com', 'Google Gemini'),
    ('Copilot', 'https://copilot.microsoft.com', 'Microsoft Copilot');
