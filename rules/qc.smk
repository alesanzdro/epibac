rule epibac_fastqc_raw:
    input:
        lambda wc: get_fastq(wc)['r' + wc.read]
    output:
        html=f"{OUTDIR}/qc/fastqc_raw/{{sample}}_r{{read}}_fastqc.html",
        zip=f"{OUTDIR}/qc/fastqc_raw/{{sample}}_r{{read}}_fastqc.zip"
    threads: get_resource("fastqc","threads")
    resources:
        mem_mb=get_resource("fastqc","mem"),
        walltime=get_resource("fastqc","walltime")
    log:
        f"{LOGDIR}/fastqc_raw/{{sample}}_r{{read}}.log"
    benchmark:
        f"{LOGDIR}/fastqc_raw/{{sample}}_r{{read}}.bmk"
    wrapper:
        "v2.6.0/bio/fastqc"

checkpoint epibac_fastp_pe:
    input:
        lambda wc: get_fastq(wc)['r1'],
        lambda wc: get_fastq(wc)['r2']
    output:
        html=f"{OUTDIR}/qc/fastp/{{sample}}_fastp.html",
        json=f"{OUTDIR}/qc/fastp/{{sample}}_fastp.json",
        r1=f"{OUTDIR}/trimmed/{{sample}}_r1.fastq.gz",
        r2=f"{OUTDIR}/trimmed/{{sample}}_r2.fastq.gz"
    params:
        extra=config["params"]["fastp"]["extra"]
    log:
        f"{LOGDIR}/fastp/{{sample}}.log"
    conda:
        '../envs/epibac_qc.yml'
    threads: get_resource("fastp","threads")
    resources:
        mem_mb=get_resource("fastp","mem"),
        walltime=get_resource("fastp","walltime")
    shell:
        """
        fastp \
        --thread {threads} \
        --in1 {input[0]} \
        --in2 {input[1]} \
        {params.extra} \
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
        '../envs/epibac_qc.yml'
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
        r1=f"{OUTDIR}/trimmed/{{sample}}_r1.fastq.gz",
        r2=f"{OUTDIR}/trimmed/{{sample}}_r2.fastq.gz"
    output:
        validated=f"{OUTDIR}/validated/{{sample}}.validated"
    run:
        cmd = f"zcat {input.r1} | wc -l"
        result = subprocess.run(cmd, shell=True, capture_output=True)
        read_count = int(result.stdout.decode()) / 4
        if read_count > 1000:
            open(output.validated, "w").close()


rule epibac_fastqc_trim:
    input:
        lambda wc: f"{OUTDIR}/trimmed/{wc.sample}_r{wc.read}.fastq.gz"
    output:
        html=f"{OUTDIR}/qc/fastqc_trim/{{sample}}_r{{read}}_fastqc.html",
        zip=f"{OUTDIR}/qc/fastqc_trim/{{sample}}_r{{read}}_fastqc.zip"
    threads: get_resource("fastqc","threads")
    resources:
        mem_mb=get_resource("fastqc","mem"),
        walltime=get_resource("fastqc","walltime")
    log:
        f"{LOGDIR}/fastqc_trim/{{sample}}_r{{read}}.log"
    benchmark:
        f"{LOGDIR}/fastqc_trim/{{sample}}_r{{read}}.bmk"
    wrapper:
        "v2.6.0/bio/fastqc"

rule epibac_kraken2:
    input:
        setup_db = f"{LOGDIR}/setup/setup_kraken2_db.flag",
        r1 = rules.epibac_fastp_pe.output.r1,
        r2 = rules.epibac_fastp_pe.output.r2
    output:
        f"{OUTDIR}/qc/kraken2/{{sample}}_CR_1.fastq",
        f"{OUTDIR}/qc/kraken2/{{sample}}_CR_2.fastq",
        report = f"{OUTDIR}/qc/kraken2/{{sample}}.txt"
    params:
        classified_out = f"{OUTDIR}/qc/kraken2/{{sample}}_CR#.fastq",
        unclassified_out = f"{OUTDIR}/qc/kraken2/{{sample}}_unclassified#.fastq"
    log:
        f"{LOGDIR}/kraken2/{{sample}}.log"
    conda:
        '../envs/epibac_qc.yml'
    threads: get_resource("kraken2", "threads")
    resources:
        mem_mb = get_resource("kraken2", "mem"),
        walltime = get_resource("kraken2", "walltime")
    shell:
        r"""
        # Averigua la ruta del ambiente conda activo
        CONDA_PREFIX=${{CONDA_PREFIX}}

        kraken2 \
            --threads {threads} \
            --db $CONDA_PREFIX/db/kraken2_minusb \
            --gzip-compressed \
            --paired {input.r1} {input.r2} \
            --report {output.report} \
            --classified-out {params.classified_out} \
            --unclassified-out {params.unclassified_out} \
            --use-names \
            &> {log}
        """
        
rule epibac_quast:
    input:
        fasta=f"{OUTDIR}/assembly/{{sample}}/{{sample}}.fasta"
    output:
        directory(f"{OUTDIR}/qc/quast/{{sample}}")
    params:
        label=lambda wc: wc.sample
    log:
        f"{LOGDIR}/quast/{{sample}}.log"
    conda:
        '../envs/epibac_qc.yml'
    threads: get_resource("quast", "threads")
    resources:
        mem_mb=get_resource("quast", "mem"),
        walltime=get_resource("quast", "walltime")
    shell:
        """
        if [ ! -s {input.fasta} ]; then
            echo "[ERROR] El archivo FASTA {input.fasta} está vacío." > {log}
            mkdir -p {output}
            exit 0
        fi

        quast -t {threads} \
              {input.fasta} \
              -l {params.label} \
              --glimmer \
              -o {output} \
              &>> {log}
        """
        
rule multiqc:
    input:
        lambda wc: expand(f"{OUTDIR}/qc/fastqc_raw/{{sample}}_r{{read}}_fastqc.zip", sample=get_samples().index, read=["1","2"]),
        lambda wc: expand(f"{OUTDIR}/qc/fastqc_trim/{{sample}}_r{{read}}_fastqc.zip", sample=get_samples().index, read=["1","2"]),
        lambda wc: expand(f"{OUTDIR}/qc/kraken2/{{sample}}.txt", sample=get_samples().index),
        lambda wc: expand(f"{OUTDIR}/qc/quast/{{sample}}", sample=get_samples().index),
        lambda wc: expand(f"{OUTDIR}/annotation/{{sample}}", sample=get_samples().index)
    output:
        f"{OUTDIR}/qc/multiqc.html"
    log:
        f"{LOGDIR}/multiqc.log"
    threads: get_resource("multiqc", "threads")
    resources:
        mem_mb=get_resource("multiqc", "mem"),
        walltime=get_resource("multiqc", "walltime")
    wrapper:
        "v2.9.1/bio/multiqc"