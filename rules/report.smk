from datetime import datetime

rule epibac_summary:
    input:
        ["{OUTDIR}/qc/count_reads/{sample}_counts.txt".format(OUTDIR=OUTDIR,sample=getattr(row, 'sample')) for row in samples.itertuples()],
        [expand(f"{OUTDIR}/amr_mlst/{row.sample}_amrfinder.tsv", allow_missing=True) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")],
        [expand(f"{OUTDIR}/amr_mlst/{row.sample}_mlst.tsv", allow_missing=True) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")],
        [expand(f"{OUTDIR}/amr_mlst/resfinder/{row.sample}/ResFinder_results.txt", allow_missing=True) for row in samples.itertuples() if (str(getattr(row, 'fq2')) != "nan")]
    output:
        directory("{}/report".format(OUTDIR)),
        "{OUTDIR}/report/{date}_EPIBAC.tsv".format(OUTDIR=OUTDIR, date=datetime.now().strftime("%y%m%d")),
        "{OUTDIR}/report/{date}_EPIBAC.xlsx".format(OUTDIR=OUTDIR, date=datetime.now().strftime("%y%m%d"))

    params:
       input = directory("{}/amr_mlst".format(OUTDIR))
    log:
        f"{LOGDIR}/report/summary.log"
    conda:
        '../envs/epibac_report.yml'
    threads: get_resource("summary","threads")
    resources:
        mem_mb = get_resource("summary","mem"),
        walltime = get_resource("summary","walltime")
    script:
        "../scripts/epibac_summary.py"