import pandas as pd
import os
from snakemake.utils import validate
from snakemake.utils import min_version
from datetime import datetime

min_version("7.32")

#singularity: "docker://continuumio/miniconda3:4.6.14"

#report: "report/workflow.rst"

###### Config file and sample sheets #####
configfile: "config.yaml"
#validate(config, schema="schemas/config.schema.yaml")

# snakemake --use-conda -j 20 --dry-run --dag | dot -Tpng > dag.png

OUTDIR = config["outdir"]
LOGDIR = config["logdir"]

#samples = pd.read_csv(config["samples"],sep="\t").set_index("sample", drop=False)
#validate(samples, schema="schemas/samples.schema.yaml")

samples = pd.read_csv(config["samples"], sep="\t", dtype=str).set_index("sample", drop=False)
samples.index = samples.index.astype(str)

# Code for when we have a column named UNIT, for when we need to merge samples (from big samplesheet file)
#samples = pd.read_csv(config["samples"],sep="\t", dtype=str).set_index(["sample", "unit"], drop=False)
#samples.index = samples.index.set_levels([i.astype(str) for i in samples.index.levels])  # enforce str in index
#validate(units, schema="schemas/units.schema.yaml")


include: "rules/common.smk"
##### Modules #####include: "rules/setup.smk"

##### Target rules #####
rule all:
    input:
        f"{OUTDIR}/qc/multiqc.html",
        f"{OUTDIR}/report/{datetime.now().strftime('%y%m%d')}_EPIBAC.tsv"
   

include: "rules/setup.smk"
include: "rules/qc.smk"
include: "rules/assembly.smk"
include: "rules/annotation.smk"
include: "rules/amr_mlst.smk"
include: "rules/report.smk"