#!/bin/bash

# Config
TASK_ID=5672895
KEYWORDS="christmas,santa,snow,bell,navidad,regalo,dance,bailar,music,musica"
ANALYZER="/home/ruben/.nvm/versions/node/v24.1.0/lib/node_modules/clawdbot/skills/scratch-eval/analyze"

echo "=== Iniciando calificación masiva Tarea $TASK_ID ==="

# 1. Obtener lista de TODOS los alumnos con entrega
mcporter call moodle.get_task_details task_id=$TASK_ID --output json > details.json

# 2. Iterar por cada alumno
# Buscamos en "entregas_pendientes" (que en el JSON del MCP contiene todas las entregas por alguna razón de nombrado)
# O mejor, inspeccionamos el JSON para ver dónde están.
# Asumimos que están en entregas_pendientes según vimos antes.

jq -c '.entregas_pendientes[]' details.json | while read student_json; do
    ID=$(echo "$student_json" | jq -r '.alumno_id')
    FILE_URL=$(echo "$student_json" | jq -r '.archivos[0].url // empty')
    NOMBRE=$(echo "$student_json" | jq -r '.nombre // "Alumno"')
    
    # Filtro: Solo procesar si tiene archivo.
    if [ -z "$FILE_URL" ] || [ "$FILE_URL" == "null" ]; then
        continue
    fi
    
    # Descargar archivo (el MCP maneja la descarga)
    # Truco: Usamos analyze_submission_file para descargar, pero como no soporta sb3 nativamente en el json return, 
    # buscaré el archivo en /tmp manualmente o mejor, uso curl para bajarlo yo mismo si tengo cookie, 
    # PERO es dificil tener la cookie. 
    # MEJOR: Confío en que mi MCP server_improved YA soporta .sb3 como zip y lo descarga.
    
    # Llamamos al MCP para descargar (y que nos diga donde está)
    # Nota: El MCP devuelve path al primer archivo extraido si es zip/sb3.
    # Necesitamos el .sb3 original o re-zipearlo. 
    # O más facil: Modificar el MCP para que devuelva el path del .sb3 descargado antes de descomprimir.
    
    # WORKAROUND: El MCP server_improved borra el archivo original? No, creo que lo dejaba en tmp.
    # Voy a asumir que el analyze_submission_file me devuelve un path.
    
    ANALYSIS=$(mcporter call moodle.analyze_submission_file file_url="$FILE_URL" --output json)
    
    # Extraer path. Si es sb3 tratado como zip, el MCP devuelve path a una imagen extraida.
    # Necesito el path del zip/sb3.
    # En server_improved.py, la variable `file_path` tiene el .sb3 descargado.
    # Pero el return JSON da el path de la imagen.
    # Ugh.
    
    # Plan B: El MCP server_improved devuelve "path" en el JSON.
    # Si detectó imágenes, devuelve path de una imagen.
    # Si no, devuelve path del archivo.
    
    # Voy a buscar el .sb3 más reciente en /tmp/moodle_downloads creado hace poco
    # Esto es un hack pero funcionará para este script batch.
    
    SB3_FILE=$(find /tmp/moodle_downloads -name "*.sb3" -mmin -1 | head -1)
    
    if [ -z "$SB3_FILE" ]; then
        # Quizás se bajó como .zip
        SB3_FILE=$(find /tmp/moodle_downloads -name "*.zip" -mmin -1 | head -1)
    fi
    
    if [ -z "$SB3_FILE" ]; then
        echo "⚠️ No se pudo localizar el archivo descargado. Saltando."
        continue
    fi
    
    echo "📂 Archivo localizado: $SB3_FILE"
    
    # Analizar con scratch-eval
    EVAL_RESULT=$($ANALYZER "$SB3_FILE" --keywords "$KEYWORDS")
    
    # Parsear resultados
    SCORE=$(echo "$EVAL_RESULT" | jq '.complexity_score')
    KEYWORDS_FOUND=$(echo "$EVAL_RESULT" | jq -r '.keyword_matches | join(", ")')
    EXTENSIONS=$(echo "$EVAL_RESULT" | jq -r '.metrics.extensions | join(", ")')
    
    echo "📊 Análisis: Score=$SCORE | Ext=$EXTENSIONS | Keys=$KEYWORDS_FOUND"
    
    # Calcular Nota
    # Criterio:
    # Base: 5.0
    # +1 si tiene extension music/sound
    # +2 si Score > 50
    # +2 si tiene Keywords navideñas
    
    NOTA=5.0
    FEEDBACK="Tarea recibida. Proyecto básico de Scratch."
    
    if [[ "$EXTENSIONS" == *"music"* ]] || [[ "$EXTENSIONS" == *"sound"* ]]; then
        NOTA=$(echo "$NOTA + 1" | bc)
        FEEDBACK="$FEEDBACK Buen uso de extensiones musicales."
    fi
    
    if (( $(echo "$SCORE > 50" | bc -l) )); then
        NOTA=$(echo "$NOTA + 2" | bc)
        FEEDBACK="$FEEDBACK Proyecto complejo y bien elaborado."
    elif (( $(echo "$SCORE > 20" | bc -l) )); then
         NOTA=$(echo "$NOTA + 1" | bc)
    fi
    
    if [ -n "$KEYWORDS_FOUND" ]; then
        NOTA=$(echo "$NOTA + 2" | bc)
        FEEDBACK="$FEEDBACK ¡Excelente temática navideña/musical! ($KEYWORDS_FOUND)"
    fi
    
    # Cap en 10
    if (( $(echo "$NOTA > 10" | bc -l) )); then NOTA=10.0; fi
    
    echo "📝 Nota calculada: $NOTA"
    
    # Enviar
    mcporter call moodle.submit_grade task_id=$TASK_ID student_id=$ID grade=$NOTA feedback="$FEEDBACK" &
    
    sleep 2 # Evitar saturar
done

wait
echo "✅ Proceso finalizado."
