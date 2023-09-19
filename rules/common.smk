import glob

##### Wildcard constraints #####
wildcard_constraints:
    sample="|".join(samples["sample"])


##### Helper functions #####


def get_resource(rule,resource):
    try:
        return config["resources"][rule][resource]
    except KeyError:
        return config["resources"]["default"][resource]

def get_fastq(wildcards):
    """Get fastq files of given sample-unit."""
    fastqs = samples.loc[(wildcards.sample), ["fq1", "fq2"]].dropna()
    if len(fastqs) == 2:
        return {"r1": fastqs.fq1, "r2": fastqs.fq2}
    return {"r1": fastqs.fq1}

def get_filtered_samples():
    validated_samples = [f.split('/')[-1].split('.')[0] for f in glob.glob("out/validated/*.validated")]
    return validated_samples

    
#FILTERED_SAMPLES = []
#def get_filtered_samples():
#    global FILTERED_SAMPLES
#    if not FILTERED_SAMPLES:
#        with open("out/qc/fastq_filter/samples_pass.csv", 'r') as file:
#            FILTERED_SAMPLES = [line.split(';')[0] for line in file if int(line.split(';')[1].strip()) > 1000]
#    return FILTERED_SAMPLES
