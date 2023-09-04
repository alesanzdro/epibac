rule epibac_prokka:
    input:
        setup = "setup_prokka_db.flag",
        fasta = lambda wc: f"{OUTDIR}/assembly/{wc.sample}/{wc.sample}.fasta" 
        #fasta = "{}/assembly/{{sample}}/{{sample}}.fasta".format(OUTDIR)
    output:
        faa = "{}/annotation/{{sample}}/{{sample}}.faa".format(OUTDIR),
        dir = directory("{}/annotation/{{sample}}".format(OUTDIR))
    log:
        f"{LOGDIR}/prokka/{{sample}}.log"
    conda:
        '../envs/epibac.yml'
    threads: get_resource("prokka","threads")
    resources:
        mem_mb = get_resource("prokka","mem"),
        walltime = get_resource("prokka","walltime")
    params:
        prefix=lambda wc: f"{wc.sample}" 
    shell:
        """
        # Averigua la ruta del ambiente conda activo
        CONDA_PREFIX=${{CONDA_PREFIX}}

        prokka \
        --cpus {threads} \
        {input.fasta} \
        --prefix {params.prefix} \
        --strain {params.prefix} \
        --locustag {params.prefix} \
        --hmms $CONDA_PREFIX/db/hmm/PGAP.hmm \
        --force \
        --outdir {output.dir}
        #&> {log}
        """
