import os
import sys
import re
import argparse
import glob
from pathlib import Path
from collections import defaultdict


def parse_arguments():
    """Parse los argumentos de la línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Genera el archivo samplesinfo.csv para EPIBAC."
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["gva", "normal"],
        required=True,
        help="Modo de análisis: gva o normal",
    )
    parser.add_argument(
        "--run_name",
        "-r",
        required=True,
        help="Nombre de la carrera (ej: 250319_ALIC991)",
    )
    parser.add_argument(
        "--platform",
        "-p",
        choices=["illumina", "nanopore"],
        required=True,
        help="Plataforma de secuenciación: illumina o nanopore",
    )
    parser.add_argument(
        "--fastq", "-f", required=True, help="Ruta al directorio con archivos FASTQ"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Ruta de salida para el archivo samplesinfo.csv (por defecto: directorio padre del directorio de fastq)",
    )

    return parser.parse_args()


def find_fastq_files(fastq_dir, platform):
    """
    Busca los archivos FASTQ en el directorio especificado
    según la plataforma.
    """
    if not os.path.exists(fastq_dir):
        print(f"Error: El directorio {fastq_dir} no existe.")
        sys.exit(1)

    # Extensiones comunes para archivos FASTQ
    extensions = [".fastq.gz", ".fastq", ".fq.gz", ".fq"]

    # Recopilar todos los archivos FASTQ en el directorio
    fastq_files = []
    for ext in extensions:
        fastq_files.extend(glob.glob(os.path.join(fastq_dir, f"*{ext}")))

    if not fastq_files:
        print(f"Error: No se encontraron archivos FASTQ en {fastq_dir}")
        sys.exit(1)

    return fastq_files


def extract_sample_id_illumina(fastq_file):
    """
    Extrae el ID de la muestra de un archivo FASTQ de Illumina.
    Busca patrones comunes como _S1_R1, _S1_R2, etc.
    """
    basename = os.path.basename(fastq_file)

    # Intentar varios patrones comunes para archivos Illumina
    patterns = [
        r"^(.+?)_S\d+_R[12](?:_001)?\.f(?:ast)?q(?:\.gz)?$",  # Sample_S1_R1_001.fastq.gz
        r"^(.+?)_R[12](?:_001)?\.f(?:ast)?q(?:\.gz)?$",  # Sample_R1_001.fastq.gz
        r"^(.+?)_r[12](?:_001)?\.f(?:ast)?q(?:\.gz)?$",  # Sample_r1_001.fastq.gz
        r"^(.+?)\.R[12]\.f(?:ast)?q(?:\.gz)?$",  # Sample.R1.fastq.gz
        r"^(.+?)\.r[12]\.f(?:ast)?q(?:\.gz)?$",  # Sample.r1.fastq.gz
        r"^(.+?)_[FR]\.f(?:ast)?q(?:\.gz)?$",  # Sample_F.fastq.gz o Sample_R.fastq.gz
    ]

    for pattern in patterns:
        match = re.match(pattern, basename)
        if match:
            return match.group(1)

    # Si no coincide con ningún patrón conocido, devolver el nombre sin extensión
    # como último recurso
    print(
        f"Advertencia: No se pudo identificar patrón estándar en {basename}, usando nombre de archivo"
    )
    return os.path.splitext(basename)[0].split(".")[0]  # Eliminar todas las extensiones


def extract_sample_id_nanopore(fastq_file):
    """
    Extrae el ID de la muestra de un archivo FASTQ de Nanopore.
    """
    basename = os.path.basename(fastq_file)

    # Para Nanopore, simplemente eliminamos extensiones comunes
    for ext in [".fastq.gz", ".fastq", ".fq.gz", ".fq"]:
        if basename.endswith(ext):
            return basename[: -len(ext)]

    # Si no coincide con ninguna extensión conocida
    return basename


def group_illumina_pairs(fastq_files):
    """
    Agrupa archivos FASTQ de Illumina por pares R1/R2.
    Devuelve un diccionario: {sample_id: {"R1": path, "R2": path}}
    """
    samples = defaultdict(dict)

    for fastq_file in fastq_files:
        basename = os.path.basename(fastq_file)

        # Determinar si es R1 o R2
        if (
            re.search(r"_R1(?:_001)?\.f(?:ast)?q(?:\.gz)?$", basename, re.IGNORECASE)
            or re.search(r"_r1(?:_001)?\.f(?:ast)?q(?:\.gz)?$", basename, re.IGNORECASE)
            or re.search(r"\.R1\.f(?:ast)?q(?:\.gz)?$", basename, re.IGNORECASE)
            or re.search(r"\.r1\.f(?:ast)?q(?:\.gz)?$", basename, re.IGNORECASE)
            or re.search(r"_F\.f(?:ast)?q(?:\.gz)?$", basename, re.IGNORECASE)
        ):
            read = "R1"
        elif (
            re.search(r"_R2(?:_001)?\.f(?:ast)?q(?:\.gz)?$", basename, re.IGNORECASE)
            or re.search(r"_r2(?:_001)?\.f(?:ast)?q(?:\.gz)?$", basename, re.IGNORECASE)
            or re.search(r"\.R2\.f(?:ast)?q(?:\.gz)?$", basename, re.IGNORECASE)
            or re.search(r"\.r2\.f(?:ast)?q(?:\.gz)?$", basename, re.IGNORECASE)
            or re.search(r"_R\.f(?:ast)?q(?:\.gz)?$", basename, re.IGNORECASE)
        ):
            read = "R2"
        else:
            print(
                f"Advertencia: No se pudo determinar si '{basename}' es R1 o R2. Ignorando."
            )
            continue

        # Extraer ID de la muestra
        sample_id = extract_sample_id_illumina(fastq_file)

        # Guardar ruta absoluta
        samples[sample_id][read] = os.path.abspath(fastq_file)

    return samples


def create_samplesinfo(args):
    """
    Crea el archivo samplesinfo.csv según el modo y la plataforma.
    """
    fastq_files = find_fastq_files(args.fastq, args.platform)

    # Determinar la ruta de salida (un nivel arriba del directorio fastq si no se especifica)
    if args.output:
        output_dir = args.output
    else:
        # Obtener el directorio padre del directorio fastq
        output_dir = os.path.dirname(os.path.abspath(args.fastq))

    # Usar el formato samplesinfo_NOMBRE_CARRERA.csv
    output_file = os.path.join(output_dir, f"samplesinfo_{args.run_name}.csv")

    if args.platform == "illumina":
        # Agrupar archivos por pares R1/R2
        samples = group_illumina_pairs(fastq_files)

        # Verificar que cada muestra tenga ambos archivos R1 y R2
        incomplete_samples = [
            sample_id
            for sample_id, reads in samples.items()
            if not ("R1" in reads and "R2" in reads)
        ]

        if incomplete_samples:
            print("Error: Las siguientes muestras no tienen ambos archivos R1 y R2:")
            for sample_id in incomplete_samples:
                r1 = samples[sample_id].get("R1", "Falta R1")
                r2 = samples[sample_id].get("R2", "Falta R2")
                print(f"  {sample_id}: {r1}, {r2}")
            sys.exit(1)

        # Generar CSV según el modo
        with open(output_file, "w") as f:
            if args.mode == "gva":
                # Cabecera modo GVA
                f.write(
                    "CODIGO_MUESTRA_ORIGEN;PETICION;FECHA_TOMA_MUESTRA;ESPECIE_SECUENCIA;MOTIVO_WGS;NUM_BROTE;CONFIRMACION;COMENTARIO_WGS;ILLUMINA_R1;ILLUMINA_R2;NANOPORE\n"
                )

                # Datos de las muestras
                for sample_id, reads in samples.items():
                    f.write(f"{sample_id};;;;;;;" f";{reads['R1']};{reads['R2']};\n")

            else:  # modo normal
                # Cabecera modo normal
                f.write("id;collection_date;organism;illumina_r1;illumina_r2;ont\n")

                # Datos de las muestras
                for sample_id, reads in samples.items():
                    f.write(f"{sample_id};;;" f"{reads['R1']};{reads['R2']};\n")

    else:  # nanopore
        # Para Nanopore, cada archivo es una muestra
        sample_files = {}
        for fastq_file in fastq_files:
            sample_id = extract_sample_id_nanopore(fastq_file)
            sample_files[sample_id] = os.path.abspath(fastq_file)

        # Generar CSV según el modo
        with open(output_file, "w") as f:
            if args.mode == "gva":
                # Cabecera modo GVA
                f.write(
                    "CODIGO_MUESTRA_ORIGEN;PETICION;FECHA_TOMA_MUESTRA;ESPECIE_SECUENCIA;MOTIVO_WGS;NUM_BROTE;CONFIRMACION;COMENTARIO_WGS;ILLUMINA_R1;ILLUMINA_R2;NANOPORE\n"
                )

                # Datos de las muestras
                for sample_id, fastq_path in sample_files.items():
                    f.write(f"{sample_id};;;;;;;" f";;{fastq_path}\n")

            else:  # modo normal
                # Cabecera modo normal
                f.write("id;collection_date;organism;illumina_r1;illumina_r2;ont\n")

                # Datos de las muestras
                for sample_id, fastq_path in sample_files.items():
                    f.write(f"{sample_id};;;" f";;{fastq_path}\n")

    print(f"Archivo samplesinfo creado exitosamente: {output_file}")
    print(
        f"Se encontraron {len(samples if args.platform == 'illumina' else sample_files)} muestras."
    )

    return output_file


def validate_run_name(run_name, mode):
    """Valida que el nombre de carrera tenga el formato correcto en modo GVA."""
    if mode == "gva":
        pattern = r"^\d{6}_[A-Z]{4}\d{3}$"
        if not re.match(pattern, run_name):
            print(
                f"Error: En modo GVA, el nombre de carrera debe seguir el formato AAMMDD_HOSPXXX"
            )
            print(f"  Ejemplo: 230512_ALIC001")
            print(f"  Valor actual: {run_name}")
            return False
    return True


def main():
    """Función principal."""
    args = parse_arguments()

    # Validar el nombre de carrera en modo GVA
    if not validate_run_name(args.run_name, args.mode):
        sys.exit(1)

    # Verificar que el directorio de fastq existe
    if not os.path.exists(args.fastq):
        print(f"Error: El directorio {args.fastq} no existe")
        sys.exit(1)

    # Si se especificó directorio de salida, verificar que existe
    if args.output and not os.path.exists(args.output):
        try:
            os.makedirs(args.output)
        except Exception as e:
            print(f"Error al crear el directorio de salida: {e}")
            sys.exit(1)

    # Crear el archivo samplesinfo.csv
    output_file = create_samplesinfo(args)

    print(f"El archivo se ha generado correctamente en: {output_file}")
    print(f"Ahora puedes ejecutar:")
    print(
        f"  epibac.py run --samples {output_file} --outdir results --run-name {args.run_name} --mode {args.mode}"
    )


if __name__ == "__main__":
    main()
