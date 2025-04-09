#!/usr/bin/env python3
import os
import sys
import pandas as pd
import yaml
import json
from datetime import datetime
import re
import argparse

def parse_arguments():
    """Parsea los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description='Validador de archivos de muestras para EPIBAC')
    parser.add_argument('--samples', '-s', required=True, help='Archivo de muestras a validar')
    parser.add_argument('--config', '-c', default='config.yaml', help='Archivo de configuración')
    parser.add_argument('--mode', '-m', choices=['gva', 'normal'], help='Modo de análisis (sobrescribe config)')
    parser.add_argument('--output', '-o', help='Guardar versión validada en este archivo (opcional)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Mostrar información detallada')
    return parser.parse_args()

def validate_samples(samples_file, config, mode=None, verbose=False):
    """
    Valida el archivo de muestras.
    
    Args:
        samples_file: Ruta al archivo de muestras
        config: Diccionario con configuración o ruta al archivo config.yaml
        mode: Sobrescribe el modo en config (gva o normal)
        verbose: Si es True, muestra mensajes informativos adicionales
    
    Returns:
        dict: Con las claves "status" (0-3), "warnings", "errors", "fatal_errors" y "validated_df"
    """
    warnings = []
    errors = []
    fatal_errors = []
    validated_df = None
    
    # Cargar configuración si es una ruta
    if isinstance(config, str):
        try:
            with open(config, "r") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            fatal_errors.append(f"Error al cargar la configuración: {e}")
            return {
                "status": 3,
                "warnings": warnings,
                "errors": errors,
                "fatal_errors": fatal_errors,
                "validated_df": None
            }
    
    # Determinar el modo de análisis
    mode = mode or config.get("mode", "normal")
    if verbose:
        print(f"Modo de validación: {mode}")
    
    # Validar run_name en modo GVA
    if mode == "gva":
        run_name = config.get("run_name", "")
        if not run_name:
            fatal_errors.append("No se ha especificado run_name en la configuración para modo GVA")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
            
        # Validar formato AAMMDD_HOSPXXX
        run_pattern = re.compile(r"^\d{6}_[A-Z]{4}\d{3}$")
        if not run_pattern.match(run_name):
            fatal_errors.append(f"El formato de run_name '{run_name}' no es válido para modo GVA. " 
                               f"Debe seguir el formato AAMMDD_HOSPXXX")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
        
        # Validar código de hospital
        hospital_code = run_name.split("_")[1][:4]
        valid_hospitals = ["ALIC", "CAST", "ELCH", "GRAL", "PESE", "CLIN", "LAFE", "EPIM"]
        if hospital_code not in valid_hospitals:
            fatal_errors.append(f"Código de hospital '{hospital_code}' no válido. " 
                               f"Debe ser uno de: {', '.join(valid_hospitals)}")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
    
    # Cargar y detectar el formato del archivo
    try:
        try:
            df = pd.read_csv(samples_file, sep=";", dtype=str)
            separator = ";"
            if verbose:
                print(f"Archivo cargado con separador: punto y coma (;)")
        except:
            try:
                df = pd.read_csv(samples_file, sep=",", dtype=str)
                separator = ","
                if verbose:
                    print(f"Archivo cargado con separador: coma (,)")
            except Exception as e:
                fatal_errors.append(f"Error al cargar el archivo de muestras: {e}")
                return {"status": 3, "warnings": warnings, "errors": errors, 
                        "fatal_errors": fatal_errors, "validated_df": None}
    except Exception as e:
        fatal_errors.append(f"Error inesperado al procesar el archivo: {e}")
        return {"status": 3, "warnings": warnings, "errors": errors, 
                "fatal_errors": fatal_errors, "validated_df": None}

    # Verificar columnas según el modo
    if mode == "gva":
        # Columnas obligatorias para GVA
        required_columns = ["PETICION", "CODIGO_MUESTRA_ORIGEN"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        # Al menos uno de estos debe existir
        data_columns = ["ILLUMINA_R1", "ILLUMINA_R2", "NANOPORE"]
        has_data_column = any(col in df.columns for col in data_columns)
        
        if missing_columns:
            fatal_errors.append(f"Columnas obligatorias faltantes para modo GVA: {', '.join(missing_columns)}")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
                    
        if not has_data_column:
            fatal_errors.append(f"Debe incluir al menos una de estas columnas: {', '.join(data_columns)}")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
        
        # Columnas importantes pero no absolutamente obligatorias
        important_columns = ["FECHA_TOMA_MUESTRA", "ESPECIE_SECUENCIA", "MOTIVO_WGS"]
        missing_important = [col for col in important_columns if col not in df.columns]
        if missing_important:
            errors.append(f"Columnas importantes faltantes: {', '.join(missing_important)}")
        
        # Mapear columnas GVA a nombres estándar internos
        rename_map_gva = {
            "CODIGO_MUESTRA_ORIGEN": "id",
            "PETICION": "id2",
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
        validated_df = df.rename(columns=rename_dict)

        # En modo GVA, verificar que la columna id existe después del renombrado
        if "id" not in validated_df.columns:
            fatal_errors.append(f"La columna id (remapeada desde CODIGO_MUESTRA_ORIGEN) no existe después del renombrado")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
        
        # Verificar campos obligatorios estén llenos
        for i, row in validated_df.iterrows():
            # Verificar PETICION (id2)
            if 'id2' in validated_df.columns:
                if pd.isna(row.get('id2')) or str(row.get('id2')).strip() == '':
                    errors.append(f"Error en fila {i+2}: PETICION no especificada")
            
            # Verificar campos importantes
            if 'organism' in validated_df.columns:
                if pd.isna(row.get('organism')) or str(row.get('organism')).strip() == '':
                    errors.append(f"Error en fila {i+2}: Especie/organismo no especificado")
            
            if 'relevance' in validated_df.columns:
                if pd.isna(row.get('relevance')) or str(row.get('relevance')).strip() == '':
                    errors.append(f"Error en fila {i+2}: Motivo de análisis no especificado")
            
            if 'collection_date' in validated_df.columns:
                if pd.isna(row.get('collection_date')) or str(row.get('collection_date')).strip() == '':
                    warnings.append(f"Advertencia en fila {i+2}: Fecha de toma de muestra no especificada")
            
            # Verificar que tenga al menos una fuente de datos
            has_data = False
            for col in ['illumina_r1', 'nanopore']:
                if col in validated_df.columns:
                    if not pd.isna(row.get(col)) and str(row.get(col)).strip() != '':
                        has_data = True
                        break
            
            if not has_data:
                errors.append(f"Error en fila {i+2}: No se especificó ninguna fuente de datos (illumina_r1 o nanopore)")
            
    else:  # modo normal
        required_columns = ["id"]
        data_columns = ["illumina_r1", "illumina_r2", "nanopore"]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        has_data_column = any(col in df.columns for col in data_columns)
        
        if missing_columns:
            fatal_errors.append(f"Columnas obligatorias faltantes para modo normal: {', '.join(missing_columns)}")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
                    
        if not has_data_column:
            fatal_errors.append(f"Debe incluir al menos una de estas columnas: {', '.join(data_columns)}")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}

        # En modo normal, no hacemos renombrado
        validated_df = df.copy()

    # Verificar que todas las muestras tienen valor en la columna ID primaria
    missing_ids = validated_df[validated_df["id"].isna() | (validated_df["id"] == "")].index.tolist()
    if missing_ids:
        fatal_errors.append(f"Filas sin valor en la columna de identificación: {[i+2 for i in missing_ids]}")
        return {"status": 3, "warnings": warnings, "errors": errors, 
                "fatal_errors": fatal_errors, "validated_df": None}
                
    # Verificar caracteres especiales en los IDs
    invalid_chars_pattern = re.compile(r'[^\w\-_]')
    for i, sample_id in enumerate(validated_df["id"]):
        if invalid_chars_pattern.search(str(sample_id)):
            errors.append(f"Error en fila {i+2}: ID '{sample_id}' contiene caracteres especiales no permitidos")
    # Verificar existencia de archivos FASTQ
    fastq_columns = [col for col in validated_df.columns 
                    if col in ["illumina_r1", "illumina_r2", "nanopore"]]
    for col in fastq_columns:
        for i, file_path in enumerate(validated_df[col]):
            if pd.notna(file_path) and file_path and not os.path.exists(file_path):
                warnings.append(f"El archivo {file_path} en columna {col}, fila {i+2} no existe")

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
    if "collection_date" in validated_df.columns:
        for i, date_str in enumerate(validated_df["collection_date"]):
            if pd.notna(date_str) and date_str:
                parsed_date = parse_date(str(date_str))
                if parsed_date:
                    validated_df.at[i, "collection_date"] = parsed_date
                else:
                    errors.append(f"Error en fila {i+2}: Formato de fecha inválido: '{date_str}'")

    # Verificar muestras nanopore y configuración dorado_model
    has_nanopore = False
    if "nanopore" in validated_df.columns and not validated_df["nanopore"].isna().all() and not (validated_df["nanopore"] == "").all():
        has_nanopore = True

    if has_nanopore:
        dorado_model = config.get("params", {}).get("nanopore", {}).get("dorado_model", None)
        if not dorado_model:
            errors.append("Se detectaron muestras Nanopore pero no se ha especificado dorado_model en config.yaml")
        else:
            valid_models = [
                "dna_r10.4.1_e8.2_400bps_hac@v4.2.0",
                "dna_r10.4.1_e8.2_400bps_sup@v4.2.0",
                "dna_r9.4.1_450bps_hac@v3.3",
                "dna_r9.4.1_450bps_sup@v3.3",
            ]
            if dorado_model not in valid_models:
                errors.append(f"Modelo Dorado '{dorado_model}' no válido. Debe ser uno de: {', '.join(valid_models)}")

    # Determinar el estado final
    status = 0  # Por defecto, todo OK
    if fatal_errors:
        status = 3  # Errores fatales
        validated_df = None
    elif errors:
        status = 2  # Errores no fatales
    elif warnings:
        status = 1  # Solo advertencias
        
    return {
        "status": status,
        "warnings": warnings,
        "errors": errors,
        "fatal_errors": fatal_errors,
        "validated_df": validated_df,
        "separator": separator if "separator" in locals() else ";"
    }

def print_validation_result(result, verbose=False):
    """Imprime el resultado de la validación de forma amigable."""
    if result["fatal_errors"]:
        print("\n┏━━━━━━━━━━━━━━━━━━━━━━ VALIDACIÓN FALLIDA ❌ ━━━━━━━━━━━━━━━━━━━┓")
        print("┃ Se encontraron errores que impiden continuar:                  ┃")
        print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
        for error in result["fatal_errors"]:
            print(f"❌ {error}")
        return
        
    if result["errors"]:
        print("\n┏━━━━━━━━━━━━━━━━━━━━ VALIDACIÓN CON ERRORES ⚠️  ━━━━━━━━━━━━━━━━━┓")
        print("┃ El archivo tiene errores que deberían corregirse:              ┃")
        print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
        for error in result["errors"]:
            print(f"⚠️ {error}")
        print("")
        
    if result["warnings"]:
        if not result["errors"]:
            print("\n┏━━━━━━━━━━━━━━━━━━ VALIDACIÓN CON ADVERTENCIAS ℹ️  ━━━━━━━━━━━━━━┓")
            print("┃ El archivo tiene advertencias que podrías revisar:             ┃")
            print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
        for warning in result["warnings"]:
            print(f"ℹ️ {warning}")
        print("")
        
    if not result["errors"] and not result["warnings"]:
        print("\n┏━━━━━━━━━━━━━━━━━━━━━━ VALIDACIÓN EXITOSA ━━━━━━━━━━━━━━━━━━━━━━┓")
        print("┃ El archivo de muestras ha sido validado correctamente          ┃")
        print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")

def main():
    args = parse_arguments()
    
    # Si se proporciona un modo en la línea de comandos, sobrescribe el config
    if args.config and not os.path.exists(args.config):
        print(f"ADVERTENCIA: Archivo de configuración no encontrado: {args.config}")
        print("Usando valores por defecto")
        config = {"mode": args.mode} if args.mode else {"mode": "normal"}
    else:
        try:
            with open(args.config, "r") as f:
                config = yaml.safe_load(f)
                if args.mode:  # Sobrescribir modo si se especificó
                    config["mode"] = args.mode
        except Exception as e:
            print(f"Error al cargar la configuración: {e}")
            return 1
    
    # Ejecutar validación
    print(f"Validando archivo: {args.samples}")
    result = validate_samples(args.samples, config, verbose=args.verbose)
    
    # Imprimir resultados
    print_validation_result(result, verbose=args.verbose)
    
    # Guardar archivo validado si se solicitó
    if args.output and result["status"] < 3 and result["validated_df"] is not None:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
            result["validated_df"].to_csv(args.output, index=False, sep=result["separator"])
            print(f"\nArchivo validado guardado en: {args.output}")
        except Exception as e:
            print(f"\nError al guardar archivo validado: {e}")
    
    # Salir con código adecuado
    return 0 if result["status"] < 2 else 1

if __name__ == "__main__":
    sys.exit(main())