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
        'envs/epibac_qc.yml'
    container: 
        "docker://alesanzdro/epibac_qc:1.0"
    shell:
        """
        python scripts/validate_samples_info.py \
            {input.samples} \
            {input.schema} \
            {input.config} \
            {output.warnings} \
            {output.corrected_samples}
        """

include: "rules/common.smk"
include: "rules/setup.smk"
include: "rules/qc.smk"
include: "rules/assembly.smk"
include: "rules/annotation.smk"
include: "rules/amr_mlst.smk"
include: "rules/report.smk"

# Construimos la lista de inputs esperados para la regla all
inputs_all = [
    rules.validate_samples.output,
    f"{OUTDIR}/qc/multiqc.html",
    f"{OUTDIR}/report/{DATE}_EPIBAC.tsv",
    f"{OUTDIR}/report/{DATE}_EPIBAC.xlsx",
]

# Si estamos en modo GVA, añadimos también el reporte para GESTLAB
if config.get("mode") == "gva":
    inputs_all.append(f"{OUTDIR}/report/{DATE}_EPIBAC_GESTLAB.csv")

# Definimos la regla all con esa lista dinámica
rule all:
    input: inputs_all