rule epibac_assembly:
    input:
        r1=rules.epibac_fastp_pe.output.r1,
        r2=rules.epibac_fastp_pe.output.r2,
    output:
        fasta="{}/assembly/{{sample}}/{{sample}}.fasta".format(OUTDIR),
        gfa="{}/assembly/{{sample}}/{{sample}}.gfa".format(OUTDIR),
        log_file="{}/assembly/{{sample}}/{{sample}}.log".format(OUTDIR)
    log:
        f"{LOGDIR}/unicycler/{{sample}}.log"
    conda:
        '../envs/epibac.yml'
    threads: get_resource("unicycler","threads")
    resources:
        mem_mb = get_resource("unicycler","mem"),
        walltime = get_resource("unicycler","walltime")
    params:
        output_dir="{}/assembly/{{sample}}".format(OUTDIR)
    shell:
        r"""
        set -e
        
        unicycler \
            -t {threads} \
            {config[params][unicycler][extra]} \
            -1 {input.r1} \
            -2 {input.r2} \
            -o {params.output_dir} \
            &> {log} || {{
                echo "Unicycler falló, probablemente debido a una entrada pequeña o artefactos. Creando archivos de salida vacíos." >> {log}
                touch {output.fasta} {output.gfa} {output.log_file}
                exit 0
            }}

        mv {params.output_dir}/assembly.fasta {output.fasta}
        mv {params.output_dir}/assembly.gfa {output.gfa}
        mv {params.output_dir}/unicycler.log {output.log_file}
        """

