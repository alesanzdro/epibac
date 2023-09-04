rule epibac_assembly:
    input:
        r1 = rules.epibac_fastp_pe.output.r1,
        r2 = rules.epibac_fastp_pe.output.r2
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
        """
        unicycler \
	    -t {threads} \
	    {config[params][unicycler][extra]} \
	    -1 {input.r1} \
	    -2 {input.r2} \
	    -o {params.output_dir} \
        &> {log}

        # Verificar si los archivos existen
        if [ -f {params.output_dir}/assembly.fasta ] && [ -f {params.output_dir}/assembly.gfa ] && [ -f {params.output_dir}/unicycler.log ]; then
            # Si los archivos existen, cambiar el nombre
            mv {params.output_dir}/assembly.fasta {output.fasta}
            mv {params.output_dir}/assembly.gfa {output.gfa}
            mv {params.output_dir}/unicycler.log {output.log_file}
        else
            # Si no existen, escribir un mensaje de error en el archivo de log
            echo "Error: uno o más archivos de salida de Unicycler no se encontraron" >> {log}
        fi
        """
