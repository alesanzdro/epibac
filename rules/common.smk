import glob
import re

# Columna utilizada como identificador principal ("id" o "id2")
use_column = config.get("primary_id_column", "id")  # valor por defecto "id"

# Cargar muestras validadas desde archivo validado
samples = pd.read_csv(f"{OUTDIR}/samples_info_validated.csv", sep=";", dtype=str).set_index(primary_id_column, drop=False)

##### Wildcard constraints #####
wildcard_constraints:
    sample="|".join(samples.index)

##### Helper functions #####

def get_resource(rule, resource):
    try:
        return config["resources"][rule][resource]
    except KeyError:
        return config["resources"]["default"][resource]


def sanitize_id(x):
    """
    Reemplaza espacios, puntos, comas o guiones por subguiones.
    Así 'PC185-DE0028' -> 'PC185_DE0028', 'PF019 3FAH1' -> 'PF019_3FAH1', etc.
    """
    return re.sub(r"[ .,-]", "_", str(x))


def get_fastq(wildcards):
    """Obtener archivos fastq para una muestra dada."""
    fastqs = samples.loc[wildcards.sample, ["illumina_r1", "illumina_r2"]].dropna()
    if pd.notnull(fastqs["illumina_r1"]) and pd.notnull(fastqs["illumina_r2"]):
        return {"r1": fastqs.illumina_r1, "r2": fastqs.illumina_r2}
    elif pd.notnull(fastqs["illumina_r1"]):
        return {"r1": fastqs.illumina_r1}
    else:
        raise ValueError(f"No se encontraron archivos FASTQ válidos para {wildcards.sample}")


def get_filtered_samples():
    validated_samples = [f.split('/')[-1].split('.')[0] for f in glob.glob(f"{OUTDIR}/validated/*.validated")]
    return validated_samples