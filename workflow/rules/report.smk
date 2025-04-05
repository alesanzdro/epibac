rule epibac_summary:
    input:
        counts=lambda wc: [
            f"{OUTDIR}/qc/count_reads/{sample}_counts.txt"
            for sample in get_samples().index
        ],
        amrfinder=lambda wc: [
            f"{OUTDIR}/amr_mlst/{sample}_amrfinder.tsv"
            for sample in get_samples()[get_samples()["illumina_r2"].notnull()].index
        ],
        mlst=lambda wc: [
            f"{OUTDIR}/amr_mlst/{sample}_mlst.tsv"
            for sample in get_samples()[get_samples()["illumina_r2"].notnull()].index
        ],
        resfinder=lambda wc: [
            f"{OUTDIR}/amr_mlst/resfinder/{sample}/ResFinder_results.txt"
            for sample in get_samples()[get_samples()["illumina_r2"].notnull()].index
        ],
    output:
        report_dir=directory(f"{OUTDIR}/report"),
        tsv=f"{OUTDIR}/report/{TAG_RUN}_EPIBAC.tsv",
        xlsx=f"{OUTDIR}/report/{TAG_RUN}_EPIBAC.xlsx",
    params:
        input=directory(f"{OUTDIR}/amr_mlst"),
    log:
        f"{LOGDIR}/report/summary.log",
    conda:
        "../envs/epibac_report.yml"
    threads: get_resource("summary", "threads")
    resources:
        mem_mb=get_resource("summary", "mem"),
        walltime=get_resource("summary", "walltime"),
    script:
        "../scripts/epibac_summary.py"


