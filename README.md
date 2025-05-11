# 🎓 Moodle AI Tasks

Sistema de asistencia para la evaluación de tareas de Moodle mediante Inteligencia Artificial. Permite a los profesores conectar su cuenta de Moodle, obtener sus cursos y tareas, y utilizar modelos de lenguaje (LLM) como ChatGPT, Claude o Google Gemini para ayudar en el proceso de evaluación.

## ✨ Características

- 🔄 Sincronización automática de cursos y tareas desde Moodle
- 📝 Descarga y gestión de entregas de los alumnos
- 🤖 Integración con múltiples LLMs (ChatGPT, Claude, Gemini, etc.)
- 🎯 Sistema de prompts optimizados para evaluación
- 📊 Seguimiento del estado de evaluaciones
- 🔐 Sistema de usuarios y autenticación
- 🎨 Interfaz moderna y responsive

## 🚀 Instalación y Ejecución

### Prerrequisitos

- Docker
- Docker Compose

### 1. Clonar el repositorio

```bash
git clone https://github.com/Canx/moodle-ai.git
cd moodle-ai
```

### 2. Configurar el entorno

El proyecto usa Docker Compose para gestionar todos los servicios necesarios:

- PostgreSQL para la base de datos
- Redis para la cola de tareas
- Backend FastAPI (Python)
- Worker Celery para tareas asíncronas
- Frontend Vite/React

### 3. Iniciar los servicios

```bash
# Construir e iniciar todos los servicios
docker compose up --build

# O en segundo plano
docker compose up -d --build
```

La aplicación estará disponible en:
- Frontend: http://localhost:5173
- API Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 4. Gestión de los servicios

```bash
# Ver logs de todos los servicios
docker compose logs -f

# Ver logs de un servicio específico
docker compose logs -f backend

# Detener los servicios
docker compose down

# Reiniciar un servicio específico
docker compose restart backend
```

## 🛠️ Desarrollo

Para desarrollo local, puedes usar el modo de recarga automática:

```bash
# Backend con recarga automática
docker compose up backend

# Frontend con HMR
docker compose up frontend
```

## 📝 Estructura del proyecto

```
moodle_ai/
├── backend/           # API y lógica de negocio
│   ├── endpoints/     # Endpoints de la API
│   ├── services/      # Servicios (scraper, etc.)
│   └── migrations/    # Migraciones de BD
├── frontend/         # Interfaz de usuario (React)
│   └── src/          # Componentes y lógica
└── docker-compose.yml
```

## 📚 Stack Tecnológico

- **Backend**: FastAPI, SQLAlchemy, Celery
- **Frontend**: React, Vite
- **Base de datos**: PostgreSQL
- **Cola de tareas**: Redis
- **Contenedores**: Docker
