#!/bin/bash

# Script de ejemplo: Flujo de trabajo mejorado de calificación

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Flujo de Calificación Mejorado ===${NC}\n"

# Parámetros
TASK_ID=5721702
MOODLE_ALIAS="default"

# 1. VER RESUMEN DE LA TAREA
echo -e "${YELLOW}[1] Obteniendo resumen de la tarea...${NC}"
mcporter call moodle.get_grading_summary task_id=$TASK_ID --output json > summary.json
cat summary.json | jq .

PENDIENTES=$(jq '.sin_calificar' summary.json)
REENTREGADOS=$(jq '.con_reentrega_potencial' summary.json)
PORCENTAJE=$(jq '.porcentaje_completado' summary.json)

echo -e "\n${GREEN}Resumen:${NC}"
echo "  - Pendientes: $PENDIENTES"
echo "  - Con reentrega potencial: $REENTREGADOS"
echo "  - Completado: ${PORCENTAJE}%\n"

# 2. LISTAR ALUMNOS PENDIENTES
echo -e "${YELLOW}[2] Alumnos sin calificar:${NC}"
mcporter call moodle.list_pending_students task_id=$TASK_ID --output json > pending.json
jq '.alumnos_pendientes[] | {alumno_id, nombre, fecha_entrega}' pending.json

# 3. LISTAR REENTREGADOS
echo -e "\n${YELLOW}[3] Alumnos con reentrega potencial:${NC}"
mcporter call moodle.list_resubmitted_students task_id=$TASK_ID --output json > resubmitted.json
jq '.alumnos_reentregados[] | {alumno_id, nombre, nota_actual, num_archivos}' resubmitted.json

# 4. PROCESAR CADA PENDIENTE (ejemplo)
echo -e "\n${YELLOW}[4] Procesando pendientes...${NC}"
jq -r '.alumnos_pendientes[] | "\(.alumno_id)|\(.nombre)"' pending.json | while IFS='|' read student_id name; do
    echo -e "\n${BLUE}Alumno: $name (ID: $student_id)${NC}"
    
    # Obtener detalles completos
    STUDENT_DATA=$(jq ".alumnos_pendientes[] | select(.alumno_id == \"$student_id\")" pending.json)
    
    # Mostrar archivos
    ARCHIVOS=$(echo "$STUDENT_DATA" | jq -r '.archivos[].nombre')
    echo "  Archivos entregados:"
    echo "$ARCHIVOS" | sed 's/^/    - /'
    
    # Descargar primer archivo si existe
    FIRST_FILE=$(echo "$STUDENT_DATA" | jq -r '.archivos[0].url // empty')
    if [ -n "$FIRST_FILE" ]; then
        echo -e "  ${YELLOW}Analizando primer archivo...${NC}"
        mcporter call moodle.analyze_submission_file file_url="$FIRST_FILE" --output json > file_analysis.json
        
        FILE_TYPE=$(jq -r '.type' file_analysis.json)
        echo "    Tipo: $FILE_TYPE"
        
        # Si es imagen o imágenes extraídas, mostrar ruta
        if [[ "$FILE_TYPE" == *"image"* ]]; then
            FILE_PATH=$(jq -r '.path // .all_images[0]' file_analysis.json)
            echo "    Guardado en: $FILE_PATH"
        fi
    fi
    
    # Aquí iría la lógica de calificación automática o manual
    # NOTA=$(ask_user_for_grade)
    # mcporter call moodle.submit_grade task_id=$TASK_ID student_id=$student_id grade=$NOTA feedback="Revisado"
done

# 5. RESUMEN FINAL
echo -e "\n${GREEN}=== Proceso completado ===${NC}"
echo -e "Archivos generados:"
echo "  - summary.json (resumen de la tarea)"
echo "  - pending.json (alumnos sin calificación)"
echo "  - resubmitted.json (reentregas)"
echo -e "\n${YELLOW}Próximos pasos:${NC}"
echo "  1. Revisar los archivos de cada alumno"
echo "  2. Enviar calificaciones con: mcporter call moodle.submit_grade ..."
echo "  3. Verificar el progreso con: get_grading_summary"
