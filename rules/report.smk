from datetime import datetime

DATE = datetime.now().strftime("%y%m%d")

rule epibac_summary:
    input:
        counts = lambda wc: [f"{OUTDIR}/qc/count_reads/{sample}_counts.txt" for sample in get_samples().index],
        amrfinder = lambda wc: [f"{OUTDIR}/amr_mlst/{sample}_amrfinder.tsv" for sample in get_samples()[get_samples()["illumina_r2"].notnull()].index],
        mlst = lambda wc: [f"{OUTDIR}/amr_mlst/{sample}_mlst.tsv" for sample in get_samples()[get_samples()["illumina_r2"].notnull()].index],
        resfinder = lambda wc: [f"{OUTDIR}/amr_mlst/resfinder/{sample}/ResFinder_results.txt" for sample in get_samples()[get_samples()["illumina_r2"].notnull()].index],
    output:
        report_dir = directory(f"{OUTDIR}/report"),
        tsv = f"{OUTDIR}/report/{DATE}_EPIBAC.tsv",
        xlsx = f"{OUTDIR}/report/{DATE}_EPIBAC.xlsx"
    params:
        input = directory(f"{OUTDIR}/amr_mlst")
    log:
        f"{LOGDIR}/report/summary.log"
    conda:
        '../envs/epibac_report.yml'
    threads: get_resource("summary", "threads")
    resources:
        mem_mb = get_resource("summary", "mem"),
        walltime = get_resource("summary", "walltime")
    script:
        "../scripts/epibac_summary.py"

rule epibac_summary_gestlab:
    input:
        validated_samples_info = f"{OUTDIR}/samples_info_validated.csv",
        results = f"{OUTDIR}/report/{DATE}_EPIBAC.tsv"
    output:
        gestlab_report = f"{OUTDIR}/report/{DATE}_EPIBAC_GESTLAB.csv"
    log:
        f"{LOGDIR}/report/summary_gestlab.log"
    conda:
        '../envs/epibac_report.yml'
    container: 
        "docker://alesanzdro/epibac_report:1.0"
    threads: get_resource("summary", "threads")
    resources:
        mem_mb = get_resource("summary", "mem"),
        walltime = get_resource("summary", "walltime")
    run:
        import pandas as pd
        
        df_meta = pd.read_csv(input.validated_samples_info, sep=";")
        df_results = pd.read_csv(input.results, sep="\t")

        # Detectamos si Sample coincide con id o con id2
        if df_results['Sample'].isin(df_meta['id']).all():
            merge_col = 'id'
        elif df_results['Sample'].isin(df_meta['id2']).all():
            merge_col = 'id2'
        else:
            raise ValueError("No se puede encontrar coincidencia entre 'Sample' y 'id' o 'id2'.")

        df_results = df_results.rename(columns={"Sample": merge_col})
        df_merged = df_meta.merge(df_results, on=merge_col, how="left")

        # Eliminar columnas no deseadas
        for col in ["SCOPE_core", "GENE_resfinder", "PHENO_resfinder", "MLST"]:
            if col in df_merged.columns:
                df_merged.drop(columns=col, inplace=True)

        # Renombramos columnas
        rename_map_gva = {
            "PETICION": "id",
            "CODIGO_ORIGEN": "id2",
            "FECHA_TOMA_MUESTRA": "collection_date",
            "MO": "organism",
            "MOTIVO_WGS": "relevance",
            "CARRERA": "run_id",
            "ILLUMINA_R1": "illumina_r1",
            "ILLUMINA_R2": "illumina_r2",
            "ONT": "nanopore",
            "MODELO_DORADO": "dorado_model",
            "ID-WGS": "Scheme_mlst",
            "ST-WGS": "ST",
            "MLST-WGS": "MLST",
            "R-Geno-WGS": "AMR",
            "PHENO-WGS": "PHENO_resfinder",
            "V-WGS": "VIRULENCE"
        }
        df_merged.rename(columns={v: k for k, v in rename_map_gva.items()}, inplace=True)

        # Añadir columnas extra
        df_merged['MO-EST-WGS'] = "Bacterias"
        df_merged['Tipo_Analisis_WGS'] = "Verificación"
        df_merged['Plasmidos-WGS'] = pd.NA

        # Generar Fichero_lecturas_WGS
        def build_path(row):
            if pd.isna(row['CARRERA']):
                return pd.NA
            parts = row['CARRERA'].split("_")
            if len(parts) < 2:
                return pd.NA
            hosp = parts[1][:-3]  # Quitar los últimos 3 números
            return f"\\\\NLSAR\\deposito\\CVA_{hosp}\\illumina\\{row['CARRERA']}"

        df_merged['Fichero_lecturas_WGS'] = df_merged.apply(build_path, axis=1)

        # Simplificamos columnas de nombres de ficheros
        for col in ["ILLUMINA_R1", "ILLUMINA_R2", "ONT"]:
            if col in df_merged.columns:
                df_merged[col] = df_merged[col].apply(lambda x: os.path.basename(x) if pd.notna(x) and x != "" else x)

        # Guardar
        df_merged.to_csv(output.gestlab_report, sep=";", index=False)