#!/usr/bin/env python3
import os
import sys
import pandas as pd
import shutil
import subprocess
import hashlib
import glob
import yaml
import argparse
import time
from pathlib import Path

# Definir parser de argumentos
def parse_args():
    parser = argparse.ArgumentParser(description="Copiar archivos de secuenciación")
    parser.add_argument("gestlab_report", help="Informe en formato GESTLAB")
    parser.add_argument("report_tsv", help="Informe en formato TSV")
    parser.add_argument("report_xlsx", help="Informe en formato XLSX")
    parser.add_argument("output_log", help="Archivo de log de salida")
    parser.add_argument("outdir", help="Directorio de salida")
    parser.add_argument("tag_run", help="Tag de la carrera")
    parser.add_argument("--config-file", help="Ruta al archivo de configuración")
    return parser.parse_args()
# En el script de copia:
def create_directory_structure(dest_path):
    """Crea la estructura de directorios si no existe"""
    # Asegurar que usamos forward slash
    dest_path = dest_path.replace('\\', '/')
    
    # Extraer el directorio base (sin el nombre del archivo)
    if dest_path.endswith('.gz') or dest_path.endswith('.fastq'):
        dest_dir = os.path.dirname(dest_path)
    else:
        dest_dir = dest_path
    
    # Crear estructura de directorios
    os.makedirs(dest_dir, exist_ok=True)
    print(f"Creado directorio: {dest_dir}")
    
    return dest_path


def create_destination_structure(base_path, platform, tag_run):
    """
    Crea la estructura completa de directorios para el destino.
    
    Args:
        base_path: Ruta base (storage_cabinet)
        platform: Plataforma (illumina o nanopore)
        tag_run: Tag de la carrera
        
    Returns:
        tuple: (éxito, ruta_completa, mensaje)
    """
    try:
        # Extraer hospital del tag_run
        hosp = extract_hospital_from_carrera(tag_run)
        if not hosp:
            return False, "", f"No se pudo extraer código de hospital del tag_run {tag_run}"
        
        # Construir la estructura completa
        platform_dir = f"{base_path}/CVA_{hosp}/{platform}"
        run_dir = f"{platform_dir}/{tag_run}"
        fastq_dir = f"{run_dir}/fastq"
        
        # Crear directorios en orden
        os.makedirs(platform_dir, exist_ok=True)
        os.makedirs(run_dir, exist_ok=True)
        os.makedirs(fastq_dir, exist_ok=True)
        
        print(f"Creada estructura de directorios: {fastq_dir}")
        return True, fastq_dir, "Estructura creada correctamente"
        
    except Exception as e:
        return False, "", f"Error al crear estructura de directorios: {e}"

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


