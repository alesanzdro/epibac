rule setup_prokka_database:
    """
    The up-to-date versions of all TIGRFAM models are available for download by FTP as a component of the current release of PGAP HMMs. 
    """
    output:
        "setup_prokka_db.flag"
    log:
        f"{LOGDIR}/setupo/prokka_db.log"
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
        wget -P $CONDA_PREFIX/db/hmm/ https://ftp.ncbi.nlm.nih.gov/hmm/current/hmm_PGAP.HMM.tgz

        # Descomprime la base de datos
        tar -xvzf $CONDA_PREFIX/db/hmm/hmm_PGAP.HMM.tgz -C $CONDA_PREFIX/db/hmm/

        # Concatenamos todos en un solo fichero
        cat $CONDA_PREFIX/db/hmm/hmm_PGAP/*.HMM > $CONDA_PREFIX/db/hmm/PGAP.hmm
        
        # Construimos índice HMMER
        hmmpress $CONDA_PREFIX/db/hmm/PGAP.hmm

        # Asegura que Prokka pueda encontrar la base de datos
        prokka --setupdb

        # Configuramois base de datos de amrfinder
        amrfinder -u

        # Crear un flag para indicar que la configuración está completa
        touch {output}
        """
