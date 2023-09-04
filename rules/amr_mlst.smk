rule epibac_amr:
    input:
        fasta = lambda wc: f"{OUTDIR}/assembly/{wc.sample}/{wc.sample}.fasta",
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
        > {output.tsv}
        """

        #fasta = "{}/assembly/{{sample}}/{{sample}}.fasta".format(OUTDIR),
        #prokka = "{}/annotation/{{sample}}/{{sample}}.faa".format(OUTDIR)

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
        mlst \
        --label {params.name} \
        {input} \
        > {output.tsv}
        """
	