rule epibac_summary_gestlab:
    input:
        validated_samples_info=f"{OUTDIR}/samples_info_validated.csv",
        results=f"{OUTDIR}/report/{TAG_RUN}_EPIBAC.tsv",
    output:
        gestlab_report=f"{OUTDIR}/report/{TAG_RUN}_EPIBAC_GESTLAB.csv",
    log:
        f"{LOGDIR}/report/summary_gestlab.log",
    conda:
        "../envs/epibac_report.yml"
    container:
        "docker://alesanzdro/epibac_report:1.0"
    threads: get_resource("summary", "threads")
    resources:
        mem_mb=get_resource("summary", "mem"),
        walltime=get_resource("summary", "walltime"),
    run:
        import pandas as pd

        df_meta = pd.read_csv(input.validated_samples_info, sep=";")
        df_results = pd.read_csv(input.results, sep="\t")

        # Detectamos si Sample coincide con id o con id2
        if df_results["Sample"].isin(df_meta["id"]).all():
            merge_col = "id"
        elif df_results["Sample"].isin(df_meta["id2"]).all():
            merge_col = "id2"
        else:
            raise ValueError(
                "No se puede encontrar coincidencia entre 'Sample' y 'id' o 'id2'."
            )

        df_results = df_results.rename(columns={"Sample": merge_col})
        df_merged = df_meta.merge(df_results, on=merge_col, how="left")

        # Eliminar columnas no deseadas
        for col in ["SCOPE_core", "GENE_resfinder", "PHENO_resfinder", "MLST"]:
            if col in df_merged.columns:
                df_merged.drop(columns=col, inplace=True)

        df_merged["CARRERA"] = TAG_RUN
        # Renombramos columnas
        rename_map_gva = {
            "PETICION": "id",
                "CODIGO_MUESTRA_ORIGEN": "id2",
                "FECHA_TOMA_MUESTRA": "collection_date",
                "ESPECIE_SECUENCIA": "organism",
                "MOTIVO_WGS": "relevance",
                "ILLUMINA_R1": "illumina_r1",
                "ILLUMINA_R2": "illumina_r2",
                "NANOPORE": "nanopore",
                "ID_WS": "Scheme_mlst",
                "ST_WGS": "ST",
                "MLST_WGS": "MLST",
                "R_Geno_WGS": "AMR",
                "PHENO_WGS": "PHENO_resfinder",
                "V_WGS": "VIRULENCE",
                "CONFIRMACION": "confirmation_note",
                "NUM_BROTE": "outbreak_id",
                "COMENTARIO_WGS": "comment",
            }

        df_merged.rename(
                columns={v: k for k, v in rename_map_gva.items()}, inplace=True
        )

        # Añadir columnas extra
        df_merged["MO_EST_WGS"] = "BACTERIA"
        df_merged["TIPO_ANALISIS_WGS"] = "VERIFICACION"
        df_merged["PLASMIDOS_WGS"] = pd.NA

        # Asignar las columnas adicionales del modo GVA si existen
        # Si NUM_BROTE ya está en df_meta, se mantendrá en df_merged


        # Determinar el tipo de secuenciación (ILLUMINA, NANOPORE o HYBRID)
        def determine_seq_method(row):
            has_illumina = pd.notna(row["ILLUMINA_R1"]) and row["ILLUMINA_R1"] != ""
            has_nanopore = pd.notna(row["NANOPORE"]) and row["NANOPORE"] != ""

            if has_illumina and has_nanopore:
                return "HYBRID"
            elif has_illumina:
                return "ILLUMINA"
            elif has_nanopore:
                return "NANOPORE"
            else:
                return pd.NA

                # Añadir columna de método de secuenciación


        df_merged["OBS_MET_WGS"] = df_merged.apply(determine_seq_method, axis=1)

        # Simplificamos columnas de nombres de ficheros
        for col in ["ILLUMINA_R1", "ILLUMINA_R2", "NANOPORE"]:
            if col in df_merged.columns:
                df_merged[col] = df_merged[col].apply(
                    lambda x: os.path.basename(x) if pd.notna(x) and x != "" else x
                )

                # Generar FICHERO_LECTURAS_WGS


        def build_path(row):
            if pd.isna(row["CARRERA"]):
                return pd.NA

            parts = row["CARRERA"].split("_")
            if len(parts) < 2:
                return pd.NA

                # Obtener los parámetros específicos del modo GVA

            storage_cabinet = (
                config.get("mode_config", {})
                .get("gva", {})
                .get("storage_cabinet", "\\\\NLSAR\\deposito")
            )
            hosp = parts[1][:4]  # Primeros 4 caracteres del segundo segmento

            # Determinar plataforma según el método de secuenciación
            seq_method = row["OBS_MET_WGS"]
            platform = "illumina"  # Por defecto

            if seq_method == "NANOPORE":
                platform = "nanopore"
                # Para HYBRID, usamos illumina como primario pero guardaremos ambas rutas

                # Construir ruta de destino
            return f"{storage_cabinet}\\CVA_{hosp}\\{platform}\\{row['CARRERA']}"

            # Generar rutas de destino según el tipo de secuenciación


        df_merged["FICHEROS_LECTURAS_WGS"] = df_merged.apply(build_path, axis=1)

        # Para secuencias híbridas, necesitamos ambas rutas
        df_paths = pd.DataFrame(index=df_merged.index)
        df_paths["sample_id"] = df_merged[merge_col]
        df_paths["carrera"] = df_merged["CARRERA"]
        df_paths["seq_method"] = df_merged["OBS_MET_WGS"]
        df_paths["dest_path_illumina"] = df_merged.apply(
            lambda row: (
                build_path(row)
                if row["OBS_MET_WGS"] in ["ILLUMINA", "HYBRID"]
                else pd.NA
            ),
            axis=1,
        )
        df_paths["dest_path_nanopore"] = df_merged.apply(
            lambda row: (
                f"{config.get('mode_config',{}).get('gva',{}).get('storage_cabinet', '\\\\NLSAR\\deposito')}\\CVA_{row['CARRERA'].split('_')[1][:4]}\\nanopore\\{row['CARRERA']}"
                if row["OBS_MET_WGS"] in ["NANOPORE", "HYBRID"]
                else pd.NA
            ),
            axis=1,
        )

        # Guardar información de rutas para posible uso en un script de copia
        paths_file = os.path.join(
            os.path.dirname(output.gestlab_report), f"{DATE}_paths_for_copy.csv"
        )
        df_paths.to_csv(paths_file, sep=";", index=False)

        # Guardar
        df_merged.to_csv(output.gestlab_report, sep=";", index=False)


rule copy_sequencing_files:
    input:
        gestlab_report=f"{OUTDIR}/report/{TAG_RUN}_EPIBAC_GESTLAB.csv",
        report_tsv=f"{OUTDIR}/report/{TAG_RUN}_EPIBAC.tsv",
        report_xlsx=f"{OUTDIR}/report/{TAG_RUN}_EPIBAC.xlsx",
    output:
        copy_log=f"{OUTDIR}/report/{TAG_RUN}_file_copy_log.txt",
    log:
        f"{LOGDIR}/report/copy_sequencing_files.log",
    conda:
        "../envs/epibac_report.yml"
    threads: 1
    resources:
        mem_mb=2000,
        walltime=480,
    shell:
        """
        python scripts/copy_gva_files.py \
            {input.gestlab_report} \
            {input.report_tsv} \
            {input.report_xlsx} \
            {output.copy_log} \
            {OUTDIR} \
            {TAG_RUN} \
            2> {log}
        """
