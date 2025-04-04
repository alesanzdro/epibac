


mkdir -p /home/asanzc/CabinaCS/NLSAR/deposito/CVA_CLIN/illumina

240427_CLIN002


eval "$(ssh-agent -s)"
ssh-add ~/.ssh/almeida-git.key




git commit -m 'refactor: improve configuration and validation system

- Move configuration structure from params.mode to epibac_mode
- Add robust date parsing for DD/MM/YY format in sample validation
- Implement hospital code validation from run_name (AAMMDD_HOSPXXX)
- Fix Kraken2 database configuration structure
- Add validation for required fields based on analysis mode (GVA/normal)
- Improve error handling and warning messages
- Update file naming to use TAG_RUN instead of DATE

The changes simplify the configuration structure while adding stronger
validation for dates, hospital codes and mandatory fields. This ensures
data consistency especially for GVA mode requirements.

Breaking changes:
- Configuration key params.mode is now epibac_mode
- Kraken2 database config structure has changed'


2. Modificación del script validate_samples_info.py
Este script ahora tendrá que realizar validaciones adicionales como:

Comprobar que todas las muestras tengan valores en la columna ID según el modo
Verificar que dorado_model esté configurado si hay muestras nanopore

#!/usr/bin/env python3
import os
import sys
import pandas as pd
import yaml
import json
from jsonschema import validate, ValidationError

def validate_samples(samples_file, schema_file, config_file, warnings_file, output_file):
    """
    Valida el archivo de muestras y genera un archivo corregido.
    """
    # Cargar el archivo de muestras
    try:
        df = pd.read_csv(samples_file)
    except Exception as e:
        sys.exit(f"Error al cargar el archivo de muestras: {e}")
    
    # Cargar el esquema
    try:
        with open(schema_file, 'r') as f:
            schema = json.load(f)
    except Exception as e:
        sys.exit(f"Error al cargar el esquema: {e}")
    
    # Cargar configuración
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        sys.exit(f"Error al cargar la configuración: {e}")
    
    # Obtener modo y primary_id_column de la configuración
    mode = config.get("params", {}).get("mode", "normal")
    if mode == "gva":
        primary_id_column = config.get("params", {}).get("mode_config", {}).get("gva", {}).get("primary_id_column", "id2")
    else:
        primary_id_column = config.get("params", {}).get("mode_config", {}).get("normal", {}).get("primary_id_column", "id")
    
    warnings = []
    
    # Validar que todas las muestras tengan valor en la columna ID según el modo
    if primary_id_column not in df.columns:
        sys.exit(f"Error fatal: La columna {primary_id_column} no existe en el archivo de muestras")
    
    missing_ids = df[df[primary_id_column].isna() | (df[primary_id_column] == "")].index.tolist()
    if missing_ids:
        sys.exit(f"Error fatal: Las siguientes filas no tienen valor en {primary_id_column}: {missing_ids}")
    
    # Verificar si hay muestras nanopore y si dorado_model está configurado
    has_nanopore = False
    if 'ont' in df.columns and not df['ont'].isna().all():
        has_nanopore = True
    
    if has_nanopore:
        dorado_model = config.get("params", {}).get("dorado_model", None)
        if not dorado_model:
            sys.exit(f"Error fatal: Se detectaron muestras Nanopore pero no se ha especificado dorado_model en config.yaml")
    
    # Realizar otras validaciones según el esquema
    # ... (implementación de validación con jsonschema)
    
    # Guardar advertencias
    with open(warnings_file, 'w') as f:
        for warning in warnings:
            f.write(f"{warning}\n")
    
    # Guardar dataframe corregido
    df.to_csv(output_file, index=False)
    
    return True

if __name__ == "__main__":
    if len(sys.argv) != 6:
        sys.exit("Uso: validate_samples.py samples_file schema_file config_file warnings_file output_file")
    
    samples_file = sys.argv[1]
    schema_file = sys.argv[2]
    config_file = sys.argv[3]
    warnings_file = sys.argv[4]
    output_file = sys.argv[5]
    
    validate_samples(samples_file, schema_file, config_file, warnings_file, output_file)

3. Actualización de config.yaml para incluir dorado_model
params:
    # Modo de análisis para lanzar EPIBAC
    mode: "gva"  # Puede ser "normal" o "gva"
    # Carpeta en las que se van a guardar las bases de datos
    refdir: "resources"
    run_name: "240512_CLIN002"
    # Modelo de Dorado para muestras Nanopore (requerido si hay muestras Nanopore)
    dorado_model: "dna_r10.4.1_e8.2_400bps_sup@v4.2.0"
    mode_config:
        gva:
          # Identificador primario de las muestras PETICION (id) o CODIGO_MUESTRA_ORIGEN (id2)
          primary_id_column: "id2"
          # Ruta de la carpeta Cabina de la Conselleria GVA para el copiado de los ficheros
          storage_cabinet: "/home/asanzc/CabinaCS/NLSAR"
        normal:
          primary_id_column: "id"
    # ...resto de la configuración...


4. Actualización del esquema de samples_info.csv (samples.schema.yaml)

{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "description": "Identificador principal de la muestra (obligatorio en modo normal)"
    },
    "id2": {
      "type": ["string", "null"],
      "description": "Identificador secundario (obligatorio en modo GVA)"
    },
    "illumina_r1": {
      "type": ["string", "null"],
      "description": "Ruta al archivo FASTQ R1 de Illumina"
    },
    "illumina_r2": {
      "type": ["string", "null"],
      "description": "Ruta al archivo FASTQ R2 de Illumina"
    },
    "ont": {
      "type": ["string", "null"],
      "description": "Ruta al archivo FASTQ de Oxford Nanopore"
    }
    // ... otros campos ...
  },
  "required": ["id"]
}