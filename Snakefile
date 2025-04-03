import pandas as pd
import os
import sys
import re
from datetime import datetime
from snakemake.utils import validate, min_version

min_version("9.1.1")

configfile: "config.yaml"
validate(config, schema="schemas/config.schema.yaml")

# Definir variables globales básicas
OUTDIR = config["outdir"]
LOGDIR = config["logdir"]

# Obtener fecha actual en formato YYMMDD para usar como TAG_RUN por defecto
DEFAULT_DATE = datetime.now().strftime("%y%m%d")

# Definir TAG_RUN basado en config o usar fecha actual como fallback
if "params" in config and "run_name" in config["params"]:
    TAG_RUN = config["params"]["run_name"]
else:
    TAG_RUN = DEFAULT_DATE

# Obtener modo de análisis
mode = config.get("epibac_mode", "normal")

# Verificar si el formato del run_name es válido para modo GVA
if mode == "gva":
    run_pattern = re.compile(r"^\d{6}_[A-Z]{4}\d{3}$")
    if not run_pattern.match(TAG_RUN):
        sys.exit(f"Error: En modo GVA, run_name debe seguir el formato AAMMDD_HOSPXXX. Valor actual: {TAG_RUN}")

# Definir REFDIR basado en la nueva ubicación en config
REFDIR = config["params"]["refdir"]

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