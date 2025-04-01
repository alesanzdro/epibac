#!/bin/bash
# filepath: /ALMEIDA/PROJECTS/CODE/epibac/scripts/setup_prokka.sh

set -e  # Exit on error
set -o pipefail

DB_DIR="$1"
FLAG_FILE="$2"
LOG_FILE="$3"

# Crear directorios necesarios
mkdir -p "$DB_DIR" "$DB_DIR/cm" "$DB_DIR/hmm" "$DB_DIR/kingdom"
mkdir -p "$(dirname $LOG_FILE)"

# Iniciar log - MODIFICADO: ahora solo escribe al archivo de log
echo "Iniciando configuración de Prokka en $DB_DIR" > "$LOG_FILE"
date >> "$LOG_FILE"

# Función para loguear sin mostrar por pantalla
log() {
    echo "$@" >> "$LOG_FILE"
}

# Descargar y procesar archivos HMM
if [ ! -f "$DB_DIR/PGAP.hmm" ]; then
    log "Descargando archivos HMM de PGAP"
    cd "$DB_DIR"
    wget --no-check-certificate -O hmm_PGAP.HMM.tgz https://ftp.ncbi.nlm.nih.gov/hmm/current/hmm_PGAP.HMM.tgz >> "$LOG_FILE" 2>&1
    
    log "Extrayendo archivos HMM"
    tar -xzf hmm_PGAP.HMM.tgz >> "$LOG_FILE" 2>&1
    
    log "Concatenando archivos HMM"
    find hmm_PGAP -type f -name "*.HMM" -exec cat {} + > PGAP.hmm.raw 2>> "$LOG_FILE"
    
    log "Filtrando duplicados"
    awk '/^NAME/ { if (a[$2]++) skip=1; else skip=0 } !skip { print }' PGAP.hmm.raw > PGAP.hmm 2>> "$LOG_FILE"
    
    log "Creando índices HMM"
    hmmpress -f PGAP.hmm >> "$LOG_FILE" 2>&1 || log "Advertencia: hmmpress terminó con errores, continuando de todos modos"
    
    # Limpieza
    log "Limpiando archivos temporales"
    rm -rf hmm_PGAP hmm_PGAP.HMM.tgz PGAP.hmm.raw >> "$LOG_FILE" 2>&1
else
    log "Los archivos HMM ya existen, omitiendo descarga"
fi

# Descargar archivos CM
for CM_FILE in Archaea Bacteria Viruses; do
    if [ ! -f "$DB_DIR/cm/$CM_FILE" ]; then
        log "Descargando $CM_FILE"
        wget --no-check-certificate -O "$DB_DIR/cm/$CM_FILE" "https://github.com/tseemann/prokka/raw/master/db/cm/$CM_FILE" >> "$LOG_FILE" 2>&1 || \
        wget --no-check-certificate -O "$DB_DIR/cm/$CM_FILE" "https://raw.githubusercontent.com/tseemann/prokka/master/db/cm/$CM_FILE" >> "$LOG_FILE" 2>&1
    fi
done

# Crear archivo de versión
log "Creando archivo de versión"
echo "PGAP HMM database" > "$DB_DIR/VERSION.txt"
echo "Fecha de instalación: $(date)" >> "$DB_DIR/VERSION.txt"

# Crear flag
log "Creando flag de finalización"
echo "Prokka database installed successfully" > "$FLAG_FILE"
log "Configuración completada"
date >> "$LOG_FILE"