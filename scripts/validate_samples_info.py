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
   - Modo normal => al menos uno de id o id2 (o si usas CODIGO_ORIGEN/PETICION, etc.).
   - Illumina => si ILLUMINA_R1 está, ILLUMINA_R2 también y viceversa.
   - ONT => si ONT está, MODELO_DORADO también.
   - Normaliza MO (minusculas, guiones bajos), avisa si no existe en config.yaml.
5. Registra advertencias/correcciones en un log. Si hay errores graves, sale con exit code 1.
"""

import sys
import os
import csv
import yaml
import re
import datetime
from snakemake.utils import validate
import pandas as pd

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
        """Registra un warning con info de línea y PETICION (o CODIGO_ORIGEN)"""
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
        # Podrías usar CODIGO_ORIGEN, PETICION, etc.
        peticion_val = row.get("PETICION", "").strip()
        codigo_origen = row.get("CODIGO_ORIGEN", "").strip()
        if not codigo_origen:
            # Este ya se valida en el schema como required, pero lo chequeamos
            errors_list.append((i+1, peticion_val, "CODIGO_ORIGEN está vacío."))
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

        ### 4b) Organismo (MO) => normalizar a minusculas, guiones bajos
        mo_str = row.get("MO", "").strip()
        if not mo_str:
            # El esquema ya lo requiere. Si está vacío => pondremos 'UNKNOWN'
            mo_str = "UNKNOWN"
            df.at[i, "MO"] = mo_str
        else:
            # Normaliza
            mo_normalized = re.sub(r"\s+", "_", mo_str.strip().lower())
            if mo_normalized != mo_str:
                log_warning(i+1, peticion_val, 
                            f"Organismo '{mo_str}' normalizado a '{mo_normalized}'.")
            df.at[i, "MO"] = mo_normalized
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
                # Chequeo de existencia de archivos (opcional)
                # if not os.path.exists(r1):
                #     errors_list.append((i+1, peticion_val, f"No existe el archivo '{r1}'."))
                # if not os.path.exists(r2):
                #     errors_list.append((i+1, peticion_val, f"No existe el archivo '{r2}'."))
                pass

        ### 4e) Validar Nanopore => ONT y MODELO_DORADO
        ont = row.get("ONT", "").strip()
        dorado = row.get("MODELO_DORADO", "").strip()
        if ont:
            if not dorado:
                errors_list.append((i+1, peticion_val, 
                    "Se indica ONT pero falta MODELO_DORADO."))
            else:
                # if not os.path.exists(ont):
                #     errors_list.append((i+1, peticion_val, f"No existe el archivo ONT '{ont}'."))
                # validación extra de dorado si tienes lista
                pass
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
    "CODIGO_ORIGEN": "id2",
    "FECHA_TOMA_MUESTRA": "collection_date",
    "MO": "organism",
    "MOTIVO_WGS": "relevance",
    "CARRERA": "run_id",
    "ILLUMINA_R1": "illumina_r1",
    "ILLUMINA_R2": "illumina_r2",
    "ONT": "nanopore",
    "MODELO_DORADO": "dorado_model"
    }


    # Luego de validar y antes de renombrar columnas
    if config.get("mode") == "gva":
        # Elimina columnas 'id' e 'id2' si existen y están completamente vacías
        for col in ["id", "id2"]:
            if col in df.columns and df[col].str.strip().eq("").all():
                df.drop(columns=col, inplace=True)

        # Renombra desde PETICION y CODIGO_ORIGEN
        df.rename(columns=rename_map_gva, inplace=True)
    else:
        # En modo normal, no se renombran PETICION y CODIGO_ORIGEN, solo se validan
        pass
   
    df.to_csv(samples_info_validated, sep=';', index=False)

    # Si llegamos aquí sin errores, todo OK
    print(f"Validación de {samples_csv} completada sin errores graves. "\
          f"Revisa {warnings_log} para ver posibles advertencias.")
    sys.exit(0)


if __name__ == "__main__":
    main()
