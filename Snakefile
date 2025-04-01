import pandas as pd
import os
import sys
from snakemake.utils import validate, min_version

min_version("9.1.1")

configfile: "config.yaml"
validate(config, schema="schemas/config.schema.yaml")

# Definir variables globales básicas
OUTDIR = config["outdir"]
LOGDIR = config["logdir"]
REFDIR = config["refdir"]

# Importar módulos (common.smk primero para tener disponibles sus funciones)
include: "rules/common.smk"
include: "rules/setup.smk"
include: "rules/qc.smk"
include: "rules/assembly.smk"
include: "rules/annotation.smk"
include: "rules/amr_mlst.smk"
include: "rules/report.smk"

# Regla de validación (primera regla para que se ejecute por defecto)
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

# Regla principal
rule all:
    input: get_all_inputs()