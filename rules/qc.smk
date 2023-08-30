rule fastqc:
    input:
        lambda wc: samples.loc[(wc.sample)]['fq' + wc.read]
    output:
        html="{}/qc/fastqc/{{sample}}_r{{read}}_fastqc.html".format(OUTDIR),
        zip="{}/qc/fastqc/{{sample}}_r{{read}}_fastqc.zip".format(OUTDIR)
    threads: get_resource("fastqc","threads")
    resources:
        mem_mb=get_resource("fastqc","mem"),
        walltime=get_resource("fastqc","walltime")
    params: 
        lambda wc: "-t {}".format(get_resource("fastqc","threads"))
    log:
        "{}/fastqc/{{sample}}_r{{read}}.log".format(LOGDIR)
    benchmark:
        "{}/fastqc/{{sample}}_r{{read}}.bmk".format(LOGDIR)
    wrapper:
        "v2.6.0/bio/fastqc"

rule multiqc:
    input:
         [expand(f"{OUTDIR}/qc/fastqc/{row.sample}_{{r}}_fastqc.zip", r=["r1"]) for row in samples.itertuples() if (str(getattr(row, 'fq2')) == "nan")],
         [expand(f"{OUTDIR}/qc/fastqc/{row.sample}_{{r}}_fastqc.zip", r=["r1","r2"]) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")],
    output:
        f"{OUTDIR}/qc/multiqc.html"
    log:
        f"{LOGDIR}/multiqc.log"
    threads: get_resource("multiqc","threads")
    resources:
        mem_mb = get_resource("multiqc","mem"),
        walltime = get_resource("multiqc","walltime")
    wrapper:
        "v2.6.0/bio/multiqc"
