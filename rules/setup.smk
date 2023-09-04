rule setup_kraken2_database:
    output:
        f"{LOGDIR}/setup/setup_kraken2_db.flag"
    log:
        f"{LOGDIR}/setup/kraken2_db.log"
    conda:
        '../envs/epibac.yml'
    shell:
        """
        # Averigua la ruta del ambiente conda activo
        CONDA_PREFIX=${{CONDA_PREFIX}}

        # Crear el directorio si no existe
        mkdir -p $CONDA_PREFIX/db/kraken2_minusb/

        # Descarga la base de datos
        #wget -O $CONDA_PREFIX/db/kraken2_minusb/k2_minusb_20230605.tar.gz https://genome-idx.s3.amazonaws.com/kraken/k2_minusb_20230605.tar.gz &>> {log}
        # https://genome-idx.s3.amazonaws.com/kraken/k2_pluspf_20230605.tar.gz
        # Descomprime la base de datos
        tar -xvzf $CONDA_PREFIX/db/kraken2_minusb/k2_minusb_20230605.tar.gz -C $CONDA_PREFIX/db/kraken2_minusb/ &>> {log}
        
        # Eliminamos fichero que ya no necesitamos
        rm $CONDA_PREFIX/db/kraken2_minusb/k2_minusb_20230605.tar.gz*

        # Crear un flag para indicar que la configuración está completa
        touch {output}
        """

rule setup_prokka_database:
    """
    The up-to-date versions of all TIGRFAM models are available for download by FTP as a component of the current release of PGAP HMMs. 
    """
    output:
        f"{LOGDIR}/setup/setup_prokka_db.flag"
    log:
        f"{LOGDIR}/setup/prokka_db.log"
    conda:
        '../envs/epibac.yml'
    shell:
        """
        # Averigua la ruta del ambiente conda activo
        CONDA_PREFIX=${{CONDA_PREFIX}}

        # Modificamos variable entorno de forma permanente
        echo "export PATH=$CONDA_PREFIX/bin:\$PATH" > $CONDA_PREFIX/etc/conda/activate.d/export_perl.sh
        chmod +x $CONDA_PREFIX/etc/conda/activate.d/export_perl.sh
        export PATH=$CONDA_PREFIX/bin:$PATH

        # Crear el directorio si no existe
        mkdir -p $CONDA_PREFIX/db/hmm/

        # Descarga la base de datos
        echo -e "\n\n$(printf '*%.0s' {{1..25}}) Descargamos base de datos $(printf '*%.0s' {{1..25}})\n" &>> {log}
        wget -O $CONDA_PREFIX/db/hmm/hmm_PGAP.HMM.tgz https://ftp.ncbi.nlm.nih.gov/hmm/current/hmm_PGAP.HMM.tgz &>> {log}

        # Descomprime la base de datos
        tar -xvzf $CONDA_PREFIX/db/hmm/hmm_PGAP.HMM.tgz -C $CONDA_PREFIX/db/hmm/ &>> {log}

        # Concatenamos todos en un solo fichero
        cat $CONDA_PREFIX/db/hmm/hmm_PGAP/*.HMM > $CONDA_PREFIX/db/hmm/PGAP.hmm
        
        echo -e "\n\n$(printf '*%.0s' {{1..25}}) Construimos índice HMMER $(printf '*%.0s' {{1..25}})\n" &>> {log}
        hmmpress $CONDA_PREFIX/db/hmm/PGAP.hmm &>> {log}

        # Asegura que Prokka pueda encontrar la base de datos
        echo -e "\n\n$(printf '*%.0s' {{1..25}}) SETUP PROKKA DB $(printf '*%.0s' {{1..25}})\n" &>> {log}
        prokka --setupdb &>> {log}

        # Eliminamos fichero que ya no necesitamos
        rm $CONDA_PREFIX/db/hmm/hmm_PGAP.HMM.tgz*

        # Crear un flag para indicar que la configuración está completa
        touch {output}
        """

rule setup_amrfinder_database:
    output:
        f"{LOGDIR}/setup/setup_amrfinder_db.flag"
    log:
        f"{LOGDIR}/setup/setup_amrfinder_db.log"
    conda:
        '../envs/epibac.yml'
    shell:
        """
        echo -e "\n\n$(printf '*%.0s' {{1..25}}) SETUP AMRFINDER DB $(printf '*%.0s' {{1..25}})\n" &>> {log}
        amrfinder -u &>> {log}
        touch {output}
        """

rule setup_resfinder_database:
    output:
        f"{LOGDIR}/setup/setup_resfinder_db.flag"
    log:
        f"{LOGDIR}/setup/setup_resfinder_db.log"
    conda:
        '../envs/epibac_extra.yml'
    shell:
        """
        # Averigua la ruta del ambiente conda activo
        CONDA_PREFIX=${{CONDA_PREFIX}}

        # Clonamos DB
        if [ -d "$CONDA_PREFIX/share/resfinder-4.1.11/db/resfinder_db" ]; then
            rm -rf $CONDA_PREFIX/share/resfinder-4.1.11/db/resfinder_db
        fi

        git clone https://git@bitbucket.org/genomicepidemiology/resfinder_db.git $CONDA_PREFIX/share/resfinder-4.1.11/db/resfinder_db

        # Modificamos variable entorno de forma permanente
        echo "export CGE_BLASTN=$CONDA_PREFIX/bin/blastn" > $CONDA_PREFIX/etc/conda/activate.d/CGE.sh
        echo "export CGE_RESFINDER_RESGENE_DB=$CONDA_PREFIX/share/resfinder-4.1.11/db/resfinder_db" >> $CONDA_PREFIX/etc/conda/activate.d/CGE.sh
        chmod +x $CONDA_PREFIX/etc/conda/activate.d/CGE.sh
        
        touch {output}
        """
