import glob
import re
import pandas as pd
import os
from datetime import datetime

# =================== CONSTANTES Y VARIABLES GLOBALES =================== #

# Fecha actual para reportes
DATE = datetime.now().strftime("%y%m%d")

# =================== OPCIONES DE CONFIGURACIÓN =================== #

# Procesar opciones de línea de comandos
def process_cli_args():
    """Procesa los argumentos de línea de comandos y actualiza la configuración."""
    import sys
    
    # Detectar skip_prokka
    if "--skip_prokka" in sys.argv:
        if "skip" not in config:
            config["skip"] = {}
        config["skip"]["prokka"] = True
        sys.argv.remove("--skip_prokka")

# Ejecutar procesamiento de argumentos
process_cli_args()

def should_skip(component):
    """
    Verifica si un componente debe ser omitido según la configuración.
    
    Args:
        component: Nombre del componente a verificar (ej. "prokka")
        
    Returns:
        bool: True si se debe omitir, False en caso contrario
    """
    # Primero verifica el formato antiguo para compatibilidad
    if f"skip_{component}" in config:
        return config[f"skip_{component}"]
    # Luego verifica el nuevo formato
    return config.get("skip", {}).get(component, False)

# =================== CONFIGURACIÓN DE BASES DE DATOS =================== #

# ----- KRAKEN2 -----
KRAKEN_DB_URL = config["params"]["kraken2"]["db_url"]
KRAKEN_DB_NAME = os.path.basename(KRAKEN_DB_URL).replace(".tar.gz", "")
KRAKEN_DB_DIR = f"{REFDIR}/databases/kraken2/{KRAKEN_DB_NAME}"
KRAKEN_DB_FLAG = f"{KRAKEN_DB_DIR}/.installed.flag"
KRAKEN_DB_LOG = f"{REFDIR}/databases/log/{KRAKEN_DB_NAME}.log"

# ----- AMRFINDER -----
AMRFINDER_DB_DIR = f"{REFDIR}/databases/amrfinder"
AMRFINDER_DB_FLAG = f"{AMRFINDER_DB_DIR}/.installed.flag"
AMRFINDER_DB_LOG = f"{REFDIR}/databases/log/amrfinder.log"

# ----- RESFINDER -----
RESFINDER_DB_DIR = f"{REFDIR}/databases/resfinder"
RESFINDER_DB_FLAG = f"{REFDIR}/databases/resfinder/.installed.flag"
RESFINDER_DB_LOG = f"{REFDIR}/databases/log/resfinder.log"

# ----- PROKKA -----
PROKKA_DB_DIR = f"{REFDIR}/databases/prokka"
PROKKA_DB_FLAG = f"{PROKKA_DB_DIR}/.installed.flag"
PROKKA_DB_LOG = f"{REFDIR}/databases/log/prokka.log"

# =================== FUNCIONES DE ACCESO A DATOS DE MUESTRAS =================== #

def get_samples_safe():
    """
    Obtiene el DataFrame de muestras de forma segura, sin lanzar errores si el archivo no existe.
    
    Returns:
        DataFrame: DataFrame con información de las muestras o vacío si no existe.
    """
    samples_csv = f"{OUTDIR}/samples_info_validated.csv"
    if os.path.exists(samples_csv):
        use_column = config.get("primary_id_column", "id")
        return pd.read_csv(samples_csv, sep=";", dtype=str).set_index(use_column, drop=False)
    else:
        return pd.DataFrame()  # Devuelve vacío, evita romper el flujo

def get_samples():
    """
    Obtiene el DataFrame de muestras. Lanza error si el archivo no existe.
    
    Returns:
        DataFrame: DataFrame con información de las muestras.
    
    Raises:
        FileNotFoundError: Si el archivo de muestras validadas no existe.
    """
    samples_csv = f"{OUTDIR}/samples_info_validated.csv"
    if os.path.exists(samples_csv):
        use_column = config.get("primary_id_column", "id")
        return pd.read_csv(samples_csv, sep=";", dtype=str).set_index(use_column, drop=False)
    else:
        raise FileNotFoundError(f"El fichero validado '{samples_csv}' aún no existe. Ejecuta primero la regla 'validate_samples'.")

