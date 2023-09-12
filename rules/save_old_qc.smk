
rule epibac_fastqc_raw:
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
        "{}/fastqc_raw/{{sample}}_r{{read}}.log".format(LOGDIR)
    benchmark:
        "{}/fastqc_raw/{{sample}}_r{{read}}.bmk".format(LOGDIR)
    wrapper:
        "v2.6.0/bio/fastqc"

#rule epibac_fastqc_raw:
#    input:
#        raw=lambda wc: samples.loc[(wc.sample)]['fq' + wc.read]
#    output:
#        html="{}/qc/fastqc_raw/{{sample}}_r{{read}}_fastqc.html".format(OUTDIR),
#        zip="{}/qc/fastqc_raw/{{sample}}_r{{read}}_fastqc.zip".format(OUTDIR)
#    threads: get_resource("fastqc","threads")
#    resources:
#        mem_mb=get_resource("fastqc","mem"),
#        walltime=get_resource("fastqc","walltime")
#    params:
#        path="{}/qc/fastqc/".format(OUTDIR)
#    conda:
#       '../envs/epibac.yml'
#    log:
#        "{}/fastqc/{{sample}}_r{{read}}.log".format(LOGDIR)
#
#    shell:
#        """
#        fastqc {input.raw} --threads {threads} -o {params.path}
#        """


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

rule fastqc_trim:
    input:
        reads=rules.validate_reads.output.validated,
        r1="out/trimmed/{sample}_1.fastq.gz",
        r2="out/trimmed/{sample}_2.fastq.gz"
    output:
        fastqc="out/fastqc/{sample}.fastqc_done"
    shell:
        """
        fastqc {input.r1} {input.r2} -o out/fastqc/
        touch {output.fastqc}
        """







#rule create_initial_file:
#    output:
#        "out/qc/fastq_filter/samples_pass.csv"
#    shell:
#        """
#        mkdir -p out/qc/fastq_filter
#        touch {output}
#        """

#def get_filtered_samples():
#    try:
#        with open(rules.epibac_fastq_filter_reco.output[0], 'r') as file:
#            return [line.split(';')[0] for line in file if int(line.split(';')[1].strip()) > 1000]
#    except FileNotFoundError:
#        return []       

checkpoint epibac_fastq_filter_reco:
    """
    Esta regla utiliza una operación de expansión para obtener todos los archivos 
    de texto generados por la regla anterior. Luego, se leen estos archivos y si 
    el número de lecturas es más de 1000, se escribe el nombre de la muestra y el 
    número de lecturas en un archivo CSV.
    """
    input:
        [expand(f"{LOGDIR}/fastq_filter/{row.sample}.txt") for row in samples.itertuples()]
    output:
        f"{OUTDIR}/qc/fastq_filter/samples_pass.csv"
    shell:
        """
        python -c "
        import os

        with open('{output}', 'w') as fout:
            for filepath in {input}:
                sample = os.path.basename(filepath).replace('.txt', '')
                with open(filepath) as fin:
                    read_count = fin.read().strip()
                if int(read_count) > 1000:
                    fout.write(f'{sample};{read_count}\n')
        "
        """


rule epibac_fastqc_trim:
    input:
        lambda wc: f"{OUTDIR}/trimmed/{wc.sample}_r{wc.read}.fastq.gz" if wc.sample in get_filtered_samples() else []
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

#rule epibac_fastqc_trim:
#    input:
#        lambda wc: f"{OUTDIR}/trimmed/{wc.sample}_r{wc.read}.fastq.gz" 
#    output:
#        html="{}/qc/fastqc_trim/{{sample}}_r{{read}}_fastqc.html".format(OUTDIR),
#        zip="{}/qc/fastqc_trim/{{sample}}_r{{read}}_fastqc.zip".format(OUTDIR)
#    threads: get_resource("fastqc","threads")
#    resources:
#        mem_mb=get_resource("fastqc","mem"),
#        walltime=get_resource("fastqc","walltime")
#    params:
#        lambda wc: "-t {}".format(get_resource("fastqc","threads"))
#    log:
#        "{}/fastqc_trim/{{sample}}_r{{read}}.log".format(LOGDIR)
#    benchmark:
#        "{}/fastqc_trim/{{sample}}_r{{read}}.bmk".format(LOGDIR)
#    wrapper:
#        "v2.6.0/bio/fastqc"


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


rule multiqc:
    input:
        [expand(f"{OUTDIR}/qc/fastqc_raw/{row.sample}_{{r}}_fastqc.zip", r=["r1"]) for row in samples.itertuples() if (str(getattr(row, 'fq2')) == "nan")],
        #[expand(f"{OUTDIR}/qc/fastqc_trim/{sample}_{{r}}_fastqc.zip", r=["r1","r2"]) for sample in get_filtered_samples() if (str(getattr(sample, 'fq2')) != "nan")],
        #[expand(f"{OUTDIR}/trimmed/{sample}_{{r}}.fastq.gz", r=["r1","r2"]) for sample in get_filtered_samples() if (str(getattr(sample, 'fq2')) != "nan")],
        #[f"{OUTDIR}/qc/kraken2/{sample}.txt".format(OUTDIR=OUTDIR, sample=sample) for sample in get_filtered_samples()],
        #[f"{OUTDIR}/qc/quast/{sample}".format(OUTDIR=OUTDIR, sample=sample) for sample in get_filtered_samples()],
        #[f"{OUTDIR}/annotation/{sample}".format(OUTDIR=OUTDIR, sample=sample) for sample in get_filtered_samples()],
        #[f"{OUTDIR}/amr_mlst/{sample}_amrfinder.tsv".format(OUTDIR=OUTDIR, sample=sample) for sample in get_filtered_samples()],
        #[f"{OUTDIR}/amr_mlst/{sample}_mlst.tsv".format(OUTDIR=OUTDIR, sample=sample) for sample in get_filtered_samples()],
        #[f"{OUTDIR}/amr_mlst/resfinder/{sample}/ResFinder_results.txt".format(OUTDIR=OUTDIR, sample=sample) for sample in get_filtered_samples()]
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
