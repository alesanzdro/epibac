#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Usage:
  python validate_samples.py samples_info.csv samples.schema.yaml config.yaml validation_warnings.txt samples_info_validated.csv

Proceso:
1. Detecta el separador (',' o ';') y comillas en samples_info.csv.
2. Carga config.yaml (YAML).
3. Valida el CSV con snakemake.utils.validate y el esquema samples.schema.yaml.
4. Realiza validaciones extra y normalizaciones:
   - Fechas en FECHA_TOMA_MUESTRA => AAAA-MM-DD (detecta formatos 'DD/MM/YY', etc.).
   - Modo GVA => PETICION y CARRERA obligatorias, con formato 'AAMMDD_HOSPxxx' en CARRERA.
   - Modo normal => al menos uno de id o id2 (o si usas CODIGO_MUESTRA_ORIGEN/PETICION, etc.).
   - Illumina => si ILLUMINA_R1 está, ILLUMINA_R2 también y viceversa.
   - ONT => si ONT está, MODELO_DORADO también.
   - Normaliza ESPECIE_SECUENCIA (minusculas, guiones bajos), avisa si no existe en config.yaml.
5. Registra advertencias/correcciones en un log. Si hay errores graves, sale con exit code 1.
"""

import sys
import gzip
import os
import csv
import yaml
import re
import datetime
from snakemake.utils import validate
import pandas as pd

def is_valid_fastq_gz(filepath):
    """
    Verifica que un archivo:
    1. Existe
    2. Tiene extensión .gz
    3. No está vacío
    4. Es un archivo gzip válido y legible
    5. Parece contener datos FASTQ (líneas que comienzan con @)
    
    Retorna (es_valido, mensaje_error)
    """
    try:
        if not os.path.exists(filepath):
            return False, f"El archivo no existe: '{filepath}'"
            
        if not filepath.lower().endswith('.gz'):
            return False, f"El archivo no tiene extensión .gz: '{filepath}'"
            
        if os.path.getsize(filepath) == 0:
            return False, f"El archivo está vacío: '{filepath}'"
            
        # Intentar abrir y leer las primeras líneas para verificar que es un gzip válido
        with gzip.open(filepath, 'rt') as f:
            # Leemos las primeras 4 líneas para verificar formato FASTQ
            lines = [f.readline() for _ in range(4)]
            
            # Si no hay contenido, el archivo está vacío o corrupto
            if not lines or not lines[0]:
                return False, f"El archivo no contiene datos: '{filepath}'"
                
            # Verificar que parece formato FASTQ (primera línea empieza con @)
            if not lines[0].startswith('@'):
                return False, f"El archivo no parece tener formato FASTQ (no empieza con @): '{filepath}'"
                
        return True, ""
    except gzip.BadGzipFile:
        return False, f"El archivo no es un gzip válido: '{filepath}'"
    except PermissionError:
        return False, f"No hay permisos para leer el archivo: '{filepath}'"
    except Exception as e:
        return False, f"Error al validar el archivo: '{filepath}': {str(e)}"


def main():
    if len(sys.argv) < 6:
        print("Error: faltan argumentos.\nUso:\n  python validate_samples.py samples.csv schema.yaml config.yaml warnings_log.txt samples_info_validated.csv")
        sys.exit(1)

    samples_csv = sys.argv[1]
    schema_yaml = sys.argv[2]
    config_yaml = sys.argv[3]
    warnings_log = sys.argv[4]
    samples_info_validated = sys.argv[5]

    # 1) Leer config.yaml
    with open(config_yaml, "r") as fconf:
        config = yaml.safe_load(fconf)

    mode = config.get("mode", "normal")  # "gva" o "normal"
    # (Supón que tienes un dict de organismos válidos en config, p.ej. config["species"] = [...]
    #  O si es un mapeo, p.ej. config["species"] = {"klebsiella_pneumoniae": {...}, ...}
    valid_species = set()
    if "species" in config and isinstance(config["species"], dict):
        valid_species = set(config["species"].keys())

    # 2) Detectar separador y comillas en samples.csv
    #    csv.Sniffer revisa unas primeras líneas para inferir delimitador y quotechar
    try:
        with open(samples_csv, "r", encoding="utf-8") as f:
            sample_head = f.read(4096)
            dialect = csv.Sniffer().sniff(sample_head, delimiters=";,")
            f.seek(0)
            df = pd.read_csv(f, sep=dialect.delimiter, quotechar=dialect.quotechar, dtype=str)
    except Exception as e:
        print(f"Error al leer {samples_csv}: {e}")
        sys.exit(1)

    # Rellenar NaN con cadenas vacías para evitar float('nan')
    df = df.fillna("")

    # 3) Validar la estructura básica con snakemake.utils.validate
    #    Asume que cada fila del DataFrame se validará según lo descrito en samples.schema.yaml
    try:
        validate(df, schema_yaml)
    except Exception as e:
        print(f"Error de esquema en {samples_csv}:\n{e}")
        sys.exit(1)

    # 4) Realizar validaciones y correcciones
    warnings_list = []   # guardaremos (linea, peticion, mensaje) para cada advertencia
    errors_list = []     # errores graves que causan sys.exit(1) al final

    # Funciones auxiliares
    def log_warning(line_idx, peticion, msg):
        """Registra un warning con info de línea y PETICION (o CODIGO_MUESTRA_ORIGEN)"""
        warnings_list.append((line_idx, peticion, msg))

    def parse_and_normalize_date(dstr):
        """
        Intenta interpretar la fecha (posibles formatos) y devolver en YYYY-MM-DD.
        Retorna (fecha_normalizada, corrected_bool).
        Si no se puede parsear, lanza ValueError.
        """
        dstr = dstr.strip()
        if not dstr:
            raise ValueError("Fecha vacía")

        # Si ya cumple ^\d{4}-\d{2}-\d{2}$ y es válida, no corregimos
        if re.match(r"^\d{4}-\d{2}-\d{2}$", dstr):
            # verificar que sea una fecha real
            yyyy, mm, dd = map(int, dstr.split("-"))
            datetime.date(yyyy, mm, dd)  # lanza error si no es válida
            return dstr, False

        # Si no cumple, probamos distintos formatos
        candidates = [
            ("%d/%m/%y", False),
            ("%d/%m/%Y", False),
            ("%d-%m-%y", False),
            ("%d-%m-%Y", False),
            # etc. puedes añadir más
        ]
        # Vamos probando
        for fmt, year_is_two_digits in candidates:
            try:
                dt = datetime.datetime.strptime(dstr, fmt)
                # Si el formato tenía %y, interpretará 24 como 1924, ojo. 
                # Normalmente strptime con %y asume 19xx/20xx según la librería, 
                # pero se puede forzar por tu cuenta si quieres.
                norm = dt.strftime("%Y-%m-%d")
                return norm, True
            except ValueError:
                pass

        raise ValueError(f"No se pudo interpretar la fecha: '{dstr}'")

    # Recorremos filas y aplicamos validaciones
    for i, row in df.iterrows():
        # Para identificar la muestra, tomamos algo único. 
        # Podrías usar CODIGO_MUESTRA_ORIGEN, PETICION, etc.
        peticion_val = row.get("PETICION", "").strip()
        codigo_muestra_origen = row.get("CODIGO_MUESTRA_ORIGEN", "").strip()
        if not codigo_muestra_origen:
            # Este ya se valida en el schema como required, pero lo chequeamos
            errors_list.append((i+1, peticion_val, "CODIGO_MUESTRA_ORIGEN está vacío."))
            continue

        ### 4a) Normalizar fecha FECHA_TOMA_MUESTRA
        fecha_str = row.get("FECHA_TOMA_MUESTRA", "").strip()
        try:
            normalized_date, corrected = parse_and_normalize_date(fecha_str)
            # Verificar que no sea futura
            y, m, d = map(int, normalized_date.split("-"))
            fdt = datetime.date(y, m, d)
            if fdt > datetime.date.today():
                errors_list.append((i+1, peticion_val, f"Fecha '{fecha_str}' es futura."))
            else:
                # Si corrected, generamos warning
                if corrected and fecha_str != normalized_date:
                    log_warning(i+1, peticion_val, 
                                f"Formato de fecha '{fecha_str}' normalizado a '{normalized_date}'.")
                df.at[i, "FECHA_TOMA_MUESTRA"] = normalized_date
        except ValueError as ve:
            errors_list.append((i+1, peticion_val, f"Fecha inválida '{fecha_str}': {ve}"))

        ### 4b) Organismo (ESPECIE_SECUENCIA) => normalizar a minusculas, guiones bajos
        mo_str = row.get("ESPECIE_SECUENCIA", "").strip()
        if not mo_str:
            # El esquema ya lo requiere. Si está vacío => pondremos 'UNKNOWN'
            mo_str = "UNKNOWN"
            df.at[i, "ESPECIE_SECUENCIA"] = mo_str
        else:
            # Normaliza
            mo_normalized = re.sub(r"\s+", "_", mo_str.strip().lower())
            if mo_normalized != mo_str:
                log_warning(i+1, peticion_val, 
                            f"Organismo '{mo_str}' normalizado a '{mo_normalized}'.")
            df.at[i, "ESPECIE_SECUENCIA"] = mo_normalized
            # Chequeo si está en la lista de config
            if valid_species and mo_normalized not in valid_species:
                log_warning(i+1, peticion_val, 
                            f"Organismo '{mo_str}' / '{mo_normalized}' no está en config.yaml.")

        ### 4c) Modo GVA => PETICION y CARRERA obligatorios, val formato
        if mode == "gva":
            if not peticion_val:
                errors_list.append((i+1, peticion_val, "Modo GVA: Falta PETICION."))
            carrera_val = row.get("CARRERA", "").strip()
            if not carrera_val:
                errors_list.append((i+1, peticion_val, "Modo GVA: Falta CARRERA."))
            else:
                # Validar patrón AAMMDD_HOSPxxx
                # Ej. 240427_CLIN002 => 24 -> 2024, 04 -> abril, 27 -> día
                # etc. Haz la regex a tu gusto
                match = re.match(r"^(\d{6})_([A-Za-z]{4})(\d{3})$", carrera_val)
                if not match:
                    errors_list.append((i+1, peticion_val, 
                        f"CARRERA '{carrera_val}' no cumple formato AAMMDD_HOSPXXX."))
                else:
                    # Podrías verificar que la fecha AAMMDD sea real y no futura, etc.
                    # Opcional.
                    pass
        else:
            # Modo normal => al menos un ID (id, id2) si PETICION no es obligatorio
            _id = row.get("id", "").strip()
            _id2 = row.get("id2", "").strip()
            if not _id and not _id2:
                errors_list.append((i+1, peticion_val, 
                    "Modo normal: Falta al menos uno de id o id2."))

        ### 4d) Validar Illumina => ILLUMINA_R1 y R2
        r1 = row.get("ILLUMINA_R1", "").strip()
        r2 = row.get("ILLUMINA_R2", "").strip()
        if r1 or r2:
            if not (r1 and r2):
                errors_list.append((i+1, peticion_val, 
                    "Tiene uno de ILLUMINA_R1/ILLUMINA_R2 pero no el otro."))
            else:
                # Verificar R1
                valid_r1, error_r1 = is_valid_fastq_gz(r1)
                if not valid_r1:
                    errors_list.append((i+1, peticion_val, f"ILLUMINA_R1: {error_r1}"))
                    
                # Verificar R2
                valid_r2, error_r2 = is_valid_fastq_gz(r2)
                if not valid_r2:
                    errors_list.append((i+1, peticion_val, f"ILLUMINA_R2: {error_r2}"))

        ### 4e) Validar Nanopore => ONT y MODELO_DORADO
        ont = row.get("ONT", "").strip()
        dorado = row.get("MODELO_DORADO", "").strip()
        if ont:
            if not dorado:
                errors_list.append((i+1, peticion_val, 
                    "Se indica ONT pero falta MODELO_DORADO."))
            else:
                # Verificar archivo ONT
                valid_ont, error_ont = is_valid_fastq_gz(ont)
                if not valid_ont:
                    errors_list.append((i+1, peticion_val, f"ONT: {error_ont}"))
                
                # Validación del modelo Dorado
                valid_models = ["dna_r10.4.1_e8.2_400bps_sup@v4.2.0", "dna_r10.4.1_e8.2_400bps_hac@v4.2.0"]
                if dorado not in valid_models:
                    log_warning(i+1, peticion_val, 
                        f"MODELO_DORADO '{dorado}' no está en la lista de modelos conocidos: {', '.join(valid_models)}")
        else:
            if dorado:
                log_warning(i+1, peticion_val, 
                    f"MODELO_DORADO '{dorado}' pero no hay ruta ONT. Podría ser un error.")

    # 5) Reportar resultados
    #    - Warnings => logs/validation_warnings.txt
    #    - Errors => se listan en stderr, luego sys.exit(1)

    # Primero escribimos warnings en el archivo
    os.makedirs(os.path.dirname(warnings_log), exist_ok=True)
    with open(warnings_log, "w", encoding="utf-8") as wlog:
        if not warnings_list:
            wlog.write("No warnings.\n")
        else:
            for (line_no, pet, msg) in warnings_list:
                identificador = pet if pet else f"linea_{line_no}"
                wlog.write(f"Línea {line_no} (PETICION {identificador}): {msg}\n")

    # Si hay errores, los mostramos y salimos con error
    if errors_list:
        print("\n*** ERRORES DE VALIDACIÓN ***\n")
        for (line_no, pet, msg) in errors_list:
            identificador = pet if pet else f"linea_{line_no}"
            print(f"Línea {line_no} (PETICION {identificador}): {msg}")
        sys.exit(1)

    # Luego de validar todo y no tener errores graves, guardamos el CSV corregido y con las columnas renombradas
    # en caso de ser mode gva
    rename_map_gva = {
    "PETICION": "id",
    "CODIGO_MUESTRA_ORIGEN": "id2",
    "FECHA_TOMA_MUESTRA": "collection_date",
    "ESPECIE_SECUENCIA": "organism",
    "MOTIVO_WGS": "relevance",
    "CARRERA": "run_id",
    "ILLUMINA_R1": "illumina_r1",
    "ILLUMINA_R2": "illumina_r2",
    "ONT": "nanopore",
    "MODELO_DORADO": "dorado_model",
    "CONFIRMACION": "confirmation_note",
    "NUM_BROTE": "outbreak_id",
    "COMENTARIO_WGS": "comment"
    }

    # Columnas obligatorias en modo normal
    required_normal = ["id", "collection_date", "organism"]
    # Además, se requiere al menos uno de estos pares: (illumina_r1, illumina_r2) o (nanopore, dorado_model)

    # Luego de validar y antes de renombrar columnas
    if config.get("mode") == "gva":
        # Primero verificamos si existen las columnas que queremos preservar
        # y las creamos si no existen
        for col in ["NUM_BROTE", "CONFIRMACION", "COMENTARIO_WGS"]:
            if col not in df.columns:
                df[col] = ""

        # Elimina columnas 'id' e 'id2' si existen y están completamente vacías
        for col in ["id", "id2"]:
            if col in df.columns and df[col].str.strip().eq("").all():
                df.drop(columns=col, inplace=True)

        # Guardar todas las columnas no mapeadas para preservarlas
        extra_columns = {col: col for col in df.columns if col not in rename_map_gva.keys() and col not in rename_map_gva.values()}
        
        # Renombra desde PETICION y CODIGO_MUESTRA_ORIGEN
        df.rename(columns=rename_map_gva, inplace=True)
        
    else:
        # En modo normal, no se renombran PETICION y CODIGO_MUESTRA_ORIGEN, solo se validan
        pass
   
    df.to_csv(samples_info_validated, sep=';', index=False)

    # Si llegamos aquí sin errores, todo OK
    print(f"Validación de {samples_csv} completada sin errores graves. "\
          f"Revisa {warnings_log} para ver posibles advertencias.")
    sys.exit(0)


if __name__ == "__main__":
    main()
