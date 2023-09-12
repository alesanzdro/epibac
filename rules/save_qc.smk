import glob
import os
def get_filtered_samples():
    validated_samples = [f.split('/')[-1].split('.')[0] for f in glob.glob("out/validated/*.validated")]
    return validated_samples


rule epibac_fastqc_raw:
    input:
        lambda wc: samples.loc[(wc.sample)]['fq' + wc.read]
    output:
        html="{}/qc/fastqc_raw/{{sample}}_r{{read}}_fastqc.html".format(OUTDIR),
        zip="{}/qc/fastqc_raw/{{sample}}_r{{read}}_fastqc.zip".format(OUTDIR)
    threads: get_resource("fastqc","threads")
    resources:
        mem_mb=get_resource("fastqc","mem"),
        walltime=get_resource("fastqc","walltime")
    params: 
        lambda wc: "-t {}".format(get_resource("fastqc","threads"))
    log:
        "{}/fastqc_raw/{{sample}}_r{{read}}.log".format(LOGDIR)
    benchmark:
        "{}/fastqc_raw/{{sample}}_r{{read}}.bmk".format(LOGDIR)
    wrapper:
        "v2.6.0/bio/fastqc"

checkpoint epibac_fastp_pe:
    input:
        r1 = lambda wc: samples.loc[wc.sample, 'fq1'],
        r2 = lambda wc: samples.loc[wc.sample, 'fq2']
    output:
        html="{}/qc/fastp/{{sample}}_fastp.html".format(OUTDIR),
	    json="{}/qc/fastp/{{sample}}_fastp.json".format(OUTDIR),
	    r1="{}/trimmed/{{sample}}_r1.fastq.gz".format(OUTDIR),
	    r2="{}/trimmed/{{sample}}_r2.fastq.gz".format(OUTDIR)
    params:
        extra=""
    log:
        f"{LOGDIR}/fastp/{{sample}}.log"
    conda:
        '../envs/epibac.yml'
    threads: get_resource("fastp","threads")
    resources:
        mem_mb = get_resource("fastp","mem"),
        walltime = get_resource("fastp","walltime")
    shell:
        """
        fastp \
        --thread {threads} \
        --in1 {input.r1} \
        --in2 {input.r2}  \
        {config[params][fastp][extra]} \
        --json {output.json} \
        --html {output.html} \
        --out1 {output.r1} \
        --out2 {output.r2} \
        &> {log}
        """

checkpoint validate_reads:
    input:
        lambda wildcards: f"{OUTDIR}/trimmed/{wildcards.sample}_r1.fastq.gz"
    output:
        directory("{}/validated/{{sample}}".format(OUTDIR))
    shell:
        """
        read_count=$(zcat {input} | wc -l)
        if (( read_count / 4 > 1000 )); then
            touch {output}
        fi
        """

def get_file_names(wildcards, dir="qc/fastqc_trim", extension="fastq.gz"):
    sample = wildcards['sample']
    ck_output = checkpoints.validate_reads.get(sample=sample).output[0]
    SMP, = glob_wildcards(os.path.join(ck_output, "{sample}"))
    return [f"{OUTDIR}/{dir}/{sample}_r{read}.{extension}" for sample in SMP for read in ['r1', 'r2']]



#def get_file_names(wildcards):
#    ck_output = checkpoints.validate_reads.get(**wildcards).output[0]
#    samples, = glob_wildcards(os.path.join(ck_output, "{sample}"))
#    return [f"{OUTDIR}/trimmed/{sample}_r{wildcards.read}.fastq.gz" for sample in samples]




#def get_file_names(wildcards, dir="qc/fastqc_trim", extension="fastq.gz"):
#    ck_output = checkpoints.validate_reads.get(**wildcards).output[0]
#    validated_samples = [os.path.basename(fname) for fname in glob.glob(f"{ck_output}/*")]
#    return [f"{OUTDIR}/{dir}/{sample}_r{read}.{extension}" for sample in validated_samples for read in ['r1', 'r2']]




