#!/usr/bin/env python3
import os
import sys
import pandas as pd
import yaml
from datetime import datetime
import re

# Códigos de estado para la validación
STATUS_OK = 0       # Todo correcto
STATUS_WARNINGS = 1  # Con advertencias no críticas
STATUS_ERRORS = 2   # Con errores pero procesable
STATUS_FATAL = 3    # Errores fatales, imposible procesar

def validate_samples(samples_file, schema_file, config_file, report_file, output_file):
    """
    Valida el archivo de muestras y genera un archivo corregido según el modo.
    Retorna un código de estado y genera un informe detallado.
    """
    warnings = []
    errors = []
    fatal_errors = []
    
    # Cargar configuración
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        fatal_errors.append(f"Error al cargar la configuración: {e}")
        _write_report(report_file, [], [], fatal_errors)
        return STATUS_FATAL

    # Determinar el modo de análisis
    mode = config.get("mode", "normal")

    # Validar run_name en modo GVA
    if mode == "gva":
        run_name = config.get("run_name", "")
        if not run_name:
            fatal_errors.append("Error: No se ha especificado run_name en la configuración para modo GVA")
            _write_report(report_file, [], [], fatal_errors)
            return STATUS_FATAL
            
        # Validar formato AAMMDD_HOSPXXX
        run_pattern = re.compile(r"^\d{6}_[A-Z]{4}\d{3}$")
        if not run_pattern.match(run_name):
            fatal_errors.append(f"Error: El formato de run_name '{run_name}' no es válido para modo GVA. Debe seguir el formato AAMMDD_HOSPXXX")
            _write_report(report_file, [], [], fatal_errors)
            return STATUS_FATAL
        
        # Extraer y validar código de hospital
        hospital_code = run_name.split("_")[1][:4]
        valid_hospitals = ["ALIC", "CAST", "ELCH", "GRAL", "PESE", "CLIN", "LAFE", "EPIM"]
        if hospital_code not in valid_hospitals:
            fatal_errors.append(f"Error: Código de hospital '{hospital_code}' no válido. Debe ser uno de: {', '.join(valid_hospitals)}")
            _write_report(report_file, [], [], fatal_errors)
            return STATUS_FATAL

    # Cargar el archivo de muestras
    try:
        # Intentar primero con punto y coma (común en GVA)
        try:
            df = pd.read_csv(samples_file, sep=";", dtype=str)
            separator = ";"
        except:
            # Si falla, intentar con coma
            try:
                df = pd.read_csv(samples_file, sep=",", dtype=str)
                separator = ","
            except Exception as e:
                fatal_errors.append(f"Error al cargar el archivo de muestras: {e}")
                _write_report(report_file, [], [], fatal_errors)
                return STATUS_FATAL
    except Exception as e:
        fatal_errors.append(f"Error inesperado al procesar el archivo: {e}")
        _write_report(report_file, [], [], fatal_errors)
        return STATUS_FATAL

    # Verificar columnas según el modo
    if mode == "gva":
        # Columnas obligatorias para GVA
        required_columns = ["PETICION", "CODIGO_MUESTRA_ORIGEN", "ILLUMINA_R1", "ILLUMINA_R2", "NANOPORE"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            fatal_errors.append(f"Error: Columnas obligatorias faltantes para modo GVA: {', '.join(missing_columns)}")
            _write_report(report_file, [], [], fatal_errors)
            return STATUS_FATAL
        
        # Columnas importantes pero no absolutamente obligatorias
        important_columns = ["FECHA_TOMA_MUESTRA", "ESPECIE_SECUENCIA", "MOTIVO_WGS"]
        missing_important = [col for col in important_columns if col not in df.columns]
        if missing_important:
            errors.append(f"Error: Columnas importantes faltantes: {', '.join(missing_important)}")
        
        # Mapear columnas GVA a nombres estándar internos
        rename_map_gva = {
            "PETICION": "id",
            "CODIGO_MUESTRA_ORIGEN": "id2",
            "FECHA_TOMA_MUESTRA": "collection_date",
            "ESPECIE_SECUENCIA": "organism",
            "MOTIVO_WGS": "relevance",
            "ILLUMINA_R1": "illumina_r1",
            "ILLUMINA_R2": "illumina_r2",
            "NANOPORE": "nanopore",
            "ID_WS": "scheme_mlst",
            "ST_WGS": "st",
            "MLST_WGS": "mlst",
            "R_Geno_WGS": "amr",
            "PHENO_WGS": "pheno_resfinder",
            "V_WGS": "virulence",
            "CONFIRMACION": "confirmation_note",
            "NUM_BROTE": "outbreak_id",
            "COMENTARIO_WGS": "comment",
        }

        # Aplicar solo las columnas que existen
        rename_dict = {k: v for k, v in rename_map_gva.items() if k in df.columns}
        df = df.rename(columns=rename_dict)

        # Obtener primary_id_column según la configuración
        if mode == "gva":
            primary_id_column = config.get("mode_config", {}).get("gva", {}).get("primary_id_column", "id2")
        else:
            primary_id_column = config.get("mode_config", {}).get("normal", {}).get("primary_id_column", "id")

        # Verificar que primary_id_column existe después del renombrado
        if primary_id_column not in df.columns:
            fatal_errors.append(f"Error: La columna {primary_id_column} no existe después del renombrado en modo GVA")
            _write_report(report_file, [], [], fatal_errors)
            return STATUS_FATAL
            
        # Verificar campos obligatorios estén llenos
        for i, row in df.iterrows():
            if pd.isna(row.get('organism')) or str(row.get('organism')).strip() == '':
                errors.append(f"Error en fila {i+2}: Especie/organismo no especificado")
            
            if pd.isna(row.get('relevance')) or str(row.get('relevance')).strip() == '':
                errors.append(f"Error en fila {i+2}: Motivo de análisis no especificado")
            
            if pd.isna(row.get('collection_date')) or str(row.get('collection_date')).strip() == '':
                warnings.append(f"Advertencia en fila {i+2}: Fecha de toma de muestra no especificada")
    else:  # modo normal
        required_columns = ["id", "illumina_r1", "illumina_r2", "nanopore"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            fatal_errors.append(f"Error: Columnas obligatorias faltantes para modo normal: {', '.join(missing_columns)}")
            _write_report(report_file, [], [], fatal_errors)
            return STATUS_FATAL

        # En modo normal, primary_id_column es "id"
        primary_id_column = "id"

    # Verificar que todas las muestras tienen valor en la columna ID primaria
    missing_ids = df[df[primary_id_column].isna() | (df[primary_id_column] == "")].index.tolist()
    if missing_ids:
        fatal_errors.append(f"Error: Filas sin valor en {primary_id_column}: {[i+2 for i in missing_ids]}")
        _write_report(report_file, [], [], fatal_errors)
        return STATUS_FATAL

    # Verificar existencia de archivos FASTQ
    fastq_columns = [col for col in df.columns if col in ["illumina_r1", "illumina_r2", "nanopore"]]
    for col in fastq_columns:
        for i, file_path in enumerate(df[col]):
            if pd.notna(file_path) and file_path and not os.path.exists(file_path):
                warnings.append(f"Advertencia: El archivo {file_path} en la columna {col}, fila {i+2} no existe")

    # Formatear fechas
    def parse_date(date_str):
        """Parsea una fecha en varios formatos posibles y la convierte a YYYY-MM-DD."""
        if pd.isna(date_str) or date_str == "":
            return None
            
        date_patterns = [
            (r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2})$", "%d/%m/%y"),
            (r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$", "%d/%m/%Y"),
            (r"(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})$", "%Y/%m/%d"),
        ]

        for pattern, date_format in date_patterns:
            match = re.match(pattern, str(date_str))
            if match:
                try:
                    clean_date = re.sub(r"[.-]", "/", str(date_str))
                    parsed_date = datetime.strptime(clean_date, date_format)
                    return parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    continue
        return None

    # Procesar fechas
    if "collection_date" in df.columns:
        for i, date_str in enumerate(df["collection_date"]):
            if pd.notna(date_str) and date_str:
                parsed_date = parse_date(str(date_str))
                if parsed_date:
                    df.at[i, "collection_date"] = parsed_date
                else:
                    errors.append(f"Error en fila {i+2}: Formato de fecha inválido: '{date_str}'")

    # Verificar muestras nanopore y configuración dorado_model
    has_nanopore = False
    if "nanopore" in df.columns and not df["nanopore"].isna().all() and not (df["nanopore"] == "").all():
        has_nanopore = True

    if has_nanopore:
        dorado_model = config.get("params", {}).get("nanopore", {}).get("dorado_model", None)
        if not dorado_model:
            errors.append("Error: Se detectaron muestras Nanopore pero no se ha especificado dorado_model en config.yaml")
        else:
            valid_models = [
                "dna_r10.4.1_e8.2_400bps_hac@v4.2.0",
                "dna_r10.4.1_e8.2_400bps_sup@v4.2.0",
                "dna_r9.4.1_450bps_hac@v3.3",
                "dna_r9.4.1_450bps_sup@v3.3",
            ]
            if dorado_model not in valid_models:
                errors.append(f"Error: Modelo Dorado '{dorado_model}' no válido. Debe ser uno de: {', '.join(valid_models)}")

    # Escribir informe de validación
    status = _write_report(report_file, warnings, errors, fatal_errors)
    
    # Si hay errores fatales, no generar el archivo de salida
    if status == STATUS_FATAL:
        return status
        
    # Guardar dataframe corregido
    try:
        df.to_csv(output_file, index=False, sep=separator)
    except Exception as e:
        fatal_errors.append(f"Error al guardar el archivo de salida: {e}")
        _write_report(report_file, warnings, errors, fatal_errors)
        return STATUS_FATAL
        
    return status

def _write_report(report_file, warnings, errors, fatal_errors):
    """Escribe el informe de validación y determina el estado."""
    with open(report_file, "w") as f:
        if fatal_errors:
            f.write("===== ERRORES FATALES =====\n")
            for error in fatal_errors:
                f.write(f"{error}\n")
            f.write("\n")
            return STATUS_FATAL
            
        if errors:
            f.write("===== ERRORES =====\n")
            for error in errors:
                f.write(f"{error}\n")
            f.write("\n")
            
        if warnings:
            f.write("===== ADVERTENCIAS =====\n")
            for warning in warnings:
                f.write(f"{warning}\n")
            f.write("\n")
            
        if not errors and not warnings:
            f.write("===== VALIDACIÓN EXITOSA =====\n")
            f.write("No se encontraron problemas en el archivo de muestras.\n")
            return STATUS_OK
        elif errors:
            return STATUS_ERRORS
        else:
            return STATUS_WARNINGS

if __name__ == "__main__":
    if len(sys.argv) != 6:
        sys.exit("Uso: validate_samples.py samples_file schema_file config_file report_file output_file")

    samples_file = sys.argv[1]
    schema_file = sys.argv[2]
    config_file = sys.argv[3]
    report_file = sys.argv[4]
    output_file = sys.argv[5]

    status = validate_samples(samples_file, schema_file, config_file, report_file, output_file)
    
    # Salir con el código de estado adecuado
    if status == STATUS_FATAL:
        print(f"VALIDACIÓN FALLIDA: Se encontraron errores fatales. Ver {report_file} para detalles.")
        sys.exit(1)
    elif status == STATUS_ERRORS:
        print(f"VALIDACIÓN CON ERRORES: Se encontraron errores. Ver {report_file} para detalles.")
        sys.exit(0)  # Salir con éxito pero indicando que hay errores
    elif status == STATUS_WARNINGS:
        print(f"VALIDACIÓN CON ADVERTENCIAS: Ver {report_file} para detalles.")
        sys.exit(0)  # Salir con éxito
    else:
        print("VALIDACIÓN EXITOSA: No se encontraron problemas.")
        sys.exit(0)