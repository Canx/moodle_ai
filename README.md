# Moodle LLM Corrector (MVP)

Este proyecto es un MVP de un servicio web que permite a profesores conectar su cuenta de Moodle, obtener sus cursos y comenzar el proceso de corrección automática de tareas con ayuda de un modelo LLM como ChatGPT.

---

## 🚀 Cómo iniciar el proyecto

### 1. Clona el repositorio

```bash
git clone https://github.com/Canx/moodle-ai.git
cd moodle-ai
```

### 2. Crea un entorno virtual para el backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

### 3. Instala las dependencias

```bash
pip install -r requirements.txt
```

### 4. Ejecuta el backend

```bash
uvicorn main:app --reload
```

### 5. Ejecuta el frontend

1. Ve al directorio del frontend:
```bash
cd frontend
```

2. Instala las dependencias
```bash
npm install
```

3. Inicia el servidor de desarrollo
```bash
npm run dev
```
