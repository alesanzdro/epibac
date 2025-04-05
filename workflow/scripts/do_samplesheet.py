import os
import pandas as pd
import argparse

# python scripts/do_samplesheet.py RAW/230901_LSPV013/LSPV013/ samplesheet-LSPV013.csv


def create_samplesheet(input_directory, output_file):
    files = os.listdir(input_directory)
    data = []

    for file in files:
        if any(word in file for word in ["SALM", "LMON", "CAMP", "CNP"]):
            sample_id = file.split("_")
            if "CNP" in file:
                sample = "_".join(sample_id[:2])
                r_type = sample_id[3].split(".")[0]
            else:
                sample = "_".join(sample_id[:3])
                r_type = sample_id[4].split(".")[0]

            path = os.path.join(input_directory, file)
            data.append((sample, r_type, path))

    df = pd.DataFrame(data, columns=["sample", "r_type", "path"])
    df_pivot = df.pivot(index="sample", columns="r_type", values="path").reset_index()
    df_pivot.columns.name = ""
    df_pivot.columns = ["sample", "fq1", "fq2"]

    df_pivot.to_csv(output_file, index=False, sep="\t")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a samplesheet from fastq files"
    )
    parser.add_argument(
        "input_directory", help="Input directory containing the fastq files"
    )
    parser.add_argument("output_file", help="Output file name for the samplesheet")

    args = parser.parse_args()

    create_samplesheet(args.input_directory, args.output_file)
