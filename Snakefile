import pandas as pd
import os
from snakemake.utils import validate
from snakemake.utils import min_version
min_version("7.32")

#singularity: "docker://continuumio/miniconda3:4.6.14"

#report: "report/workflow.rst"

###### Config file and sample sheets #####
configfile: "config.yaml"
#validate(config, schema="schemas/config.schema.yaml")


##### Helper functions #####

def get_resource(rule,resource):
    try:
        return config["resources"][rule][resource]
    except KeyError:
        return config["resources"]["default"][resource]

def get_fastq(wildcards):
    """Get fastq files of given sample-unit."""
    fastqs = samples.loc[(wildcards.sample), ["fq1", "fq2"]].dropna()
    if len(fastqs) == 2:
        return {"r1": fastqs.fq1, "r2": fastqs.fq2}
    return {"r1": fastqs.fq1}

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


##### Wildcard constraints #####
wildcard_constraints:
    sample="|".join(samples["sample"])


#include: "rules/common.smk"

##### Target rules #####

rule all:
    input:
        [expand(f"{OUTDIR}/qc/fastqc_trim/{row.sample}_{{r}}_fastqc.zip", r=["r1","r2"]) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")],
	    f"{OUTDIR}/qc/multiqc.html"

##### Modules #####

include: "rules/setup.smk"
include: "rules/qc.smk"
include: "rules/assembly.smk"
include: "rules/annotation.smk"
include: "rules/amr_mlst.smk"
