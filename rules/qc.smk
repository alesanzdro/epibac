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
	    json="{}/qc/fastp/{{sample}}_fastp.son".format(OUTDIR),
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

checkpoint epibac_fastp_pe_count:
    input:
        r1=lambda wc: f"{OUTDIR}/trimmed/{wc.sample}_r1.fastq.gz",
        r2=lambda wc: f"{OUTDIR}/trimmed/{wc.sample}_r2.fastq.gz"
    output:
        nreads="{}/qc/count_reads/{{sample}}_counts.txt".format(OUTDIR)
    log:
        f"{LOGDIR}/count_reads/{{sample}}.log"
    conda:
        '../envs/epibac.yml'
    threads: get_resource("read_count","threads")
    resources:
        mem_mb = get_resource("read_count","mem"),
        walltime = get_resource("read_count","walltime")
    shell:
        """
        if [ ! -f {input.r1} ]; then
            read_count_r1=0
        else
            read_count_r1=$(zcat {input.r1} | wc -l)
        fi
        
        if [ ! -f {input.r2} ]; then
            read_count_r2=0
        else
            read_count_r2=$(zcat {input.r2} | wc -l)
        fi

        total_read_count=$(( (read_count_r1 + read_count_r2) / 4 ))
        echo $total_read_count > {output.nreads}  
        &> {log}
        """

checkpoint validate_reads:
    input:
        r1=lambda wc: f"{OUTDIR}/trimmed/{wc.sample}_r1.fastq.gz",
        r2=lambda wc: f"{OUTDIR}/trimmed/{wc.sample}_r2.fastq.gz"
    output:
        validated="out/validated/{sample}.validated"
    run:
        import subprocess
        cmd = f"zcat {input.r1} | wc -l"
        result = subprocess.run(cmd, shell=True, capture_output=True)
        read_count = int(result.stdout.decode())/4
        if read_count > 1000:
            open(output.validated, "w").close()


rule epibac_fastqc_trim:
    input:
        lambda wc: f"{OUTDIR}/trimmed/{wc.sample}_r{wc.read}.fastq.gz" 
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


rule epibac_kraken2:
    input:
        setup_db = f"{LOGDIR}/setup/setup_kraken2_db.flag",
        r1 = rules.epibac_fastp_pe.output.r1,
        r2 = rules.epibac_fastp_pe.output.r2
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
        "{}/assembly/{{sample}}/{{sample}}.fasta".format(OUTDIR)
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
        # Verifica si el archivo FASTA es vacío o no
        if [ ! -s {input} ]; then
            echo "[ERROR] El archivo FASTA {input} está vacío" &> {log}
            mkdir -p {output}
            exit 0
        fi

        quast -t {threads} \
        {input} \
        -l {params.l} \
        --glimmer \
        -o {output} \
        &> {log}
        """


rule multiqc:
    input:
        [expand(f"{OUTDIR}/qc/fastqc_raw/{row.sample}_{{r}}_fastqc.zip", r=["r1","r2"]) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")],
        #["{OUTDIR}/qc/count_reads/{sample}_counts.txt".format(OUTDIR=OUTDIR,sample=getattr(row, 'sample')) for row in samples.itertuples()],
        [expand(f"{OUTDIR}/qc/fastqc_trim/{row.sample}_{{r}}_fastqc.zip", r=["r1","r2"], allow_missing=True) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")],
        [expand(f"{OUTDIR}/qc/kraken2/{row.sample}.txt", allow_missing=True) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")],
        [expand(f"{OUTDIR}/qc/quast/{row.sample}", allow_missing=True) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")],
        [expand(f"{OUTDIR}/annotation/{row.sample}", allow_missing=True) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")],
        #[expand(f"{OUTDIR}/amr_mlst/{row.sample}_amrfinder.tsv", allow_missing=True) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")],
        #[expand(f"{OUTDIR}/amr_mlst/{row.sample}_mlst.tsv", allow_missing=True) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")],
        #[expand(f"{OUTDIR}/amr_mlst/resfinder/{row.sample}/ResFinder_results.txt", allow_missing=True) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")]
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
