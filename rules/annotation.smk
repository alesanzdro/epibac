rule epibac_prokka:
    input:
        setup_db = PROKKA_DB_FLAG,
        fasta = lambda wc: f"{OUTDIR}/assembly/{wc.sample}/{wc.sample}.fasta" 
    output:
        faa = "{}/annotation/{{sample}}/{{sample}}.faa".format(OUTDIR),
        gff = "{}/annotation/{{sample}}/{{sample}}.gff".format(OUTDIR),
        dir = directory("{}/annotation/{{sample}}".format(OUTDIR))
    log:
        f"{LOGDIR}/prokka/{{sample}}.log"
    conda:
        '../envs/epibac_amr_annotation.yml'
    container: 
        "docker://alesanzdro/epibac_amr_annotation:1.0"
    threads: get_resource("prokka","threads")
    resources:
        mem_mb = get_resource("prokka","mem"),
        walltime = get_resource("prokka","walltime")
    params:
        prefix = lambda wc: f"{wc.sample}",
        db_dir = PROKKA_DB_DIR
    shell:
        """
        # Verifica si el archivo FASTA es vacío o no
        if [ ! -s {input.fasta} ]; then
            echo "[ERROR] El archivo FASTA {input.fasta} está vacío" &> {log}
            mkdir -p {output.dir}
            touch {output.faa}
            touch {output.gff}
            exit 0
        fi

        prokka \
        --cpus {threads} \
        {input.fasta} \
        --prefix {params.prefix} \
        --strain {params.prefix} \
        --locustag {params.prefix} \
        --hmms {params.db_dir}/PGAP.hmm \
        --outdir {output.dir} \
        --force \
        &> {log}
        """
