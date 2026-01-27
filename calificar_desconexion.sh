#!/bin/bash

TASK_ID=5687261
echo "=== Calificando 'Desconexión Digital' (Tarea $TASK_ID) ==="

# 1. Obtener detalles
mcporter call moodle.get_task_details task_id=$TASK_ID --output json > details.json

# 2. Iterar entregas
jq -c '.entregas_pendientes[]' details.json | while read student_json; do
    ID=$(echo "$student_json" | jq -r '.alumno_id')
    FILE_URL=$(echo "$student_json" | jq -r '.archivos[0].url // empty')
    
    if [ -z "$FILE_URL" ] || [ "$FILE_URL" == "null" ]; then
        echo "❌ Alumno $ID: Sin archivo."
        mcporter call moodle.submit_grade task_id=$TASK_ID student_id=$ID grade=0.0 feedback="No se encontró archivo." &
        continue
    fi
    
    echo "🔍 Analizando Alumno $ID..."
    
    # Análisis de contenido (el MCP devuelve texto extraido en 'full_content' o 'content_preview')
    ANALYSIS=$(mcporter call moodle.analyze_submission_file file_url="$FILE_URL" --output json)
    TEXT=$(echo "$ANALYSIS" | jq -r '.full_content // .content_preview // ""')
    TYPE=$(echo "$ANALYSIS" | jq -r '.type')
    
    # Métricas simples en bash
    WORD_COUNT=$(echo "$TEXT" | wc -w)
    CHAR_COUNT=$(echo "$TEXT" | wc -c)
    
    echo "   Tipo: $TYPE | Palabras: $WORD_COUNT | Caracteres: $CHAR_COUNT"
    
    # Criterios
    # Base 0
    NOTA=0.0
    FEEDBACK=""
    
    # 1. Formato
    if [[ "$TYPE" == ".docx" ]] || [[ "$TYPE" == ".odt" ]] || [[ "$TYPE" == ".pdf" ]]; then
        NOTA=5.0
        FEEDBACK="Formato correcto."
    elif [[ "$TYPE" == ".txt" ]]; then
        NOTA=4.0
        FEEDBACK="Formato básico."
    else
        # Fallback si no pudo extraer texto o es otro formato
        if [ "$WORD_COUNT" -gt 50 ]; then
             NOTA=5.0 # Asumimos que si hay texto es válido
        else
             NOTA=2.0
             FEEDBACK="Formato no estándar o ilegible."
        fi
    fi
    
    # 2. Extensión (11 preguntas ~ 20-30 palabras por respuesta = 200-300 palabras ideal)
    if [ "$WORD_COUNT" -gt 300 ]; then
        NOTA=$(echo "$NOTA + 4.0" | bc)
        FEEDBACK="$FEEDBACK Respuestas extensas y detalladas."
    elif [ "$WORD_COUNT" -gt 150 ]; then
        NOTA=$(echo "$NOTA + 3.0" | bc)
        FEEDBACK="$FEEDBACK Buena extensión."
    elif [ "$WORD_COUNT" -gt 50 ]; then
        NOTA=$(echo "$NOTA + 1.0" | bc)
        FEEDBACK="$FEEDBACK Respuestas algo breves."
    else
        FEEDBACK="$FEEDBACK Respuestas muy breves o incompletas."
    fi
    
    # 3. Reflexión (bonus)
    if echo "$TEXT" | grep -iqE "siento|pienso|creo|opino|porque"; then
        NOTA=$(echo "$NOTA + 1.0" | bc)
        FEEDBACK="$FEEDBACK Buena reflexión personal."
    fi
    
    # Cap
    if (( $(echo "$NOTA > 10" | bc -l) )); then NOTA=10.0; fi
    
    echo "   📝 Nota: $NOTA"
    
    mcporter call moodle.submit_grade task_id=$TASK_ID student_id=$ID grade=$NOTA feedback="$FEEDBACK" &
    sleep 1
done

wait
echo "✅ Finalizado."
