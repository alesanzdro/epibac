import pandas as pd
import os
from snakemake.utils import validate, min_version
from datetime import datetime

DATE = datetime.now().strftime("%y%m%d")

min_version("9.1.1")

configfile: "config.yaml"
validate(config, schema="schemas/config.schema.yaml")

OUTDIR = config["outdir"]
LOGDIR = config["logdir"]

rule validate_samples:
    input:
        samples=config["samples"],
        schema="schemas/samples.schema.yaml",
        config="config.yaml"
    output:
        warnings=f"{LOGDIR}/validation_warnings.txt",
        corrected_samples=f"{OUTDIR}/samples_info_validated.csv"
    conda:
        'envs/epibac.yml'
    shell:
        """
        python scripts/validate_samples_info.py \
            {input.samples} \
            {input.schema} \
            {input.config} \
            {output.warnings} \
            {output.corrected_samples}
        """

# Función para obtener las muestras validadas, evaluada solo después de ejecutar validate_samples
def get_samples():
    samples_csv = f"{OUTDIR}/samples_info_validated.csv"
    if os.path.exists(samples_csv):
        return pd.read_csv(samples_csv, sep=";", dtype=str).set_index(config.get("primary_id_column", "id"), drop=False)
    else:
        raise FileNotFoundError("El fichero validado aún no existe. Ejecuta validate_samples primero.")

include: "rules/common.smk"
include: "rules/setup.smk"
include: "rules/qc.smk"
include: "rules/assembly.smk"
include: "rules/annotation.smk"
include: "rules/amr_mlst.smk"
include: "rules/report.smk"

rule all:
    input:
        rules.validate_samples.output,
        f"{OUTDIR}/qc/multiqc.html",
        # Reporte resumen final (TSV y XLSX con fecha)
        f"{OUTDIR}/report/{DATE}_EPIBAC.tsv",
        f"{OUTDIR}/report/{DATE}_EPIBAC.xlsx",
        f"{OUTDIR}/report/{DATE}_EPIBAC_GESTLAB.csv"

