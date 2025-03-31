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
    container: 
        "docker://alesanzdro/epibac_qc:1.0"
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
    container: 
        "docker://alesanzdro/epibac_qc:1.0"
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
    container: 
        "docker://alesanzdro/epibac_qc:1.0"
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
    container: 
        "docker://alesanzdro/epibac_qc:1.0"
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
    container: 
        "docker://alesanzdro/epibac_qc:1.0"
    wrapper:
        "v2.6.0/bio/fastqc"

rule epibac_kraken2:
    input:
        setup_db = KRAKEN_DB_FLAG,
        r1 = rules.epibac_fastp_pe.output.r1,
        r2 = rules.epibac_fastp_pe.output.r2
    output:
        "{}/qc/kraken2/{{sample}}_CR_1.fastq".format(OUTDIR),
        "{}/qc/kraken2/{{sample}}_CR_2.fastq".format(OUTDIR),
        report = "{}/qc/kraken2/{{sample}}.txt".format(OUTDIR)
    params:
        report_dir = directory("{}/qc/kraken2".format(OUTDIR)),
        classified_out = "{}/qc/kraken2/{{sample}}_CR#.fastq".format(OUTDIR),
        db_path = KRAKEN_DB_DIR
    log:
        f"{LOGDIR}/kraken2/{{sample}}.log"
    conda: 
        "../envs/epibac_qc.yml"
    container: 
        "docker://alesanzdro/epibac_qc:1.0"
    threads: get_resource("kraken2", "threads")
    resources:
        mem_mb = get_resource("kraken2", "mem"),
        walltime = get_resource("kraken2", "walltime")
    shell:
        """
        kraken2 \
            --threads {threads} \
            --db {params.db_path} \
            --gzip-compressed \
            --paired {input.r1} {input.r2} \
            --output {output.report} \
            --classified-out "{params.classified_out}" \
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
    container: 
        "docker://alesanzdro/epibac_qc:1.0"
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
        validated = f"{OUTDIR}/samples_info_validated.csv",
        fastqc_raw = lambda wc: [
            f"{OUTDIR}/qc/fastqc_raw/{sample}_r{read}_fastqc.zip"
            for sample in get_samples().index for read in ["1", "2"]
        ],
        fastqc_trim = lambda wc: [
            f"{OUTDIR}/qc/fastqc_trim/{sample}_r{read}_fastqc.zip"
            for sample in get_samples().index for read in ["1", "2"]
        ],
        kraken = lambda wc: [
            f"{OUTDIR}/qc/kraken2/{sample}.txt" for sample in get_samples().index
        ],
        quast = lambda wc: [
            f"{OUTDIR}/qc/quast/{sample}" for sample in get_samples().index
        ],
        annot = lambda wc: [
            f"{OUTDIR}/annotation/{sample}" for sample in get_samples().index
        ]
    output:
        f"{OUTDIR}/qc/multiqc.html"
    log:
        f"{LOGDIR}/multiqc.log"
    threads: get_resource("multiqc", "threads")
    resources:
        mem_mb=get_resource("multiqc", "mem"),
        walltime=get_resource("multiqc", "walltime")
    container: 
        "docker://alesanzdro/epibac_qc:1.0"
    wrapper:
        "v2.9.1/bio/multiqc"
