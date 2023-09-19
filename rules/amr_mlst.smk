rule epibac_amr:
    input:
        setup_db = f"{LOGDIR}/setup/setup_amrfinder_db.flag",
        fasta = f"{OUTDIR}/assembly/{{sample}}/{{sample}}.fasta",
        prokka = lambda wc: f"{OUTDIR}/annotation/{wc.sample}/{wc.sample}.faa",
        gff = lambda wc: f"{OUTDIR}/annotation/{wc.sample}/{wc.sample}.gff" 

    output:
        gff = "{}/annotation/{{sample}}/{{sample}}_amrfinder.gff".format(OUTDIR),
        tsv = "{}/amr_mlst/{{sample}}_amrfinder.tsv".format(OUTDIR)
    log:
        f"{LOGDIR}/amrfinder/{{sample}}.log"
    conda:
        '../envs/epibac.yml'
    threads: get_resource("amrfinder","threads")
    resources:
        mem_mb = get_resource("amrfinder","mem"),
        walltime = get_resource("amrfinder","walltime")
    params:
        name=lambda wc: f"{wc.sample}" 
    shell:
        """
        # Verifica si el archivo FASTA es vacío o no
        if [ ! -s {input.fasta} ]; then
            echo "[ERROR] El archivo FASTA {input} está vacío" &> {log}
            touch {output.gff}
            touch {output.tsv}
            exit 0
        fi

        # preparamos fichero para amrfinder
        perl -pe '/^##FASTA/ && exit; s/(\W)Name=/$1OldName=/i; s/ID=([^;]+)/ID=$1;Name=$1/' {input.gff} > {output.gff}

        amrfinder \
        --plus \
        --threads {threads} \
        --name {params.name} \
        -n {input.fasta} \
        -p {input.prokka} \
        -g {output.gff} \
        --coverage_min 0.7 \
        > {output.tsv} \
        2> {log}
        """

rule epibac_resfinder:
    input:
        setup_db = f"{LOGDIR}/setup/setup_resfinder_db.flag",
        fasta = f"{OUTDIR}/assembly/{{sample}}/{{sample}}.fasta"
    output:
        dir = directory("{}/amr_mlst/resfinder/{{sample}}".format(OUTDIR)),
        res = "{}/amr_mlst/resfinder/{{sample}}/ResFinder_results.txt".format(OUTDIR)

    log:
        f"{LOGDIR}/resfinder/{{sample}}.log"
    conda:
        '../envs/epibac_extra.yml'
    threads: get_resource("resfinder","threads")
    resources:
        mem_mb = get_resource("resfinder","mem"),
        walltime = get_resource("resfinder","walltime")
    params:
        name=lambda wc: f"{wc.sample}" 
    shell:
        """
        # Verifica si el archivo FASTA es vacío o no
        if [ ! -s {input.fasta} ]; then
            echo "[ERROR] El archivo FASTA {input} está vacío" &> {log}
            mkdir -p {output.dir}
            touch {output.res}
            exit 0
        fi

        # Averigua la ruta del ambiente conda activo
        CONDA_PREFIX=${{CONDA_PREFIX}}
        
        run_resfinder.py \
        -db_res $CONDA_PREFIX/share/resfinder-4.1.11/db/resfinder_db \
        -o {output.dir} \
        {config[params][resfinder][extra]} \
        -ifa {input.fasta} \
        &> {log}
        """

rule epibac_mlst:
    input:
        lambda wc: f"{OUTDIR}/assembly/{wc.sample}/{wc.sample}.fasta"
    output:
        tsv = "{}/amr_mlst/{{sample}}_mlst.tsv".format(OUTDIR)
    log:
        f"{LOGDIR}/mlst/{{sample}}.log"
    conda:
        '../envs/epibac.yml'
    threads: get_resource("mlst","threads")
    resources:
        mem_mb = get_resource("mlst","mem"),
        walltime = get_resource("mlst","walltime")
    params:
        name=lambda wc: f"{wc.sample}" 
    shell:
        """
        # Verifica si el archivo FASTA es vacío o no
        if [ ! -s {input} ]; then
            echo "[ERROR] El archivo FASTA {input} está vacío" &> {log}
            touch {output.tsv}
            exit 0
        fi

        mlst \
        --label {params.name} \
        {input} \
        > {output.tsv} \
        2> {log}
        """
