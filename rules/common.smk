import glob
import re
import pandas as pd

use_column = config.get("primary_id_column", "id")

def get_samples():
    samples_csv = f"{config['outdir']}/samples_info_validated.csv"
    if os.path.exists(samples_csv):
        return pd.read_csv(samples_csv, sep=";", dtype=str).set_index(use_column, drop=False)
    else:
        raise FileNotFoundError(
            f"El fichero validado '{samples_csv}' aún no existe. Ejecuta primero la regla 'validate_samples'.")

# Wildcard genérico, no usa función todavía
wildcard_constraints:
    sample="[^/]+"

# Resto igual
def get_resource(rule, resource):
    try:
        return config["resources"][rule][resource]
    except KeyError:
        return config["resources"]["default"][resource]

def sanitize_id(x):
    return re.sub(r"[ .,-]", "_", str(x))

def get_fastq(wildcards):
    samples = get_samples()
    fastqs = samples.loc[wildcards.sample, ["illumina_r1", "illumina_r2"]]
    if pd.notnull(fastqs["illumina_r1"]) and pd.notnull(fastqs["illumina_r2"]):
        return {"r1": fastqs["illumina_r1"], "r2": fastqs["illumina_r2"]}
    elif pd.notnull(fastqs["illumina_r1"]):
        return {"r1": fastqs["illumina_r1"]}
    else:
        raise ValueError(f"No se encontraron archivos FASTQ válidos para {wildcards.sample}")

def get_filtered_samples():
    validated_samples = [
        f.split('/')[-1].split('.')[0] for f in glob.glob(f"{config['outdir']}/validated/*.validated")
    ]
    return validated_samples