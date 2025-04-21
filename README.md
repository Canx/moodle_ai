# Moodle AI Tasks

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

## 🐳 Iniciar con Docker

Asegúrate de tener Docker y Docker Compose instalados.

```bash
docker-compose up --build
```

Esto levantará los servicios (db, backend y frontend). Una vez iniciados, el frontend estará disponible en http://localhost:5173 y el backend en http://localhost:8000.

Para levantar en segundo plano:

```bash
docker-compose up -d --build
```

Para detener y eliminar los contenedores:

```bash
docker-compose down
