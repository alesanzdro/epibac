#!/usr/bin/env python3
import os
import sys
import pandas as pd
import shutil
import subprocess
import hashlib
import glob
import yaml
from pathlib import Path


def create_directory(path):
    """Crear directorio si no existe."""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        print(f"Error al crear directorio {path}: {e}", file=sys.stderr)
        return False


def calculate_md5(filepath):
    """Calcular hash MD5 de un archivo."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def generate_md5_file(directory, output_file):
    """Genera archivo de checksums MD5 para todos los archivos en directory."""
    checksums = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file == os.path.basename(output_file):
                continue
            filepath = os.path.join(root, file)
            try:
                md5 = calculate_md5(filepath)
                rel_path = os.path.relpath(filepath, directory)
                checksums.append(f"{md5}  {rel_path}")
            except Exception as e:
                print(f"Error calculando MD5 para {filepath}: {e}", file=sys.stderr)

    with open(output_file, "w") as f:
        f.write("\n".join(checksums))


def rsync_copy(source, destination):
    """Ejecutar rsync para copiar archivos."""
    try:
        cmd = [
            "rsync",
            "-avh",
            "--progress",
            "--partial",
            "--checksum",
            f"{source}/",
            f"{destination}/",
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.SubprocessError as e:
        return False, f"Error con rsync: {e}"


def find_fastq_files(sample_id, outdir, fastq_info):
    """Busca los archivos FASTQ de una muestra basado en la información del informe."""
    fastq_files = {}

    # Inicializar listas para los archivos
    for key in ["R1", "R2", "NANOPORE"]:
        fastq_files[key] = []

    # Buscar en las ubicaciones típicas de archivos FASTQ
    search_dirs = [
        f"{outdir}/qc/fastp",
        f"{outdir}/reads",
        # Añade aquí más directorios donde puedan estar los FASTQ
    ]

    # Si tenemos información específica de los archivos en el informe GESTLAB
    if isinstance(fastq_info, dict):
        # Si hay información de archivos específicos, buscar esos archivos
        for key, value in fastq_info.items():
            if pd.notna(value) and value:
                basename = os.path.basename(value)

                # Buscar el archivo en los directorios de búsqueda
                for directory in search_dirs:
                    if not os.path.exists(directory):
                        continue

                    # Buscar archivos que coincidan con el patrón
                    matches = glob.glob(f"{directory}/**/{basename}", recursive=True)
                    if matches:
                        # Clasificar según el tipo
                        if key == "ILLUMINA_R1":
                            fastq_files["R1"].extend(matches)
                        elif key == "ILLUMINA_R2":
                            fastq_files["R2"].extend(matches)
                        elif key == "NANOPORE":
                            fastq_files["NANOPORE"].extend(matches)
    else:
        # Búsqueda genérica por ID de muestra si no tenemos información específica
        for directory in search_dirs:
            if not os.path.exists(directory):
                continue

            all_files = glob.glob(f"{directory}/{sample_id}*.fastq.gz") + glob.glob(
                f"{directory}/{sample_id}*.fq.gz"
            )

            for file in all_files:
                basename = os.path.basename(file)
                if "_R1" in basename or "_1." in basename:
                    fastq_files["R1"].append(file)
                elif "_R2" in basename or "_2." in basename:
                    fastq_files["R2"].append(file)
                else:
                    # Asumimos que es ONT si no es claramente R1/R2
                    fastq_files["NANOPORE"].append(file)

    return fastq_files


def extract_hospital_from_carrera(carrera):
    """Extrae el código de hospital del nombre de carrera (ej. 240512_CLIN002 -> CLIN)."""
    parts = carrera.split("_")
    if len(parts) < 2:
        return None

    # El hospital es el segundo elemento, primeros 4 caracteres
    hosp = parts[1][:4]
    return hosp


def determine_seq_method(row):
    """Determina el método de secuenciación basado en las columnas del informe GESTLAB."""
    # Primero intentamos usar la columna OBS_MET_WGS si existe
    if "OBS_MET_WGS" in row and pd.notna(row["OBS_MET_WGS"]):
        return row["OBS_MET_WGS"]

    # Si no, determinamos basándonos en los archivos
    has_illumina = (
        "ILLUMINA_R1" in row
        and pd.notna(row["ILLUMINA_R1"])
        and row["ILLUMINA_R1"] != ""
    ) or (
        "ILLUMINA_R2" in row
        and pd.notna(row["ILLUMINA_R2"])
        and row["ILLUMINA_R2"] != ""
    )
    has_nanopore = "NANOPORE" in row and pd.notna(row["NANOPORE"]) and row["NANOPORE"] != ""

    if has_illumina and has_nanopore:
        return "HYBRID"
    elif has_illumina:
        return "ILLUMINA"
    elif has_nanopore:
        return "NANOPORE"
    else:
        return None


def main():
    # Verificar argumentos
    if len(sys.argv) != 7:
        print(
            f"Uso: {sys.argv[0]} gestlab_report report_tsv report_xlsx output_log outdir tag_run",
            file=sys.stderr,
        )
        sys.exit(1)

    gestlab_report = sys.argv[1]
    report_tsv = sys.argv[2]
    report_xlsx = sys.argv[3]
    output_log = sys.argv[4]
    outdir = sys.argv[5]
    tag_run = sys.argv[6]  # Ahora recibimos TAG_RUN directamente

    # Cargar el archivo de configuración para obtener storage_cabinet y mode
    config_file = "config.yaml"
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        # Obtener el modo de análisis
        mode = config.get("epibac_mode", "normal")

        # Obtener storage_cabinet solo si estamos en modo gva
        storage_cabinet = None
        if mode == "gva":
            storage_cabinet = (
                config.get("mode_config", {}).get("gva", {}).get("storage_cabinet", "")
            )
            # Verificar si storage_cabinet existe
            if storage_cabinet and not os.path.exists(storage_cabinet):
                print(
                    f"Advertencia: El directorio storage_cabinet '{storage_cabinet}' no existe",
                    file=sys.stderr,
                )
                print(
                    f"Los archivos se dejarán en la carpeta temporal: {os.path.join(outdir, tag_run)}",
                    file=sys.stderr,
                )
                storage_cabinet = None
    except Exception as e:
        print(f"Error cargando configuración: {e}", file=sys.stderr)
        storage_cabinet = None

    # Cargar datos del informe GESTLAB
    try:
        df_gestlab = pd.read_csv(gestlab_report, sep=";")
    except Exception as e:
        print(f"Error cargando informe GESTLAB: {e}", file=sys.stderr)
        sys.exit(1)

    log_entries = []

    # Identificar la columna de ID primario según el modo
    id_col = None
    if mode == "gva":
        id_col = (
            config.get("params", {})
            .get("mode_config", {})
            .get("gva", {})
            .get("primary_id_column", "id2")
        )
    else:
        id_col = (
            config.get("params", {})
            .get("mode_config", {})
            .get("normal", {})
            .get("primary_id_column", "id")
        )

    # Verificar que la columna ID exista en el informe
    if id_col not in df_gestlab.columns:
        print(
            f"Error: Columna {id_col} no encontrada en el informe GESTLAB",
            file=sys.stderr,
        )
        # Buscar alternativas
        alt_cols = [
            col
            for col in df_gestlab.columns
            if col.lower() in ["id", "id2", "codigo_muestra", "codigo_muestra_origen"]
        ]
        if alt_cols:
            id_col = alt_cols[0]
            print(f"Usando columna alternativa: {id_col}", file=sys.stderr)
        else:
            sys.exit(1)

    # Determinar el método de secuenciación para cada muestra si no está definido
    if "OBS_MET_WGS" not in df_gestlab.columns:
        df_gestlab["OBS_MET_WGS"] = df_gestlab.apply(determine_seq_method, axis=1)

    # Extraer el hospital del nombre de carrera (tag_run)
    hosp = extract_hospital_from_carrera(tag_run)
    if not hosp and mode == "gva":
        log_entries.append(
            f"Error: No se pudo extraer código de hospital del tag_run {tag_run}"
        )

    # Crear directorio temporal para la carrera
    carrera_dir = os.path.join(outdir, tag_run)
    if not create_directory(carrera_dir):
        log_entries.append(f"Error: No se pudo crear directorio {carrera_dir}")
        sys.exit(1)

    # Crear directorio para FASTQ
    fastq_dir = os.path.join(carrera_dir, "fastq")
    if not create_directory(fastq_dir):
        log_entries.append(f"Error: No se pudo crear directorio de FASTQ {fastq_dir}")
        sys.exit(1)

    # Copiar informes con nuevos nombres
    try:
        shutil.copy2(
            gestlab_report, os.path.join(carrera_dir, f"{tag_run}_EPIBAC_GESTLAB.csv")
        )
        shutil.copy2(report_tsv, os.path.join(carrera_dir, f"{tag_run}_EPIBAC.tsv"))
        shutil.copy2(report_xlsx, os.path.join(carrera_dir, f"{tag_run}_EPIBAC.xlsx"))
        log_entries.append(f"Informes copiados correctamente para carrera {tag_run}")
    except Exception as e:
        log_entries.append(f"Error copiando informes para carrera {tag_run}: {e}")
        sys.exit(1)

    # Determinar qué tipos de secuenciación tiene esta carrera
    has_illumina = False
    has_nanopore = False

    # Para cada muestra
    for _, row in df_gestlab.iterrows():
        sample_id = row[id_col]
        seq_method = row["OBS_MET_WGS"] if pd.notna(row["OBS_MET_WGS"]) else "UNKNOWN"

        if seq_method == "UNKNOWN":
            log_entries.append(
                f"Omitiendo muestra {sample_id}: método de secuenciación desconocido"
            )
            continue

        # Actualizar flags según el método de secuenciación
        if seq_method in ["ILLUMINA", "HYBRID"]:
            has_illumina = True
        if seq_method in ["NANOPORE", "HYBRID"]:
            has_nanopore = True

        # Construir información de archivos FASTQ para esta muestra
        fastq_info = {
            "ILLUMINA_R1": row.get("ILLUMINA_R1", None),
            "ILLUMINA_R2": row.get("ILLUMINA_R2", None),
            "NANOPORE": row.get("NANOPORE", None),
        }

        # Localizar y copiar archivos FASTQ
        fastq_files = find_fastq_files(sample_id, outdir, fastq_info)

        # Copiar todos los archivos FASTQ a la carpeta fastq
        files_copied = False
        for key, files in fastq_files.items():
            for file in files:
                if os.path.exists(file):
                    try:
                        dest = os.path.join(fastq_dir, os.path.basename(file))
                        shutil.copy2(file, dest)
                        files_copied = True
                        log_entries.append(f"Copiado {file} a {dest}")
                    except Exception as e:
                        log_entries.append(
                            f"Error copiando {file} para muestra {sample_id}: {e}"
                        )

        if not files_copied:
            log_entries.append(
                f"No se encontraron archivos FASTQ para la muestra {sample_id}"
            )

    # Generar checksums MD5 para todos los archivos
    md5_file = os.path.join(carrera_dir, f"{tag_run}_checksum.md5")
    generate_md5_file(carrera_dir, md5_file)

    # Si estamos en modo GVA y tenemos storage_cabinet, intentar copiar a la cabina
    if mode == "gva" and storage_cabinet and hosp:
        # Intentar copiar según tipo de secuenciación
        if has_illumina:
            dest_path = f"{storage_cabinet}/deposit/CVA_{hosp}/illumina/{tag_run}"
            if not create_directory(dest_path):
                log_entries.append(
                    f"Error: No se pudo crear directorio destino Illumina {dest_path}"
                )
            else:
                # Ejecutar rsync para copiar al destino final
                success, message = rsync_copy(carrera_dir, dest_path)
                if success:
                    log_entries.append(
                        f"Éxito: Archivos copiados correctamente a {dest_path}"
                    )
                else:
                    log_entries.append(f"Error copiando archivos: {message}")

        if has_nanopore:
            dest_path = f"{storage_cabinet}/deposit/CVA_{hosp}/nanopore/{tag_run}"
            if not create_directory(dest_path):
                log_entries.append(
                    f"Error: No se pudo crear directorio destino Nanopore {dest_path}"
                )
            else:
                # Ejecutar rsync para copiar al destino final
                success, message = rsync_copy(carrera_dir, dest_path)
                if success:
                    log_entries.append(
                        f"Éxito: Archivos copiados correctamente a {dest_path}"
                    )
                else:
                    log_entries.append(f"Error copiando archivos: {message}")
    else:
        log_entries.append(f"Archivos resultantes disponibles en: {carrera_dir}")
        if mode == "gva":
            if not hosp:
                log_entries.append("No se pudo extraer código de hospital del tag_run.")
            if not storage_cabinet:
                log_entries.append(
                    "No se ha configurado o no existe storage_cabinet en config.yaml."
                )

    # Escribir log
    with open(output_log, "w") as f:
        for entry in log_entries:
            f.write(f"{entry}\n")


if __name__ == "__main__":
    main()
