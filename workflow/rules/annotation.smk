rule epibac_prokka:
    input:
        setup_db=PROKKA_DB_FLAG,
        fasta=lambda wc: f"{OUTDIR}/assembly/{wc.sample}/{wc.sample}.fasta",
    output:
        faa="{}/annotation/{{sample}}/{{sample}}.faa".format(OUTDIR),
        gff="{}/annotation/{{sample}}/{{sample}}.gff".format(OUTDIR),
        dir=directory("{}/annotation/{{sample}}".format(OUTDIR)),
    log:
        f"{LOGDIR}/prokka/{{sample}}.log",
    conda:
        "../envs/epibac_amr_annotation.yml"
    container:
        "docker://alesanzdro/epibac_amr_annotation:1.0"
    threads: get_resource("prokka", "threads")
    resources:
        mem_mb=get_resource("prokka", "mem"),
        walltime=get_resource("prokka", "walltime"),
    params:
        prefix=lambda wc: f"{wc.sample}",
        db_dir=PROKKA_DB_DIR,
        skip=should_skip("prokka"),
    script:
        "../scripts/run_prokka.py"
