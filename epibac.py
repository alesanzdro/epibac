#!/usr/bin/env python3
"""
EPIBAC: Pipeline para análisis genómico bacteriano.

Este script proporciona una interfaz de línea de comandos para ejecutar
el pipeline EPIBAC, facilitando la instalación, validación y análisis.

Autor: Alejandro Sanz-Carbonell
Versión: 1.1.0
Fecha: 2025
"""

import os
import sys
import argparse
import logging
import subprocess
import re
import shutil
import yaml
from datetime import datetime
from pathlib import Path

# Configuración básica
VERSION = "1.0.0"
SCRIPT_DIR = Path(__file__).parent.absolute()
WORKFLOW_DIR = SCRIPT_DIR / "workflow"
SNAKEFILE = WORKFLOW_DIR / "Snakefile"
DEFAULT_CONFIG = SCRIPT_DIR / "config.yaml"
LOG_DIR = SCRIPT_DIR / "logs"

# Asegurar directorio de logs
LOG_DIR.mkdir(exist_ok=True)


def setup_logging(verbose=False):
    """
    Configura el sistema de logging.

    Args:
        verbose (bool): Si es True, establece el nivel de log a DEBUG.
                        Si es False, establece el nivel a INFO.

    Returns:
        Logger: Objeto logger configurado.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"epibac_{timestamp}.log"

    # Configurar logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("epibac")


class EpibacRunner:
    """Clase principal para ejecutar el pipeline EPIBAC."""

    def __init__(self, args):
        """
        Inicializa el runner con los argumentos de línea de comandos.

        Args:
            args: Argumentos de línea de comandos parseados.
        """
        self.args = args
        self.logger = setup_logging(args.verbose)
        self.config_file = args.config or DEFAULT_CONFIG

    def run(self):
        """
        Ejecuta el comando especificado.

        Returns:
            int: Código de salida. 0 si éxito, otro valor si error.
        """
        command = self.args.command

        self.logger.info(f"Ejecutando comando: {command}")

        # Verificar dependencias antes de ejecutar cualquier comando
        if not self.check_dependencies():
            return 1

        if command == "setup":
            return self.setup()
        elif command == "validate":
            return self.validate()
        elif command == "run":
            return self.run_analysis()
        elif command == "clean":
            return self.clean()
        elif command == "samplesinfo":
            return self.samplesinfo()
        elif command == "check":
            return self.check_structure()
        else:
            self.logger.error(f"Comando desconocido: {command}")
            return 1

    def check_dependencies(self):
        """
        Verifica que todas las dependencias necesarias estén instaladas.

        Returns:
            bool: True si todas las dependencias están instaladas, False en caso contrario.
        """
        self.logger.info("Comprobando dependencias...")

        deps = {
            "snakemake": "snakemake --version",
            "conda": "conda --version" if self.args.conda else None,
            "singularity": "singularity --version" if self.args.singularity else None,
        }

        missing = []
        for name, cmd in deps.items():
            if cmd is None:
                continue
            try:
                subprocess.run(
                    cmd.split(),
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.logger.debug(f"✓ {name} instalado correctamente")
            except (subprocess.SubprocessError, FileNotFoundError):
                missing.append(name)
                self.logger.error(f"✗ {name} no encontrado o no funciona correctamente")

        if missing:
            self.logger.error(f"Dependencias faltantes: {', '.join(missing)}")
            self.logger.error(
                "Por favor, instala las dependencias faltantes antes de continuar"
            )
            return False

        self.logger.info("Todas las dependencias están instaladas correctamente")
        return True

    def check_structure(self):
        """
        Verifica la estructura del proyecto.

        Returns:
            int: 0 si la estructura es correcta, 1 en caso contrario.
        """
        self.logger.info("Verificando estructura del proyecto...")

        # Directorios requeridos
        required_dirs = [
            WORKFLOW_DIR,
            WORKFLOW_DIR / "rules",
            WORKFLOW_DIR / "envs",
            WORKFLOW_DIR / "scripts",
            WORKFLOW_DIR / "schemas",
            SCRIPT_DIR / "resources",
            SCRIPT_DIR / "output",
            LOG_DIR,
        ]

        # Archivos requeridos
        required_files = [
            SNAKEFILE,
            DEFAULT_CONFIG,
            WORKFLOW_DIR / "schemas" / "config.schema.yaml",
            WORKFLOW_DIR / "schemas" / "samples.schema.yaml",
        ]

        # Verificar directorios
        for directory in required_dirs:
            if not directory.exists():
                self.logger.error(f"Directorio requerido no encontrado: {directory}")
                return 1

        # Verificar archivos
        for file_path in required_files:
            if not file_path.exists():
                self.logger.error(f"Archivo requerido no encontrado: {file_path}")
                return 1

        # Verificar permisos de ejecución
        if not os.access(str(__file__), os.X_OK):
            self.logger.warning("El script principal no tiene permisos de ejecución")
            self.logger.warning(f"Ejecuta: chmod +x {__file__}")

        # Verificar permisos de los scripts en workflow/scripts
        for script in (WORKFLOW_DIR / "scripts").glob("*.py"):
            if not os.access(str(script), os.X_OK):
                self.logger.warning(f"Script sin permisos de ejecución: {script}")
                self.logger.warning(f"Ejecuta: chmod +x {script}")

        self.logger.info("✓ Estructura del proyecto verificada correctamente")
        return 0

    def run_snakemake(self, targets, extra_config=None, extra_args=None):
        """
        Ejecuta Snakemake con los parámetros adecuados.
        
        Args:
            targets (list): Objetivos de Snakemake a ejecutar.
            extra_config (list, optional): Configuraciones adicionales.
            extra_args (list, optional): Argumentos adicionales para Snakemake.
        
        Returns:
            int: Código de salida de Snakemake.
        """
        cmd = ["snakemake", "--snakefile", str(SNAKEFILE)]
        
        # Configurar entorno de ejecución
        if self.args.conda:
            cmd.extend(["--use-conda"])
        elif self.args.singularity:
            cmd.extend([
                "--use-apptainer",
                "--apptainer-prefix", str(SCRIPT_DIR / "resources" / "singularity_images"),
            ])
            
            # Añadir argumentos de proxy solo si se especificó
            if self.args.proxy:
                cmd.extend(["--singularity-args", 
                        f"-B {SCRIPT_DIR} --env http_proxy={self.args.proxy} --env https_proxy={self.args.proxy}"])
            else:
                cmd.extend(["--singularity-args", f"-B {SCRIPT_DIR}"])
        
        # Agregar opciones comunes
        cmd.extend(["--cores", str(self.args.threads)])
        cmd.extend(["--configfile", str(self.config_file)])
        
        # Agregar configuración adicional
        config_args = []
        if self.args.samples:
            samples_path = os.path.abspath(self.args.samples)
            config_args.append(f"samples={samples_path}")
        if self.args.outdir:
            outdir_path = os.path.abspath(self.args.outdir)
            config_args.append(f"outdir={outdir_path}")
        if self.args.run_name:
            config_args.append(f"run_name={self.args.run_name}")
        if self.args.mode:
            config_args.append(f"mode={self.args.mode}")
        if extra_config:
            config_args.extend(extra_config)
        
        # Añadir opciones de configuración si existen
        if config_args:
            cmd.append("--config")
            cmd.extend(config_args)
        
        # Agregar argumentos adicionales
        if extra_args:
            cmd.extend(extra_args)
        
        # IMPORTANTE: Separar config de targets con --
        cmd.append("--")
        
        # Agregar targets como argumentos separados al final
        cmd.extend(targets)
        
        # Log y ejecutar
        cmd_str = " ".join(cmd)
        self.logger.debug(f"Ejecutando: {cmd_str}")
        if self.args.dry_run:
            self.logger.info(f"[DRY RUN] Comando: {cmd_str}")
            return 0
        
        try:
            result = subprocess.run(cmd, check=True)
            return result.returncode
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error al ejecutar Snakemake: {e}")
            return e.returncode
    
    def setup(self):
        """
        Configura las bases de datos necesarias.

        Returns:
            int: 0 si éxito, otro valor si error.
        """
        self.logger.info("Instalando bases de datos...")

        # Determinar qué bases de datos instalar
        targets = []
        if not self.args.skip_prokka:
            targets.append("setup_prokka_database")
        if not self.args.skip_amrfinder:
            targets.append("setup_amrfinder_database")
        if not self.args.skip_kraken2:
            targets.append("setup_kraken2_database")
        if not self.args.skip_resfinder:
            targets.append("setup_resfinder_database")

        if not targets:
            self.logger.warning("No se seleccionó ninguna base de datos para instalar")
            return 0

        return self.run_snakemake(targets, extra_args=["--rerun-incomplete"])

    def validate(self):
        """
        Valida el archivo de muestras de forma interactiva.

        Returns:
            int: 0 si el archivo es válido, 1 en caso contrario.
        """
        if not self.args.samples:
            self.logger.error("Debe especificar un archivo de muestras con --samples")
            return 1

        # Importar validador
        sys.path.append(str(SCRIPT_DIR / "workflow" / "scripts"))
        try:
            from validate_samples_file import validate_samples, print_validation_result
        except ImportError:
            self.logger.error("No se pudo importar el módulo de validación. Asegúrate de que el archivo validate_samples_file.py existe en workflow/scripts/")
            return 1
        
        # Cargar config (usando el atributo config_file en lugar de un método)
        try:
            with open(self.config_file, "r") as f:
                config = yaml.safe_load(f)
                if self.args.mode:  # Sobrescribir modo si se especificó
                    config["mode"] = self.args.mode
        except Exception as e:
            self.logger.error(f"Error al cargar la configuración: {e}")
            return 1
        
        self.logger.info("Validando archivo de muestras...")
        result = validate_samples(self.args.samples, config, mode=self.args.mode)
        
        # Mostrar resultados
        print_validation_result(result)
        
        # Guardar archivo validado si no hay errores fatales
        if result["status"] < 3 and self.args.outdir and result["validated_df"] is not None:
            outfile = os.path.join(self.args.outdir, "samples_info_validated.csv")
            report_file = os.path.join(self.args.outdir, "samples_validation_report.txt")
            
            try:
                # Crear directorio si no existe
                os.makedirs(os.path.dirname(os.path.abspath(outfile)), exist_ok=True)
                
                # Guardar archivo validado
                result["validated_df"].to_csv(outfile, index=False, sep=result["separator"])
                self.logger.info(f"Archivo validado guardado en: {outfile}")
                
                # Guardar reporte
                with open(report_file, "w") as f:
                    if result["fatal_errors"]:
                        f.write("===== ERRORES FATALES =====\n")
                        for error in result["fatal_errors"]:
                            f.write(f"{error}\n")
                        f.write("\n")
                    
                    if result["errors"]:
                        f.write("===== ERRORES =====\n")
                        for error in result["errors"]:
                            f.write(f"{error}\n")
                        f.write("\n")
                    
                    if result["warnings"]:
                        f.write("===== ADVERTENCIAS =====\n")
                        for warning in result["warnings"]:
                            f.write(f"{warning}\n")
                        f.write("\n")
                
                self.logger.info(f"Reporte de validación guardado en: {report_file}")
                
            except Exception as e:
                self.logger.error(f"Error al guardar archivo validado: {e}")
                return 1
        
        # Solo considerar exitoso si no hay errores (advertencias están bien)
        return 0 if result["status"] < 2 else 1

    def run_analysis(self):
        """
        Ejecuta el análisis completo.

        Returns:
            int: 0 si el análisis se completa con éxito, 1 en caso contrario.
        """
        if not self.args.samples:
            self.logger.error("Debe especificar un archivo de muestras con --samples")
            return 1

        if not self.args.outdir:
            self.logger.error("Debe especificar un directorio de salida con --outdir")
            return 1

        # Validar run_name para modo GVA
        if self.args.mode == "gva" and self.args.run_name:
            pattern = re.compile(r"^\d{6}_[A-Z]{4}\d{3}$")
            if not pattern.match(self.args.run_name):
                self.logger.error(
                    "En modo GVA, run_name debe seguir el formato AAMMDD_HOSPXXX"
                )
                self.logger.error("Ejemplo: 230512_ALIC001")
                return 1

        # Opciones adicionales
        extra_args = []
        if self.args.resume:
            extra_args.append("--rerun-incomplete")

        self.logger.info("Ejecutando análisis completo...")
        return self.run_snakemake(["all"], None, extra_args)

    def clean(self):
        """
        Limpia archivos temporales.

        Returns:
            int: 0 si la limpieza se completa con éxito.
        """
        if self.args.logs:
            self.logger.info("Limpiando logs...")
            log_files = list(LOG_DIR.glob("*.log"))
            for log_file in log_files:
                log_file.unlink()
            self.logger.info(f"Eliminados {len(log_files)} archivos de log")
        else:
            self.logger.info("Limpiando archivos temporales...")
            # Eliminar archivos temporales de Snakemake
            snakemake_dirs = list(SCRIPT_DIR.glob(".snakemake*"))
            for sdir in snakemake_dirs:
                shutil.rmtree(sdir, ignore_errors=True)

            if self.args.all:
                self.logger.info("Limpiando bases de datos y cachés...")
                # Eliminar imágenes de Singularity
                singularity_dir = SCRIPT_DIR / "resources" / "singularity_images"
                if singularity_dir.exists():
                    shutil.rmtree(singularity_dir, ignore_errors=True)

                # Dar opción al usuario de eliminar bases de datos
                db_dir = SCRIPT_DIR / "resources" / "databases"
                if db_dir.exists() and db_dir.is_dir():
                    response = input(
                        "¿Desea eliminar también las bases de datos descargadas? [y/N]: "
                    )
                    if response.lower() == "y":
                        self.logger.info("Eliminando bases de datos...")
                        shutil.rmtree(db_dir, ignore_errors=True)

        self.logger.info("Limpieza completada.")
        return 0

    def samplesinfo(self):
        """
        Genera el archivo samples_info.csv a partir de archivos FASTQ.
        Esta función usa el script build_samplesinfo.py del directorio workflow/scripts.

        Returns:
            int: 0 si la generación se completa con éxito, 1 en caso contrario.
        """
        # Verificar parámetros requeridos
        if not self.args.run_name:
            self.logger.error("Debe especificar el nombre de la carrera con --run-name")
            return 1

        if not self.args.platform:
            self.logger.error("Debe especificar la plataforma con --platform")
            return 1

        if not self.args.fastq:
            self.logger.error(
                "Debe especificar el directorio de archivos FASTQ con --fastq"
            )
            return 1

        # Validar el nombre de carrera en modo GVA
        if self.args.mode == "gva":
            pattern = re.compile(r"^\d{6}_[A-Z]{4}\d{3}$")
            if not pattern.match(self.args.run_name):
                self.logger.error(
                    "En modo GVA, el nombre de carrera debe seguir el formato AAMMDD_HOSPXXX"
                )
                self.logger.error("Ejemplo: 230512_ALIC001")
                return 1

        # Verificar que el directorio de fastq existe
        if not os.path.exists(self.args.fastq):
            self.logger.error(f"Error: El directorio {self.args.fastq} no existe")
            return 1

        # Si se especificó directorio de salida, verificar que existe
        if self.args.output and not os.path.exists(self.args.output):
            try:
                os.makedirs(self.args.output)
            except Exception as e:
                self.logger.error(f"Error al crear el directorio de salida: {e}")
                return 1

        # Construir comando
        build_script = WORKFLOW_DIR / "scripts" / "build_samplesinfo.py"
        if not build_script.exists():
            self.logger.error(f"Error: No se encontró el script {build_script}")
            return 1

        cmd = [
            sys.executable,
            str(build_script),
            "--mode",
            self.args.mode,
            "--run-name",
            self.args.run_name,
            "--platform",
            self.args.platform,
            "--fastq",
            self.args.fastq,
        ]

        if self.args.output:
            cmd.extend(["--output", self.args.output])

        # Ejecutar comando
        self.logger.info(f"Ejecutando: {' '.join(cmd)}")
        if self.args.dry_run:
            self.logger.info(f"[DRY RUN] Comando: {' '.join(cmd)}")
            return 0

        try:
            result = subprocess.run(cmd, check=True)
            if result.returncode == 0:
                output_dir = (
                    self.args.output
                    if self.args.output
                    else os.path.dirname(os.path.abspath(self.args.fastq))
                )
                output_file = os.path.join(
                    output_dir, f"samples_info_{self.args.run_name}.csv"
                )
                self.logger.info(
                    f"El archivo se ha generado correctamente en: {output_file}"
                )
                self.logger.info("Ahora puedes ejecutar:")
                self.logger.info(
                    f"  epibac.py run --samples {output_file} --outdir results --run-name {self.args.run_name}"
                )
            return result.returncode
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error al ejecutar build_samplesinfo.py: {e}")
            return e.returncode


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="EPIBAC: Pipeline para análisis genómico bacteriano"
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"EPIBAC v{VERSION}"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Mostrar información detallada"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Mostrar comandos sin ejecutar"
    )

    # Opciones de ejecución
    execution = parser.add_mutually_exclusive_group()
    execution.add_argument(
        "--conda", action="store_true", help="Usar entornos conda (por defecto)"
    )
    execution.add_argument(
        "--singularity",
        action="store_true",
        help="Usar contenedores Singularity/Apptainer",
    )

    # Opciones comunes
    parser.add_argument(
        "--threads", type=int, default=4, help="Número de threads (default: 4)"
    )
    parser.add_argument(
        "--config",
        type=str,
        help=f"Archivo de configuración (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument("--samples", type=str, help="Archivo de muestras")
    parser.add_argument("--outdir", type=str, help="Directorio de salida")
    parser.add_argument("--run-name", type=str, help="Nombre de la carrera/experimento")
    parser.add_argument(
        "--mode",
        choices=["gva", "normal"],
        default="gva",
        help="Modo de análisis (default: gva)",
    )
    parser.add_argument(
        "--proxy", type=str, help="URL del proxy (ej: http://proxy.ejemplo.com:8080)"
    )

    # Subparsers para comandos específicos
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # Comando: check
    subparsers.add_parser(
        "check", help="Verificar estructura del proyecto y dependencias"
    )

    # Comando: setup
    setup_parser = subparsers.add_parser(
        "setup", help="Instalar y configurar bases de datos"
    )
    setup_parser.add_argument(
        "--skip-prokka",
        action="store_true",
        help="Omitir instalación de bases de datos para Prokka",
    )
    setup_parser.add_argument(
        "--skip-amrfinder",
        action="store_true",
        help="Omitir instalación de bases de datos para AMRFinder",
    )
    setup_parser.add_argument(
        "--skip-kraken2",
        action="store_true",
        help="Omitir instalación de bases de datos para Kraken2",
    )
    setup_parser.add_argument(
        "--skip-resfinder",
        action="store_true",
        help="Omitir instalación de bases de datos para ResFinder",
    )

    # Comando: validate
    subparsers.add_parser(
        "validate", help="Validar archivo de muestras"
    )

    # Comando: run
    run_parser = subparsers.add_parser("run", help="Ejecutar análisis completo")
    run_parser.add_argument(
        "--resume", action="store_true", help="Continuar análisis previo interrumpido"
    )

    # Comando: clean
    clean_parser = subparsers.add_parser("clean", help="Limpiar archivos temporales")
    clean_parser.add_argument(
        "--all", action="store_true", help="Eliminar también bases de datos instaladas"
    )
    clean_parser.add_argument(
        "--logs", action="store_true", help="Eliminar solo archivos de log"
    )

    # Comando: samplesinfo
    samplesinfo_parser = subparsers.add_parser(
        "samplesinfo",
        help="Generar archivo samples_info.csv a partir de archivos FASTQ",
    )
    samplesinfo_parser.add_argument(
        "--fastq", "-f", required=True, help="Ruta al directorio con archivos FASTQ"
    )
    samplesinfo_parser.add_argument(
        "--platform",
        "-p",
        choices=["illumina", "nanopore"],
        required=True,
        help="Plataforma de secuenciación (illumina o nanopore)",
    )
    samplesinfo_parser.add_argument(
        "--output",
        "-o",
        help="Ruta de salida para el archivo (por defecto: directorio padre del directorio fastq)",
    )

    args = parser.parse_args()

    # Validar que se haya proporcionado un comando
    if not args.command:
        parser.print_help()
        return 1

    # Por defecto usar conda si no se especifica
    if not args.conda and not args.singularity:
        args.conda = True

    # Ejecutar el comando
    runner = EpibacRunner(args)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