def get_sample_index_if_exists():
    """
    Obtiene la lista de IDs de muestras si el archivo existe.
    
    Returns:
        list: Lista de IDs o lista vacía si el archivo no existe.
    """
    samples_csv = f"{OUTDIR}/samples_info_validated.csv"
    if os.path.exists(samples_csv):
        use_column = config.get("primary_id_column", "id")
        df = pd.read_csv(samples_csv, sep=";", dtype=str)
        return df[use_column].tolist()
    else:
        return []

def get_fastq(wildcards):
    """
    Obtiene las rutas de los archivos FASTQ para una muestra.
    
    Args:
        wildcards: Wildcards de Snakemake con el nombre de la muestra.
        
    Returns:
        dict: Diccionario con rutas de los archivos R1 y R2.
        
    Raises:
        ValueError: Si no se encuentran archivos FASTQ válidos.
    """
    samples = get_samples()
    fastqs = samples.loc[wildcards.sample, ["illumina_r1", "illumina_r2"]]
    if pd.notnull(fastqs["illumina_r1"]) and pd.notnull(fastqs["illumina_r2"]):
        return {"r1": fastqs["illumina_r1"], "r2": fastqs["illumina_r2"]}
    elif pd.notnull(fastqs["illumina_r1"]):
        return {"r1": fastqs["illumina_r1"]}
    else:
        raise ValueError(f"No se encontraron archivos FASTQ válidos para {wildcards.sample}")

def get_filtered_samples():
    """
    Obtiene muestras que tienen archivos de validación.
    
    Returns:
        list: Lista de nombres de muestras validadas.
    """
    validated_samples = [
        f.split('/')[-1].split('.')[0] for f in glob.glob(f"{OUTDIR}/validated/*.validated")
    ]
    return validated_samples

# =================== UTILIDADES GENERALES =================== #

def get_resource(rule, resource):
    """
    Obtiene un recurso para una regla específica, con fallback a los valores por defecto.
    
    Args:
        rule: Nombre de la regla.
        resource: Tipo de recurso (threads, mem, walltime).
        
    Returns:
        Valor del recurso.
    """
    try:
        return config["resources"][rule][resource]
    except KeyError:
        return config["resources"]["default"][resource]

def sanitize_id(x):
    """
    Limpia un ID para ser utilizado como wildcard.
    
    Args:
        x: ID a limpiar.
        
    Returns:
        str: ID limpio.
    """
    return re.sub(r"[ .,-]", "_", str(x))

def get_all_inputs():
    """
    Genera la lista de archivos de salida para la regla 'all'.
    
    Returns:
        list: Lista de archivos esperados por la regla all.
    """
    inputs = [
        f"{OUTDIR}/samples_info_validated.csv",
        f"{OUTDIR}/qc/multiqc.html",
        f"{OUTDIR}/report/{TAG_RUN}_EPIBAC.tsv",
        f"{OUTDIR}/report/{TAG_RUN}_EPIBAC.xlsx",
    ]
    
    # Si no estamos omitiendo Prokka, añadimos su metadata
    if not should_skip("prokka"):
        inputs.append(f"{REFDIR}/databases/prokka/VERSION.txt")
    
    # Si estamos en modo GVA, añadimos también el reporte para GESTLAB
    if config.get("epibac_mode") == "gva":
        inputs.append(f"{OUTDIR}/report/{TAG_RUN}_EPIBAC_GESTLAB.csv"),
        inputs.append(f"{OUTDIR}/report/{TAG_RUN}_file_copy_log.txt")
    
    return inputs

# Wildcard constraints
wildcard_constraints:
    sample="[^/]+"
