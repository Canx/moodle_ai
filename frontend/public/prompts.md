# Plantillas de Prompts

Este archivo contiene plantillas de prompts que puedes usar según el contexto.

## Prompt 1: Sincronizar tarea individual

**Descripción**: Encola la sincronización de una tarea específica en segundo plano y retorna su estado final junto con sus detalles.

```text
Sincroniza la tarea con ID {tarea_id} del curso {curso_id}. Para ello:
1. Llama al endpoint POST /api/tareas/{tarea_id}/sincronizar para encolar la tarea.
2. Espera a que se complete (puedes hacer polling con GET /api/tareas/{tarea_id}).
3. Devuelve un JSON con los campos:
   - descripcion
   - estado
   - entregadas
   - pendientes
   - tipo_calificacion
   - detalles_calificacion
```

## Prompt 2: Evaluación de entrega

**Descripción**: Evalúa una entrega usando la rúbrica de la tarea.

```text
Por favor evalúa la entrega para la tarea "{tarea_titulo}".
Descripción de la tarea:
{descripcion}

Archivo: {file_name}

Utiliza la rúbrica de la descripción de la tarea (si existe) pero no generes tablas ni emoticonos en la respuesta.

Proporciona:
- Comentarios detallados
- Sugerencias de mejora
- Calificación entre 0 y 10
```
