#!/usr/bin/env python3
import os
import sys
import pandas as pd
import yaml
import json
from datetime import datetime
import re

def validate_samples(samples_file, schema_file, config_file, warnings_file, output_file):
    """
    Valida el archivo de muestras y genera un archivo corregido según el modo.
    """
    warnings = []
    
    # Cargar configuración
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        sys.exit(f"Error al cargar la configuración: {e}")
    
    # Determinar el modo de análisis
    mode = config.get("epibac_mode", "normal")
    
    # Si estamos en modo GVA, validar el código de hospital en run_name
    if mode == "gva":
        run_name = config.get("params", {}).get("run_name", "")
        if run_name:
            # Extraer el código de hospital (formato esperado: AAMMDD_HOSPXXX)
            parts = run_name.split("_")
            if len(parts) >= 2:
                hospital_code = parts[1][:4]  # Primeros 4 caracteres del segundo segmento
                
                # Lista de hospitales válidos
                valid_hospitals = ["ALIC", "CAST", "ELCH", "GRAL", "PESE", "CLIN", "LAFE", "EPIM"]
                
                # Verificar si el hospital es válido
                if hospital_code not in valid_hospitals:
                    sys.exit(f"Error: Código de hospital '{hospital_code}' extraído de run_name '{run_name}' no es válido. Debe ser uno de: {', '.join(valid_hospitals)}")
            else:
                sys.exit(f"Error: El formato de run_name '{run_name}' no es válido para modo GVA. Debe seguir el formato AAMMDD_HOSPXXX")
    
    # Cargar el archivo de muestras y determinar el separador
    try:
        # Intentar primero con punto y coma (común en GVA)
        df = pd.read_csv(samples_file, sep=";")
        separator = ";"
    except:
        try:
            # Si falla, intentar con coma
            df = pd.read_csv(samples_file, sep=",")
            separator = ","
        except Exception as e:
            sys.exit(f"Error al cargar el archivo de muestras: {e}")
    
    # Verificar columnas según el modo
    if mode == "gva":
        required_columns = ["PETICION", "CODIGO_MUESTRA_ORIGEN", "ILLUMINA_R1", "ILLUMINA_R2", "NANOPORE"]
        # Verificar que existen las columnas necesarias
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            sys.exit(f"Error: El archivo no contiene las columnas obligatorias para modo GVA: {', '.join(missing_columns)}")
        
        # Mapear columnas GVA a nombres estándar internos
        rename_map_gva = {
            "PETICION": "id",
            "CODIGO_MUESTRA_ORIGEN": "id2",
            "FECHA_TOMA_MUESTRA": "collection_date",
            "ESPECIE_SECUENCIA": "organism",
            "MOTIVO_WGS": "relevance",
            "ILLUMINA_R1": "illumina_r1",
            "ILLUMINA_R2": "illumina_r2",
            "ONT": "ont",  # Cambio a 'ont' para coherencia interna
            "ID_WS": "Scheme_mlst",
            "ST_WGS": "ST",
            "MLST_WGS": "MLST",
            "R_Geno_WGS": "AMR",
            "PHENO_WGS": "PHENO_resfinder",
            "V_WGS": "VIRULENCE",
            "CONFIRMACION": "confirmation_note",
            "NUM_BROTE": "outbreak_id",
            "COMENTARIO_WGS": "comment"
        }
        
        # Aplicar solo las columnas que existen
        rename_dict = {k: v for k, v in rename_map_gva.items() if k in df.columns}
        df = df.rename(columns=rename_dict)
        
        # Obtener primary_id_column según la configuración
        primary_id_column = config.get("params", {}).get("mode_config", {}).get("gva", {}).get("primary_id_column", "id2")
        
        # Verificar que primary_id_column existe después del renombrado
        if primary_id_column not in df.columns:
            sys.exit(f"Error: La columna {primary_id_column} no existe después del renombrado en modo GVA")
    else:  # modo normal
        required_columns = ["id", "illumina_r1", "illumina_r2", "nanopore"]
        # Verificar que existen las columnas necesarias
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            sys.exit(f"Error: El archivo no contiene las columnas obligatorias para modo normal: {', '.join(missing_columns)}")
        
        # En modo normal, cambiar nanopore a ont para coherencia interna
        if "nanopore" in df.columns:
            df = df.rename(columns={"nanopore": "ont"})
        
        # Siempre primary_id_column es "id" en modo normal
        primary_id_column = "id"
    
    # Verificar que todas las muestras tienen valor en la columna ID primaria
    missing_ids = df[df[primary_id_column].isna() | (df[primary_id_column] == "")].index.tolist()
    if missing_ids:
        sys.exit(f"Error: Las siguientes filas no tienen valor en {primary_id_column}: {missing_ids}")
    
    # Verificar existencia de archivos FASTQ (como advertencia)
    fastq_columns = [col for col in df.columns if col in ["illumina_r1", "illumina_r2", "ont"]]
    for col in fastq_columns:
        for i, file_path in enumerate(df[col]):
            if pd.notna(file_path) and file_path and not os.path.exists(file_path):
                warnings.append(f"Advertencia: El archivo {file_path} en la columna {col}, fila {i+2} no existe")
    
    # En la sección de formateo de fechas, actualizar el código:

    def parse_date(date_str):
        """Parsea una fecha en varios formatos posibles y la convierte a YYYY-MM-DD."""
        date_patterns = [
            # DD/MM/YY o DD-MM-YY (año corto)
            (r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{2})$', '%d/%m/%y'),
            # DD/MM/YYYY o DD-MM-YYYY (año completo)
            (r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$', '%d/%m/%Y'),
            # YYYY/MM/DD o YYYY-MM-DD
            (r'(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})$', '%Y/%m/%d')
        ]
    
        for pattern, date_format in date_patterns:
            match = re.match(pattern, date_str)
            if match:
                try:
                    # Reemplazar cualquier separador por '/'
                    clean_date = re.sub(r'[.-]', '/', date_str)
                    # Parsear la fecha
                    parsed_date = datetime.strptime(clean_date, date_format)
                    # Devolver en formato estándar
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
        return None

    # Usar la nueva función en el bucle de procesamiento de fechas:
    if "collection_date" in df.columns:
        for i, date_str in enumerate(df["collection_date"]):
            if pd.notna(date_str) and date_str:
                parsed_date = parse_date(str(date_str))
                if parsed_date:
                    df.at[i, "collection_date"] = parsed_date
                else:
                    warnings.append(f"Advertencia: No se pudo parsear la fecha '{date_str}' en la fila {i+2}")


    # Verificar si hay muestras nanopore y si dorado_model está configurado
    has_nanopore = False
    if 'ont' in df.columns and not df['ont'].isna().all() and not (df['ont'] == "").all():
        has_nanopore = True
    
    if has_nanopore:
        dorado_model = config.get("params", {}).get("dorado_model", None)
        if not dorado_model:
            sys.exit(f"Error: Se detectaron muestras Nanopore pero no se ha especificado dorado_model en config.yaml")
        
        # Verificar que dorado_model sea uno de los valores permitidos
        valid_models = ["dna_r10.4.1_e8.2_400bps_hac@v4.2.0", "dna_r10.4.1_e8.2_400bps_sup@v4.2.0", 
                       "dna_r9.4.1_450bps_hac@v3.3", "dna_r9.4.1_450bps_sup@v3.3"]
        if dorado_model not in valid_models:
            sys.exit(f"Error: El modelo Dorado '{dorado_model}' no es válido. Debe ser uno de: {', '.join(valid_models)}")
    
    # Guardar advertencias
    with open(warnings_file, 'w') as f:
        for warning in warnings:
            f.write(f"{warning}\n")
    
    # Guardar dataframe corregido
    df.to_csv(output_file, index=False, sep=separator)
    
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
