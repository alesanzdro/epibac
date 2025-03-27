import pandas as pd
import os
from snakemake.utils import validate
from snakemake.utils import min_version
from datetime import datetime

min_version("9.1.1")

configfile: "config.yaml"
validate(config, schema="schemas/config.schema.yaml")

OUTDIR = config["outdir"]
LOGDIR = config["logdir"]

rule validate_samples:
    """
    Valida y corrige samples_info.csv generando un archivo corregido y warnings
    """
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
        python scripts/validate_samples.py \
            {input.samples} \
            {input.schema} \
            {input.config} \
            {output.warnings} \
            {output.corrected_samples}
        """

# Cargar directamente el archivo validado
validated_samples = pd.read_csv(f"{OUTDIR}/samples_info_validated.csv", sep=";", dtype=str).set_index("PETICION", drop=False)

#samples = pd.read_csv(config["samples"], sep="\t", dtype=str).set_index("sample", drop=False)
#samples.index = samples.index.astype(str)


include: "rules/common.smk"
include: "rules/setup.smk"
include: "rules/qc.smk"
include: "rules/assembly.smk"
include: "rules/annotation.smk"
include: "rules/amr_mlst.smk"
include: "rules/report.smk"

rule all:
    input:
        f"{LOGDIR}/validation_warnings.txt",
        f"{OUTDIR}/samples_info_validated.csv",
        f"{OUTDIR}/qc/multiqc.html",
        f"{OUTDIR}/report/{datetime.now().strftime('%y%m%d')}_EPIBAC.tsv"