def rsync_copy(source, destination, max_attempts=3):
    """Ejecutar rsync para copiar archivos con reintentos."""
    attempt = 0
    while attempt < max_attempts:
        try:
            attempt += 1
            cmd = [
                "rsync",
                "-ah",
                "--partial",
                "--checksum",
                f"{source}/",
                f"{destination}/",
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True, result.stdout
        except subprocess.SubprocessError as e:
            if attempt < max_attempts:
                # Espera exponencial entre reintentos
                wait_time = 2 ** attempt
                print(f"Error en intento {attempt}. Reintentando en {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                return False, f"Error con rsync después de {max_attempts} intentos: {e}"

def find_fastq_files(sample_id, outdir, fastq_info):
    """Busca los archivos FASTQ de una muestra usando las rutas directas del informe."""
    fastq_files = {"R1": [], "R2": [], "NANOPORE": []}
    
    # USAR DIRECTAMENTE LAS RUTAS ESPECIFICADAS EN EL INFORME GESTLAB
    if isinstance(fastq_info, dict):
        # Verificar si el archivo existe en la ruta especificada
        if "ILLUMINA_R1" in fastq_info and pd.notna(fastq_info["ILLUMINA_R1"]):
            r1_path = fastq_info["ILLUMINA_R1"]
            print(f"Comprobando existencia de R1: {r1_path}")
            if os.path.isfile(r1_path):
                print(f"Encontrado R1: {r1_path}")
                fastq_files["R1"].append(r1_path)
            else:
                print(f"No se encontró R1: {r1_path}")
        
        if "ILLUMINA_R2" in fastq_info and pd.notna(fastq_info["ILLUMINA_R2"]):
            r2_path = fastq_info["ILLUMINA_R2"]
            print(f"Comprobando existencia de R2: {r2_path}")
            if os.path.isfile(r2_path):
                print(f"Encontrado R2: {r2_path}")
                fastq_files["R2"].append(r2_path)
            else:
                print(f"No se encontró R2: {r2_path}")
            
        if "NANOPORE" in fastq_info and pd.notna(fastq_info["NANOPORE"]):
            nanopore_path = fastq_info["NANOPORE"]
            print(f"Comprobando existencia de Nanopore: {nanopore_path}")
            if os.path.isfile(nanopore_path):
                print(f"Encontrado Nanopore: {nanopore_path}")
                fastq_files["NANOPORE"].append(nanopore_path)
            else:
                print(f"No se encontró Nanopore: {nanopore_path}")
    
    # Imprimir un resumen para debugging
    print(f"Archivos encontrados para {sample_id}: R1={len(fastq_files['R1'])}, R2={len(fastq_files['R2'])}, Nanopore={len(fastq_files['NANOPORE'])}")
    
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
    args = parse_args()
    
    gestlab_report = args.gestlab_report
    report_tsv = args.report_tsv
    report_xlsx = args.report_xlsx
    output_log = args.output_log
    outdir = args.outdir
    tag_run = args.tag_run
    
    # Cargar el archivo de configuración para obtener storage_cabinet y mode
    if args.config_file and os.path.exists(args.config_file):
        config_file = args.config_file
    else:
        # Fallback a la ruta relativa
        script_path = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_path)))
        config_file = os.path.join(project_root, "config.yaml")
    
    log_entries = []
    
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        # Obtener el modo de análisis
        mode = config.get("mode", "normal")  # Corregido: "mode" en lugar de "epibac_mode"

        # Obtener storage_cabinet solo si estamos en modo gva
        storage_cabinet = None
        if mode == "gva":
            storage_cabinet = (
                config.get("mode_config", {}).get("gva", {}).get("storage_cabinet", "")
            )
            # Verificar y crear storage_cabinet si no existe
            if storage_cabinet:
                if not os.path.exists(storage_cabinet):
                    try:
                        os.makedirs(storage_cabinet, exist_ok=True)
                        log_entries.append(f"* Creado directorio storage_cabinet: {storage_cabinet}")
                    except Exception as e:
                        log_entries.append(f"* Error al crear storage_cabinet: {e}")
                        storage_cabinet = None
                        log_entries.append(f"* Los archivos se dejarán en la carpeta temporal: {os.path.join(outdir, tag_run)}")
            else:
                log_entries.append("* No se ha configurado storage_cabinet en config.yaml")
    except Exception as e:
        log_entries.append(f"* Error cargando configuración: {e}")
        storage_cabinet = None

    # Cargar datos del informe GESTLAB
    try:
        df_gestlab = pd.read_csv(gestlab_report, sep=";")
    except Exception as e:
        log_entries.append(f"* Error cargando informe GESTLAB: {e}")
        sys.exit(1)

    # Identificar la columna de ID primario según el modo
    id_col = None
    if mode == "gva":
        id_col = (
            config.get("mode_config", {})
            .get("gva", {})
            .get("primary_id_column", "CODIGO_MUESTRA_ORIGEN")
        )
    else:
        id_col = (
            config.get("mode_config", {})
            .get("normal", {})
            .get("primary_id_column", "id")
        )

    # Verificar que la columna ID exista en el informe
    if id_col not in df_gestlab.columns:
        log_entries.append(f"* Error: Columna {id_col} no encontrada en el informe GESTLAB")
        # Buscar alternativas
        alt_cols = [
            col
            for col in df_gestlab.columns
            if col.lower() in ["id", "id2", "codigo_muestra_origen"]
        ]
        if alt_cols:
            id_col = alt_cols[0]
            log_entries.append(f"* Usando columna alternativa: {id_col}")
        else:
            sys.exit(1)

    # Determinar el método de secuenciación para cada muestra si no está definido
    if "OBS_MET_WGS" not in df_gestlab.columns:
        df_gestlab["OBS_MET_WGS"] = df_gestlab.apply(determine_seq_method, axis=1)

    # Extraer el hospital del nombre de carrera (tag_run)
    hosp = extract_hospital_from_carrera(tag_run)
    if not hosp and mode == "gva":
        log_entries.append(f"* Error: No se pudo extraer código de hospital del tag_run {tag_run}")

    # Crear directorio temporal para la carrera
    carrera_dir = os.path.join(outdir, tag_run)
    carrera_dir = create_directory_structure(carrera_dir)
    if not os.path.exists(carrera_dir):
        log_entries.append(f"* Error: No se pudo crear directorio {carrera_dir}")
        sys.exit(1)

    # Crear directorio para FASTQ
    fastq_dir = os.path.join(carrera_dir, "fastq")
    fastq_dir = create_directory_structure(fastq_dir)
    if not os.path.exists(fastq_dir):
        log_entries.append(f"* Error: No se pudo crear directorio de FASTQ {fastq_dir}")
        sys.exit(1)

    # Copiar informes con nuevos nombres
    try:
        shutil.copy2(
            gestlab_report, os.path.join(carrera_dir, f"{tag_run}_EPIBAC_GESTLAB.csv")
        )
        shutil.copy2(report_tsv, os.path.join(carrera_dir, f"{tag_run}_EPIBAC.tsv"))
        shutil.copy2(report_xlsx, os.path.join(carrera_dir, f"{tag_run}_EPIBAC.xlsx"))
        log_entries.append(f"* Informes copiados correctamente para carrera {tag_run}")
    except Exception as e:
        log_entries.append(f"* Error copiando informes para carrera {tag_run}: {e}")
        sys.exit(1)

    # Determinar qué tipos de secuenciación tiene esta carrera
    has_illumina = False
    has_nanopore = False

    # Para cada muestra
    for _, row in df_gestlab.iterrows():
        sample_id = row[id_col]
        seq_method = row["OBS_MET_WGS"] if pd.notna(row["OBS_MET_WGS"]) else "UNKNOWN"

        if seq_method == "UNKNOWN":
            log_entries.append(f"* Omitiendo muestra {sample_id}: método de secuenciación desconocido")
            continue

        # Actualizar flags según el método de secuenciación
        if seq_method in ["ILLUMINA", "HYBRID"]:
            has_illumina = True
        if seq_method in ["NANOPORE", "HYBRID"]:
            has_nanopore = True

        # Obtener rutas directamente del informe GESTLAB
        fastq_info = {
            "ILLUMINA_R1": row.get("ILLUMINA_R1", None),
            "ILLUMINA_R2": row.get("ILLUMINA_R2", None),
            "NANOPORE": row.get("NANOPORE", None),
        }

        # Debug de rutas
        for key, path in fastq_info.items():
            if pd.notna(path) and path:
                log_entries.append(f"DEBUG: {sample_id} - {key}: {path}")

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
                        log_entries.append(f"- Copiado {file} a {dest}")
                    except Exception as e:
                        log_entries.append(f"- Error copiando {file} para muestra {sample_id}: {e}")

        if not files_copied:
            log_entries.append(f"* No se encontraron archivos FASTQ para la muestra {sample_id}")

    # Generar checksums MD5 para todos los archivos
    md5_file = os.path.join(carrera_dir, f"{tag_run}_checksum.md5")
    generate_md5_file(carrera_dir, md5_file)

    # Si estamos en modo GVA y tenemos storage_cabinet, intentar copiar a la cabina
    copy_success = False
    if mode == "gva" and storage_cabinet and hosp:
        log_entries.append(f"* Intentando copiar archivos a storage_cabinet: {storage_cabinet}")
        
        # 1. Primero, crear una carpeta para informes (sin FASTQ)
        reports_dir = os.path.join(carrera_dir, "reports_only")
        os.makedirs(reports_dir, exist_ok=True)
        
        # Copiar solo los informes y resultados (excluyendo fastq/)
        for item in os.listdir(carrera_dir):
            if item != "fastq" and item != "reports_only":
                src = os.path.join(carrera_dir, item)
                dst = os.path.join(reports_dir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                elif os.path.isdir(src):
                    shutil.copytree(src, dst)
        
        # 2. Copiar a las ubicaciones específicas
        # Para Illumina
        illumina_success = False
        if has_illumina:
            illumina_dest = f"{storage_cabinet}/CVA_{hosp}/illumina/{tag_run}"
            log_entries.append(f"* Creando ruta para Illumina: {illumina_dest}")
            
            try:
                # Crear directorio de destino
                os.makedirs(illumina_dest, exist_ok=True)
                
                # A. Copiar informes
                success_reports, message = rsync_copy(reports_dir, illumina_dest)
                if not success_reports:
                    log_entries.append(f"* Error copiando informes a Illumina: {message}")
                
                # B. Crear directorio para FASTQ
                illumina_fastq_dest = f"{illumina_dest}/fastq"
                os.makedirs(illumina_fastq_dest, exist_ok=True)
                
                # C. Identificar y copiar solo FASTQ de Illumina
                success_fastq = False
                illumina_files = []
                for _, row in df_gestlab.iterrows():
                    if pd.notna(row.get("ILLUMINA_R1")):
                        illumina_files.append(os.path.basename(row["ILLUMINA_R1"]))
                    if pd.notna(row.get("ILLUMINA_R2")):
                        illumina_files.append(os.path.basename(row["ILLUMINA_R2"]))
                
                fastq_src = os.path.join(carrera_dir, "fastq")
                for fastq_file in illumina_files:
                    src = os.path.join(fastq_src, fastq_file)
                    if os.path.exists(src):
                        dst = os.path.join(illumina_fastq_dest, fastq_file)
                        try:
                            shutil.copy2(src, dst)
                            success_fastq = True
                            log_entries.append(f"- Copiado FASTQ Illumina: {fastq_file}")
                        except Exception as e:
                            log_entries.append(f"- Error copiando FASTQ Illumina {fastq_file}: {e}")
                
                # Si no hay archivos para copiar, consideramos que es exitoso
                illumina_success = success_reports and (success_fastq or len(illumina_files) == 0)
                if illumina_success:
                    log_entries.append(f"* Éxito: Archivos Illumina copiados correctamente")
                    copy_success = True
                
            except Exception as e:
                log_entries.append(f"* Error al crear/copiar archivos Illumina: {e}")
        
        # Para Nanopore
        nanopore_success = False
        if has_nanopore:
            nanopore_dest = f"{storage_cabinet}/CVA_{hosp}/nanopore/{tag_run}"
            log_entries.append(f"* Creando ruta para Nanopore: {nanopore_dest}")
            
            try:
                # Crear directorio de destino
                os.makedirs(nanopore_dest, exist_ok=True)
                
                # A. Copiar informes
                success_reports, message = rsync_copy(reports_dir, nanopore_dest)
                if not success_reports:
                    log_entries.append(f"* Error copiando informes a Nanopore: {message}")
                
                # B. Crear directorio para FASTQ
                nanopore_fastq_dest = f"{nanopore_dest}/fastq"
                os.makedirs(nanopore_fastq_dest, exist_ok=True)
                
                # C. Identificar y copiar solo FASTQ de Nanopore
                success_fastq = False
                nanopore_files = []
                for _, row in df_gestlab.iterrows():
                    if pd.notna(row.get("NANOPORE")):
                        nanopore_files.append(os.path.basename(row["NANOPORE"]))
                
                fastq_src = os.path.join(carrera_dir, "fastq")
                for fastq_file in nanopore_files:
                    src = os.path.join(fastq_src, fastq_file)
                    if os.path.exists(src):
                        dst = os.path.join(nanopore_fastq_dest, fastq_file)
                        try:
                            shutil.copy2(src, dst)
                            success_fastq = True
                            log_entries.append(f"- Copiado FASTQ Nanopore: {fastq_file}")
                        except Exception as e:
                            log_entries.append(f"- Error copiando FASTQ Nanopore {fastq_file}: {e}")
                
                # Si no hay archivos para copiar, consideramos que es exitoso
                nanopore_success = success_reports and (success_fastq or len(nanopore_files) == 0)
                if nanopore_success:
                    log_entries.append(f"* Éxito: Archivos Nanopore copiados correctamente")
                    copy_success = True
                
            except Exception as e:
                log_entries.append(f"* Error al crear/copiar archivos Nanopore: {e}")
        
        # Considerar copia exitosa si al menos una plataforma se copió correctamente
        copy_success = illumina_success or nanopore_success
    
    # Informar sobre la ubicación final de los archivos
    if copy_success:
        log_entries.append(f"* Archivos copiados con éxito a la cabina")
        
        # Verificar que la carpeta temporal existe antes de intentar eliminarla
        if os.path.exists(carrera_dir):
            try:
                # Opcional: verificar que todos los archivos importantes fueron copiados
                # antes de eliminar (puedes añadir esta lógica si lo deseas)
                
                # Eliminar la carpeta temporal y su contenido
                shutil.rmtree(carrera_dir)
                log_entries.append(f"* Carpeta temporal eliminada: {carrera_dir}")
            except Exception as e:
                log_entries.append(f"* Error al eliminar carpeta temporal: {e}")
                log_entries.append(f"* Los archivos siguen disponibles en: {carrera_dir}")
        else:
            log_entries.append(f"* Carpeta temporal no encontrada: {carrera_dir}")
    else:
        log_entries.append(f"* La copia a la cabina no se realizó correctamente.")
        log_entries.append(f"* Archivos resultantes disponibles en: {carrera_dir}")
        if mode == "gva":
            if not hosp:
                log_entries.append("* No se pudo extraer código de hospital del tag_run.")
            if not storage_cabinet:
                log_entries.append("* No se ha configurado o no existe storage_cabinet en config.yaml.")

    # Escribir log
    with open(output_log, "w") as f:
        for entry in log_entries:
            f.write(f"{entry}\n")


if __name__ == "__main__":
    main()