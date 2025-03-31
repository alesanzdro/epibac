rule setup_kraken2_database:
    output:
        flag = KRAKEN_DB_FLAG
    log:
        KRAKEN_DB_LOG
    conda:
        '../envs/epibac_qc.yml'
    container: 
        "docker://alesanzdro/epibac_qc:1.0"
    params:
        db_url=KRAKEN_DB_URL,
        db_name=KRAKEN_DB_NAME,
        db_dir=KRAKEN_DB_DIR
    shell:
        """
        mkdir -p {params.db_dir}
        mkdir -p $(dirname {log})

        if [ ! -f "{params.db_dir}/taxo.k2d" ]; then
            echo "[INFO] Descargando base de datos Kraken2 desde {params.db_url}" &>> {log}
            wget --no-check-certificate -O {params.db_dir}/{params.db_name}.tar.gz {params.db_url} &>> {log}

            echo "[INFO] Descomprimiendo base de datos..." &>> {log}
            tar -xvzf {params.db_dir}/{params.db_name}.tar.gz -C {params.db_dir} &>> {log}

            echo "[INFO] Eliminando archivo .tar.gz..." &>> {log}
            rm -f {params.db_dir}/{params.db_name}.tar.gz
        else
            echo "[INFO] La base de datos ya está instalada, se omite la descarga." &>> {log}
        fi

        touch {output.flag}
        """

rule setup_prokka_database:
    """
    Descarga y configura la base de datos TIGRFAM (PGAP) para su uso con Prokka.
    """
    output:
        flag = PROKKA_DB_FLAG
    log:
        PROKKA_DB_LOG
    conda:
        '../envs/epibac_amr_annotation.yml'
    container:
        "docker://alesanzdro/epibac_amr_annotation:1.0"
    params:
        db_dir = PROKKA_DB_DIR
    shell:
        r"""
        mkdir -p {params.db_dir}
        mkdir -p $(dirname {log})

        if [ ! -f "{params.db_dir}/PGAP.hmm.h3i" ]; then
            echo "[INFO] Descargando base de datos TIGRFAM PGAP" &>> {log}
            wget --no-check-certificate -O {params.db_dir}/hmm_PGAP.HMM.tgz https://ftp.ncbi.nlm.nih.gov/hmm/current/hmm_PGAP.HMM.tgz &>> {log}

            tar -xvzf {params.db_dir}/hmm_PGAP.HMM.tgz -C {params.db_dir} &>> {log}

            find {params.db_dir}/hmm_PGAP -type f -name "*.HMM" -exec cat {{}} + > {params.db_dir}/PGAP.hmm.raw

            awk '/^NAME/ {{ if (a[$2]++) skip=1; else skip=0 }} !skip {{ print }}' \
                "{params.db_dir}/PGAP.hmm.raw" > "{params.db_dir}/PGAP.hmm"

            hmmpress {params.db_dir}/PGAP.hmm &>> {log}

            echo "[INFO] setupdb con PROKKA" &>> {log}
            prokka --setupdb &>> {log}

            rm -f {params.db_dir}/hmm_PGAP.HMM.tgz*
        else
            echo "[INFO] Base de datos ya existe. Se omite descarga." &>> {log}
        fi

        touch {output.flag}
        """

rule setup_amrfinder_database:
    output:
        flag = AMRFINDER_DB_FLAG
    log:
        AMRFINDER_DB_LOG
    conda:
        '../envs/epibac_amr_annotation_plus.yml'
    container: "docker://alesanzdro/epibac_amr_annotation_plus:1.0"
    params:
        db_dir = AMRFINDER_DB_DIR
    shell:
        r"""
        echo "[INFO] ACTUALIZANDO BASE DE DATOS AMRFinder EN {params.db_dir}" &>> {log}
        mkdir -p {params.db_dir}

        # Usamos la variable de entorno para controlar el path de instalación
        AMRFINDER_DB={params.db_dir} amrfinder -u &>> {log}

        touch {output.flag}
        """

rule setup_resfinder_database:
    output:
        flag = RESFINDER_DB_FLAG
    log:
        RESFINDER_DB_LOG
    conda:
        '../envs/epibac_amr_annotation_plus.yml'
    container: "docker://alesanzdro/epibac_amr_annotation_plus:1.0"
    params:
        db_dir = RESFINDER_DB_DIR
    shell:
        """
        mkdir -p {params.db_dir}

        if [ ! -d "{params.db_dir}/resfinder_db" ]; then
            echo "[INFO] Clonando base de datos de ResFinder..." &>> {log}
            git clone https://git@bitbucket.org/genomicepidemiology/resfinder_db.git {params.db_dir}/resfinder_db &>> {log}
        else
            echo "[INFO] Base de datos ResFinder ya existe." &>> {log}
        fi

        touch {output.flag}
        """