rule epibac_fastqc_trim:
    input:
        lambda wc: get_file_names(wc, dir="trimmed", extension="fastq.gz") if wc.sample in get_filtered_samples() else []
    output:
        html="{}/qc/fastqc_trim/{{sample}}_r{{read}}_fastqc.html".format(OUTDIR),
        zip="{}/qc/fastqc_trim/{{sample}}_r{{read}}_fastqc.zip".format(OUTDIR)
    threads: get_resource("fastqc","threads")
    resources:
        mem_mb=get_resource("fastqc","mem"),
        walltime=get_resource("fastqc","walltime")
    params:
        lambda wc: "-t {}".format(get_resource("fastqc","threads"))
    log:
        "{}/fastqc_trim/{{sample}}_r{{read}}.log".format(LOGDIR)
    benchmark:
        "{}/fastqc_trim/{{sample}}_r{{read}}.bmk".format(LOGDIR)
    wrapper:
        "v2.6.0/bio/fastqc"

rule multiqc:
    input:
        [expand(f"{OUTDIR}/qc/fastqc_raw/{row.sample}_{{r}}_fastqc.zip", r=["r1","r2"]) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")],
        [expand(f"{OUTDIR}/qc/fastp/{row.sample}_fastp.html") for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")],
        lambda wc: get_file_names(wc, dir="qc/fastqc_trim", extension="fastq.gz")
        
        #[expand(f"{OUTDIR}/qc/fastqc_trim/{sample}_{{r}}_fastqc.html", r=["r1","r2"]) for sample in get_filtered_samples()]
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



rule epibac_kraken2:
    input:
        setup_db = f"{LOGDIR}/setup/setup_kraken2_db.flag",
        r1 = lambda wc: f"{OUTDIR}/trimmed/{sample}_r1.fastq.gz" if wc.sample in get_filtered_samples() else [],
        r2 = lambda wc: f"{OUTDIR}/trimmed/{sample}_r2.fastq.gz" if wc.sample in get_filtered_samples() else []
    output:
        "{}/qc/kraken2/{{sample}}_CR_1.fastq".format(OUTDIR),
        "{}/qc/kraken2/{{sample}}_CR_2.fastq".format(OUTDIR),
        report="{}/qc/kraken2/{{sample}}.txt".format(OUTDIR)
    params:
        report_dir=directory("{}/qc/kraken2".format(OUTDIR)),
        classified_out="{}/qc/kraken2/{{sample}}_CR#.fastq".format(OUTDIR)
    log:
        f"{LOGDIR}/kraken2/{{sample}}.log"
    conda:
        '../envs/epibac.yml'
    threads: get_resource("kraken2","threads")
    resources:
        mem_mb = get_resource("kraken2","mem"),
        walltime = get_resource("kraken2","walltime")
    shell:
        """
        # Averigua la ruta del ambiente conda activo
        CONDA_PREFIX=${{CONDA_PREFIX}}

        kraken2 \
        --threads {threads} \
        --db $CONDA_PREFIX/db/kraken2_minusb \
        --gzip-compressed \
        --paired {input.r1} {input.r2} \
        --output {params.report_dir} \
        --report {output.report} \
        --classified-out {params.classified_out} \
        --use-names #&> {log}
        """

rule epibac_quast:
    input:
        lambda wc: f"{OUTDIR}/assembly/{wc.sample}/{wc.sample}.fasta" if wc.sample in get_filtered_samples() else []
    output:
        directory("{}/qc/quast/{{sample}}".format(OUTDIR))
    params:
        l=lambda wc: f"{wc.sample}" 
    log:
        f"{LOGDIR}/quast/{{sample}}.log"
    conda:
        '../envs/epibac.yml'
    threads: get_resource("quast","threads")
    resources:
        mem_mb = get_resource("quast","mem"),
        walltime = get_resource("quast","walltime")
    shell:
        """
        quast -t {threads} \
        {input} \
        -l {params.l} \
        --glimmer \
        -o {output} \
        &> {log}
        """


