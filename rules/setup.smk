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
    Configura todas las bases de datos de Prokka (HMM, BLAST, CM) en un directorio externo.
    """
    output:
        flag = PROKKA_DB_FLAG
    log:
        PROKKA_DB_LOG
    params:
        db_dir = PROKKA_DB_DIR,
        cm_files = ["Archaea", "Bacteria", "Viruses"]  # Archivos CM esenciales
    container:
        "docker://alesanzdro/epibac_amr_annotation:1.0"
    threads: 4
    shell:
        r"""
        # Crear estructura de directorios
        mkdir -p {params.db_dir}/{{hmm,cm,kingdom}}

        # ---- 1. Descargar HMMs de TIGRFAM (PGAP) ----
        if [ ! -f "{params.db_dir}/PGAP.hmm.h3i" ]; then
            echo -e "\n\n***** Descargando HMMs de PGAP... *****\n" &>> {log}
            wget --no-check-certificate -O {params.db_dir}/hmm_PGAP.HMM.tgz \
                https://ftp.ncbi.nlm.nih.gov/hmm/current/hmm_PGAP.HMM.tgz &>> {log}

            # Descomprimir y filtrar duplicados
            tar -xvzf {params.db_dir}/hmm_PGAP.HMM.tgz -C {params.db_dir} &>> {log}
            find {params.db_dir}/hmm_PGAP -name "*.HMM" -exec cat {{}} + > {params.db_dir}/PGAP.hmm.raw
            awk '/^NAME/ {{ if (a[$2]++) skip=1; else skip=0 }} !skip {{ print }}' \
                {params.db_dir}/PGAP.hmm.raw > {params.db_dir}/PGAP.hmm

            # Generar índices HMMER
            hmmpress -f {params.db_dir}/PGAP.hmm &>> {log} || {{ echo "[ERROR] hmmpress falló"; exit 1; }}
        fi

        # ---- 2. Descargar CM de Rfam (Infernal) ----
        echo -e "\n\n***** Descargando CM de Rfam... *****\n" &>> {log}
        for cm_file in {params.cm_files}; do
            if [ ! -f "{params.db_dir}/cm/$cm_file" ]; then
                wget --no-check-certificate -O {params.db_dir}/cm/$cm_file \
                    https://github.com/tseemann/prokka/raw/refs/heads/master/db/cm/$cm_file &>> {log}
            fi
        done

        # ---- 3. Configurar TODAS las bases de datos de Prokka ----
        echo -e "\n\n***** Configurando Prokka (HMM + BLAST + CM)... *****\n" &>> {log}
        prokka --cpus {threads} --dbdir {params.db_dir} --setupdb &>> {log} || {{ echo "[ERROR] prokka --setupdb falló"; exit 1; }}

        # ---- 4. Verificar archivos críticos ----
        # HMM
        for ext in "" .h3f .h3i .h3m .h3p; do
            if [ ! -f "{params.db_dir}/PGAP.hmm$ext" ]; then
                echo "[ERROR] PGAP.hmm$ext no existe" &>> {log}
                exit 1
            fi
        done

        # CM
        for cm_file in {params.cm_files}; do
            if [ ! -f "{params.db_dir}/cm/$cm_file" ]; then
                echo "[ERROR] $cm_file no existe en cm/" &>> {log}
                exit 1
            fi
        done

        # ---- 5. Limpiar temporales ----
        rm -rf {params.db_dir}/hmm_PGAP* {params.db_dir}/PGAP.hmm.raw
        touch {output.flag}
        """

rule setup_amrfinder_database:
    output:
        flag = AMRFINDER_DB_FLAG,
        version = AMRFINDER_DB_DIR + "/VERSION.txt"
    log:
        AMRFINDER_DB_LOG
    conda:
        '../envs/epibac_amr_annotation_plus.yml'
    container: "docker://alesanzdro/epibac_amr_annotation_plus:1.0"
    params:
        db_dir = AMRFINDER_DB_DIR
    shell:
        r"""
        echo "[INFO] Descargando base de datos AMRFinder en {params.db_dir}" &>> {log}
        mkdir -p {params.db_dir}

        amrfinder_update --force_update --database {params.db_dir} &>> {log}

        # Detectar la versión descargada (directorio más reciente)
        VERSION=$(ls -1 {params.db_dir} | grep -E '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}\..*' | sort -r | head -n 1)

        # Crear enlace simbólico "latest" -> versión
        ln -sfn "$VERSION" {params.db_dir}/latest

        # Guardar metadata mínima
        echo "Fecha de instalación: $(date --iso-8601=seconds)" > {output.version}
        echo "Versión: $VERSION" >> {output.version}
        echo "Ruta real: {params.db_dir}/$VERSION" >> {output.version}

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
            git clone https://git@bitbucket.org/genomicepidemiology/resfinder_db.git {params.db_dir} &>> {log}
        else
            echo "[INFO] Base de datos ResFinder ya existe." &>> {log}
        fi

        touch {output.flag}
        """

rule metadata_prokka_database:
    input:
        flag = PROKKA_DB_FLAG
    output:
        version = PROKKA_DB_DIR + "/VERSION.txt",
        md5 = PROKKA_DB_DIR + "/checksums.md5",
        readme = PROKKA_DB_DIR + "/README.txt"
    params:
        db_dir = PROKKA_DB_DIR,
        enable = config.get("enable_metadata", False)
    run:
        if not params.enable:
            print("Skipping metadata for Prokka DB (config[enable_metadata]=false)")
            for o in output:
                shell(f"touch {o}")
            return
        
        # Escribir versión detectada de HMM (si existe)
        version_info = "unknown"
        hmm_path = os.path.join(params.db_dir, "PGAP.hmm")
        if os.path.exists(hmm_path):
            version_info = shell(f"grep -m1 '^ACC' {hmm_path} | cut -f2", read=True).strip()
        with open(output.version, "w") as f:
            f.write(f"PGAP Version: {version_info}\n")

        # Calcular checksums
        shell(f"cd {params.db_dir} && find . -type f -exec md5sum {{}} + > {output.md5}")

        # README con contexto
        with open(output.readme, "w") as f:
            f.write(
                f"""# Prokka Custom Database Setup
Fecha de instalación: {datetime.datetime.now().isoformat()}
Ruta: {params.db_dir}
Versión HMM: {version_info}
Regla base: setup_prokka_database
Entorno: Docker/Singularity compatible
""")