import glob
import re
import pandas as pd
import os

# Variables BASES DE DATOS centralizas en carpeta resources
KRAKEN_DB_URL = config.get("kraken2_db_url")
KRAKEN_DB_NAME = os.path.basename(KRAKEN_DB_URL).replace(".tar.gz", "")
KRAKEN_DB_DIR = f"resources/databases/kraken2/{KRAKEN_DB_NAME}"
KRAKEN_DB_FLAG = f"{KRAKEN_DB_DIR}/.installed.flag"
KRAKEN_DB_LOG = f"resources/databases/log/{KRAKEN_DB_NAME}.log"

# Función robusta para obtener el índice de muestras si el archivo validado ya existe
def get_sample_index_if_exists():
    samples_csv = f"{config['outdir']}/samples_info_validated.csv"
    if os.path.exists(samples_csv):
        use_column = config.get("primary_id_column", "id")
        df = pd.read_csv(samples_csv, sep=";", dtype=str)
        return df[use_column].tolist()
    else:
        return []

# Función robusta para obtener el DataFrame completo de muestras si ya existe
# Evita error si se evalúa antes de que se genere el CSV validado
def get_samples_safe():
    samples_csv = f"{config['outdir']}/samples_info_validated.csv"
    if os.path.exists(samples_csv):
        use_column = config.get("primary_id_column", "id")
        return pd.read_csv(samples_csv, sep=";", dtype=str).set_index(use_column, drop=False)
    else:
        return pd.DataFrame()  # Devuelve vacío, evita romper el flujo de Snakemake

# Versión estricta que sí lanza error si el archivo aún no existe
def get_samples():
    samples_csv = f"{config['outdir']}/samples_info_validated.csv"
    if os.path.exists(samples_csv):
        use_column = config.get("primary_id_column", "id")
        return pd.read_csv(samples_csv, sep=";", dtype=str).set_index(use_column, drop=False)
    else:
        raise FileNotFoundError(f"El fichero validado '{samples_csv}' aún no existe. Ejecuta primero la regla 'validate_samples'.")

# Wildcard genérico, no usa función todavía
wildcard_constraints:
    sample="[^/]+"

# Recursos por defecto por regla
def get_resource(rule, resource):
    try:
        return config["resources"][rule][resource]
    except KeyError:
        return config["resources"]["default"][resource]

# Limpieza de IDs para wildcards
def sanitize_id(x):
    return re.sub(r"[ .,-]", "_", str(x))

# Obtener rutas de FASTQ para una muestra específica
def get_fastq(wildcards):
    samples = get_samples()
    fastqs = samples.loc[wildcards.sample, ["illumina_r1", "illumina_r2"]]
    if pd.notnull(fastqs["illumina_r1"]) and pd.notnull(fastqs["illumina_r2"]):
        return {"r1": fastqs["illumina_r1"], "r2": fastqs["illumina_r2"]}
    elif pd.notnull(fastqs["illumina_r1"]):
        return {"r1": fastqs["illumina_r1"]}
    else:
        raise ValueError(f"No se encontraron archivos FASTQ válidos para {wildcards.sample}")

# Extraer muestras validadas por fichero de flag opcional (no siempre usado)
def get_filtered_samples():
    validated_samples = [
        f.split('/')[-1].split('.')[0] for f in glob.glob(f"{config['outdir']}/validated/*.validated")
    ]
    return validated_samples
