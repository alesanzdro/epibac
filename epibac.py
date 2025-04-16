#!/usr/bin/env python3
"""
EPIBAC: Pipeline for bacterial genomic analysis.

This script provides a command-line interface to run
the EPIBAC pipeline, facilitating installation, validation, and analysis.

Author: Alejandro Sanz-Carbonell
Version: 1.1.0
Date: 2025
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

# Basic configuration
VERSION = "1.0.0"
SCRIPT_DIR = Path(__file__).parent.absolute()
WORKFLOW_DIR = SCRIPT_DIR / "workflow"
SNAKEFILE = WORKFLOW_DIR / "Snakefile"
DEFAULT_CONFIG = SCRIPT_DIR / "config.yaml"
LOG_DIR = SCRIPT_DIR / "logs"

# Ensure log directory exists
LOG_DIR.mkdir(exist_ok=True)


def setup_logging(verbose=False):
    """
    Configures the logging system.

    Args:
        verbose (bool): If True, sets the log level to DEBUG.
                        If False, sets the level to INFO.

    Returns:
        Logger: Configured logger object.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"epibac_{timestamp}.log"

    # Configure logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("epibac")


class EpibacRunner:
    """Main class to run the EPIBAC pipeline."""

    def __init__(self, args):
        """
        Initializes the runner with command-line arguments.

        Args:
            args: Parsed command-line arguments.
        """
        self.args = args
        self.logger = setup_logging(args.verbose)
        self.config_file = args.config or DEFAULT_CONFIG
        self.conda_path = "conda"  # Default value
    
    def run(self):
        """
        Executes the specified command.

        Returns:
            int: Exit code. 0 if successful, otherwise an error code.
        """
        command = self.args.command

        self.logger.info(f"Executing command: {command}")

        # Verify dependencies before executing any command
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
            self.logger.error(f"Unknown command: {command}")
            return 1
        
    def check_conda_available(self):
        """
        Checks if conda is available on the system, even if it's not in the PATH.
        
        Returns:
            tuple: (bool, str) - (True if conda is available, path to the conda executable)
        """
        self.logger.debug("Checking conda availability...")
        
        # 1. Check PATH first (current method)
        try:
            result = subprocess.run(
                ["conda", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.logger.debug(f"Conda found in PATH: {result.stdout.strip()}")
            return True, "conda"
        except (subprocess.SubprocessError, FileNotFoundError):
            self.logger.debug("Conda not found in PATH, searching in alternative locations...")
        
        # 2. Search in typical locations
        home_dir = os.path.expanduser("~")
        common_paths = [
            os.path.join(home_dir, "miniconda3/bin/conda"),
            os.path.join(home_dir, "anaconda3/bin/conda"),
            os.path.join(home_dir, "conda/bin/conda"),
            "/opt/conda/bin/conda",
            "/opt/miniconda3/bin/conda",
            "/opt/anaconda3/bin/conda",
            "/usr/local/miniconda3/bin/conda",
            "/usr/local/anaconda3/bin/conda"
        ]
        
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                try:
                    result = subprocess.run(
                        [path, "--version"],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    self.logger.debug(f"Conda found in {path}: {result.stdout.strip()}")
                    return True, path
                except (subprocess.SubprocessError, FileNotFoundError):
                    self.logger.debug(f"Error executing {path}")
                    continue
        
        # 3. Search for conda.sh as a last resort
        conda_sh_paths = [
            os.path.join(home_dir, "miniconda3/etc/profile.d/conda.sh"),
            os.path.join(home_dir, "anaconda3/etc/profile.d/conda.sh"),
            "/opt/conda/etc/profile.d/conda.sh",
            "/opt/miniconda3/etc/profile.d/conda.sh",
            "/opt/anaconda3/etc/profile.d/conda.sh"
        ]
        
        for path in conda_sh_paths:
            if os.path.exists(path):
                # If we find conda.sh, we assume conda is available
                conda_bin = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(path)), "bin", "conda"))
                if os.path.exists(conda_bin) and os.access(conda_bin, os.X_OK):
                    self.logger.debug(f"Conda found in {conda_bin} (via conda.sh)")
                    return True, conda_bin
        
        self.logger.debug("Conda not found in any common location")
        return False, None

    def check_dependencies(self):
        """
        Checks that all necessary dependencies are installed.
    
        Returns:
            bool: True if all dependencies are installed, False otherwise.
        """
        self.logger.info("Checking dependencies...")
    
        missing = []
        
        # Verify snakemake (always required)
        try:
            subprocess.run(
                ["snakemake", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.logger.debug("✓ snakemake installed correctly")
        except (subprocess.SubprocessError, FileNotFoundError):
            missing.append("snakemake")
            self.logger.error("✗ snakemake not found or not working correctly")
        
        # Verify conda only if --conda is specified
        if self.args.conda:
            conda_available, conda_path = self.check_conda_available()
            if conda_available:
                self.logger.debug(f"✓ conda installed correctly: {conda_path}")
                # Save the path for later use
                self.conda_path = conda_path
            else:
                missing.append("conda")
                self.logger.error("✗ conda not found or not working correctly")
                self.logger.info("If you are using an activated conda environment, make sure the conda executable is available")
        
        # Verify singularity only if --singularity is specified
        if self.args.singularity:
            try:
                subprocess.run(
                    ["singularity", "--version"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.logger.debug("✓ singularity installed correctly")
            except (subprocess.SubprocessError, FileNotFoundError):
                try:
                    # Try with apptainer (the new name for singularity)
                    subprocess.run(
                        ["apptainer", "--version"],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    self.logger.debug("✓ apptainer installed correctly")
                except (subprocess.SubprocessError, FileNotFoundError):
                    missing.append("singularity/apptainer")
                    self.logger.error("✗ singularity/apptainer not found or not working correctly")
    
        if missing:
            self.logger.error(f"Missing dependencies: {', '.join(missing)}")
            self.logger.error(
                "Please install the missing dependencies before continuing"
            )
            return False
    
        self.logger.info("All dependencies are installed correctly")
        return True

    def check_structure(self):
        """
        Verifies the project structure.

        Returns:
            int: 0 if the structure is correct, 1 otherwise.
        """
        self.logger.info("Verifying project structure...")

        # Required directories
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

        # Required files
        required_files = [
            SNAKEFILE,
            DEFAULT_CONFIG,
            WORKFLOW_DIR / "schemas" / "config.schema.yaml",
            WORKFLOW_DIR / "schemas" / "samples.schema.yaml",
        ]

        # Verify directories
        for directory in required_dirs:
            if not directory.exists():
                self.logger.error(f"Required directory not found: {directory}")
                return 1

        # Verify files
        for file_path in required_files:
            if not file_path.exists():
                self.logger.error(f"Required file not found: {file_path}")
                return 1

        # Verify execution permissions
        if not os.access(str(__file__), os.X_OK):
            self.logger.warning("The main script does not have execution permissions")
            self.logger.warning(f"Run: chmod +x {__file__}")

        # Verify permissions of scripts in workflow/scripts
        for script in (WORKFLOW_DIR / "scripts").glob("*.py"):
            if not os.access(str(script), os.X_OK):
                self.logger.warning(f"Script without execution permissions: {script}")
                self.logger.warning(f"Run: chmod +x {script}")

        self.logger.info("✓ Project structure verified correctly")
        return 0

    def get_singularity_args(self):
        """
        Generates the arguments for Singularity/Apptainer based on the configuration.
        
        Returns:
            list: List of arguments formatted for Singularity/Apptainer
        """
        # Initialize argument list
        bind_args = []
        env_args = []
        
        # Add script directory
        bind_args.append(f"{SCRIPT_DIR}")
        
        # Add proxy if configured
        if self.args.proxy:
            env_args.append(f"http_proxy={self.args.proxy}")
            env_args.append(f"https_proxy={self.args.proxy}")
        
        # Add storage_cabinet if we are in gva mode
        try:
            with open(self.config_file, "r") as f:
                config = yaml.safe_load(f)
                
            mode = config.get("mode", "")
            if mode == "gva":
                storage_cabinet = config.get("mode_config", {}).get("gva", {}).get("storage_cabinet", "")
                if storage_cabinet and os.path.exists(storage_cabinet):
                    self.logger.info(f"Adding storage_cabinet to Singularity/Apptainer bind: {storage_cabinet}")
                    bind_args.append(f"{storage_cabinet}")
                else:
                    self.logger.warning(f"Storage cabinet not found or not configured: {storage_cabinet}")
        except Exception as e:
            self.logger.warning(f"Could not get storage_cabinet: {e}")
        
        # Build Singularity options
        singularity_args = []
        
        # Add bind options
        for bind in bind_args:
            singularity_args.extend(["-B", bind])
        
        # Add environment variables
        for env in env_args:
            singularity_args.extend(["--env", env])
        
        return singularity_args

    def run_snakemake(self, targets, extra_config=None, extra_args=None):
        """
        Runs Snakemake with the appropriate parameters.
        
        Args:
            targets (list): Snakemake targets to execute.
            extra_config (list, optional): Additional configurations.
            extra_args (list, optional): Additional arguments for Snakemake.
        
        Returns:
            int: Snakemake exit code.
        """
        cmd = ["snakemake", "--snakefile", str(SNAKEFILE)]
        
        # Configure execution environment
        if self.args.conda:
            cmd.extend(["--use-conda", "--conda-frontend", "mamba"])

            # If conda is found in a specific location, ensure Snakemake uses it
            if hasattr(self, 'conda_path') and self.conda_path != "conda":
                conda_dir = os.path.dirname(self.conda_path)
                cmd.extend([
                    "--conda-prefix", os.path.join(SCRIPT_DIR, "conda_envs"),
                ])
                # Add conda to PATH for Snakemake execution
                os.environ["PATH"] = f"{conda_dir}:{os.environ.get('PATH', '')}"
                self.logger.info(f"Using conda from: {self.conda_path}")
                # Ensure setuptools is installed in the Conda environment
                cmd.extend(["--conda-create-env-args", "--override-channels", "-c", "defaults", "-c", "conda-forge", "setuptools perl perl-list-moreutils perl-list-moreutils-xs"])
                self.logger.info("Ensuring setuptools is installed in the Conda environment")
                
        elif self.args.singularity:
            cmd.extend([
                "--use-apptainer",
                "--apptainer-prefix", str(SCRIPT_DIR / "resources" / "singularity_images"),
            ])
            
            # Use the new method to generate Singularity/Apptainer arguments
            singularity_args = self.get_singularity_args()
            if singularity_args:
                cmd.extend(["--apptainer-args", " ".join(singularity_args)])
        
        # Add common options - use threads instead of cores for consistency
        cmd.extend(["--cores", str(self.args.threads)])
        cmd.extend(["--configfile", str(self.config_file)])
        
        # Add additional configuration - only if the attributes exist
        config_args = []
        # Only access these attributes if they exist (not needed for setup)
        if hasattr(self.args, 'samples') and self.args.samples:
            samples_path = os.path.abspath(self.args.samples)
            config_args.append(f"samples={samples_path}")
        if hasattr(self.args, 'outdir') and self.args.outdir:
            outdir_path = os.path.abspath(self.args.outdir)
            config_args.append(f"outdir={outdir_path}")
            # Automatically add logdir based on outdir
            logdir_path = os.path.join(outdir_path, "logs")
            config_args.append(f"logdir={logdir_path}")
        if hasattr(self.args, 'run_name') and self.args.run_name:
            config_args.append(f"run_name={self.args.run_name}")
        if hasattr(self.args, 'mode') and self.args.mode:
            config_args.append(f"mode={self.args.mode}")
        if extra_config:
            config_args.extend(extra_config)
        
        # Add configuration options if they exist
        if config_args:
            cmd.append("--config")
            cmd.extend(config_args)
        
        # Add additional arguments
        if extra_args:
            cmd.extend(extra_args)
        
        # IMPORTANT: Separate config from targets with --
        cmd.append("--")
        
        # Add targets as separate arguments at the end
        cmd.extend(targets)
        
        # Log and execute
        cmd_str = " ".join(cmd)
        self.logger.debug(f"Executing: {cmd_str}")
        if hasattr(self.args, 'dry_run') and self.args.dry_run:
            self.logger.info(f"[DRY RUN] Command: {cmd_str}")
            return 0
        
        try:
            result = subprocess.run(cmd, check=True)
            return result.returncode
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error executing Snakemake (code {e.returncode}):")
            self.logger.error(f"$ {cmd_str}")
            return e.returncode
    
    def setup(self):
        """
        Configures the necessary databases based on the configuration file.
        
        Databases to skip are controlled via the config.yaml file:
        
        skip:
          prokka: true
          amrfinder: false
          kraken2: false
          resfinder: false
    
        Returns:
            int: 0 if successful, otherwise an error code.
        """
        self.logger.info("Installing databases...")
    
        # Load skip configuration
        config = {}
        try:
            with open(self.config_file, "r") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            self.logger.error(f"Error reading the configuration file: {e}")
        
        # Get skip configuration (by default, skip nothing)
        skip_config = config.get("skip", {})
        
        # Determine which databases to install
        targets = []
     
        # Add targets based on the configuration
        if not skip_config.get("prokka", False):
            targets.append("setup_prokka_database")
            self.logger.info("✓ Prokka database will be installed")
        else:
            self.logger.info("✗ Skipping Prokka database installation")
     
        if not skip_config.get("amrfinder", False):
            targets.append("setup_amrfinder_database")
            self.logger.info("✓ AMRFinder database will be installed")
        else:
            self.logger.info("✗ Skipping AMRFinder database installation")
     
        if not skip_config.get("kraken2", False):
            targets.append("setup_kraken2_database")
            self.logger.info("✓ Kraken2 database will be installed")
        else:
            self.logger.info("✗ Skipping Kraken2 database installation")
     
        if not skip_config.get("resfinder", False):
            targets.append("setup_resfinder_database")
            self.logger.info("✓ ResFinder database will be installed")
        else:
            self.logger.info("✗ Skipping ResFinder database installation")
    
        if not targets:
            self.logger.warning("No database selected for installation")
            self.logger.info("Check the 'skip' configuration in your config.yaml file")
            return 0
     
        return self.run_snakemake(targets, extra_args=["--rerun-incomplete"])

    def validate(self):
     """
     Validates the sample file interactively.

     Returns:
         int: 0 if the file is valid, 1 otherwise.
     """
     if not self.args.samples:
         self.logger.error("You must specify a sample file with --samples")
         return 1

     # Import validator
     sys.path.append(str(SCRIPT_DIR / "workflow" / "scripts"))
     try:
         from validate_samples_file import validate_samples, print_validation_result
     except ImportError:
         self.logger.error("Could not import the validation module. Make sure the file validate_samples_file.py exists in workflow/scripts/")
         return 1
     
     # Load config (using the config_file attribute instead of a method)
     try:
         with open(self.config_file, "r") as f:
          config = yaml.safe_load(f)
          if self.args.mode:  # Override mode if specified
              config["mode"] = self.args.mode
     except Exception as e:
         self.logger.error(f"Error loading configuration: {e}")
         return 1
     
     self.logger.info("Validating sample file...")
     result = validate_samples(self.args.samples, config, mode=self.args.mode)
     
     # Show results
     print_validation_result(result)
     
     # Save validated file if there are no fatal errors
     if result["status"] < 3 and self.args.outdir and result["validated_df"] is not None:
         # Create logs/samplesinfo subdirectory
         logs_dir = os.path.join(self.args.outdir, "logs", "samplesinfo")
         os.makedirs(logs_dir, exist_ok=True)
         
         # New file paths
         outfile = os.path.join(logs_dir, "samplesinfo_validated.csv")
         report_file = os.path.join(logs_dir, "samplesvalidation_report.txt")
         
         try:
          # Save validated file
          result["validated_df"].to_csv(outfile, index=False, sep=result["separator"])
          self.logger.info(f"Validated file saved to: {outfile}")
          
          # Save report
          with open(report_file, "w") as f:
              if result["fatal_errors"]:
               f.write("===== FATAL ERRORS =====\n")
               for error in result["fatal_errors"]:
                f.write(f"{error}\n")
               f.write("\n")
              
              if result["errors"]:
               f.write("===== ERRORS =====\n")
               for error in result["errors"]:
                f.write(f"{error}\n")
               f.write("\n")
              
              if result["warnings"]:
               f.write("===== WARNINGS =====\n")
               for warning in result["warnings"]:
                f.write(f"{warning}\n")
               f.write("\n")
          
          self.logger.info(f"Validation report saved to: {report_file}")
          
         except Exception as e:
          self.logger.error(f"Error saving validated file: {e}")
          return 1
     
     # Only consider successful if there are no errors (warnings are okay)
     return 0 if result["status"] < 2 else 1

    def run_analysis(self):
     """
     Executes the complete analysis.

     Returns:
         int: 0 if the analysis completes successfully, 1 otherwise.
     """
     if not self.args.samples:
         self.logger.error("You must specify a sample file with --samples")
         return 1

     if not self.args.outdir:
         self.logger.error("You must specify an output directory with --outdir")
         return 1

     # Validate run_name for GVA mode
     if self.args.mode == "gva" and self.args.run_name:
         pattern = re.compile(r"^\d{6}_[A-Z]{4}\d{3}$")
         if not pattern.match(self.args.run_name):
          self.logger.error(
              "In GVA mode, run_name must follow the format AAMMDD_HOSPXXX"
          )
          self.logger.error("Example: 230512_ALIC001")
          return 1

     # Additional options
     extra_args = []
     if self.args.resume:
         extra_args.append("--rerun-incomplete")

     self.logger.info("Running complete analysis...")
     return self.run_snakemake(["all"], None, extra_args)

    def clean(self):
     """
     Cleans temporary files.

     Returns:
         int: 0 if cleaning completes successfully.
     """
     if self.args.logs:
         self.logger.info("Cleaning logs...")
         log_files = list(LOG_DIR.glob("*.log"))
         for log_file in log_files:
          log_file.unlink()
         self.logger.info(f"Deleted {len(log_files)} log files")
     else:
         self.logger.info("Cleaning temporary files...")
         # Delete Snakemake temporary files
         snakemake_dirs = list(SCRIPT_DIR.glob(".snakemake*"))
         for sdir in snakemake_dirs:
          shutil.rmtree(sdir, ignore_errors=True)

         if self.args.all:
          self.logger.info("Cleaning databases and caches...")
          # Delete Singularity images
          singularity_dir = SCRIPT_DIR / "resources" / "singularity_images"
          if singularity_dir.exists():
              shutil.rmtree(singularity_dir, ignore_errors=True)

          # Give the user the option to delete databases
          db_dir = SCRIPT_DIR / "resources" / "databases"
          if db_dir.exists() and db_dir.is_dir():
              response = input(
               "Do you also want to delete the downloaded databases? [y/N]: "
              )
              if response.lower() == "y":
               self.logger.info("Deleting databases...")
               shutil.rmtree(db_dir, ignore_errors=True)

     self.logger.info("Cleaning completed.")
     return 0

    def samplesinfo(self):
     """
     Generates the samples_info.csv file from FASTQ files.
     This function uses the build_samplesinfo.py script from the workflow/scripts directory.

     Returns:
         int: 0 if the generation completes successfully, 1 otherwise.
     """
     # Verify required parameters
     if not self.args.run_name:
         self.logger.error("You must specify the run name with --run_name")
         return 1

     if not self.args.platform:
         self.logger.error("You must specify the platform with --platform")
         return 1

     if not self.args.fastq:
         self.logger.error(
          "You must specify the FASTQ files directory with --fastq"
         )
         return 1

     # Validate the run name in GVA mode
     if self.args.mode == "gva":
         pattern = re.compile(r"^\d{6}_[A-Z]{4}\d{3}$")
         if not pattern.match(self.args.run_name):
          self.logger.error(
              "In GVA mode, the run name must follow the format AAMMDD_HOSPXXX"
          )
          self.logger.error("Example: 230512_ALIC001")
          return 1

     # Verify that the fastq directory exists
     if not os.path.exists(self.args.fastq):
         self.logger.error(f"Error: The directory {self.args.fastq} does not exist")
         return 1

     # If an output directory was specified, verify that it exists
     if self.args.output and not os.path.exists(self.args.output):
         try:
          os.makedirs(self.args.output)
         except Exception as e:
          self.logger.error(f"Error creating the output directory: {e}")
          return 1

     # Build command
     build_script = WORKFLOW_DIR / "scripts" / "build_samplesinfo.py"
     if not build_script.exists():
         self.logger.error(f"Error: The script {build_script} was not found")
         return 1

     cmd = [
         sys.executable,
         str(build_script),
         "--mode",
         self.args.mode,
         "--run_name",
         self.args.run_name,
         "--platform",
         self.args.platform,
         "--fastq",
         self.args.fastq,
     ]

     if self.args.output:
         cmd.extend(["--output", self.args.output])

     # Execute command
     self.logger.info(f"Executing: {' '.join(cmd)}")
     if self.args.dry_run:
         self.logger.info(f"[DRY RUN] Command: {' '.join(cmd)}")
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
              output_dir, f"samplesinfo_{self.args.run_name}.csv"
          )
          self.logger.info(
              f"The file has been generated correctly in: {output_file}"
          )
          self.logger.info("IMPORTANT: Before running the analysis you must:")
          self.logger.info("1. Edit the file and complete the fields PETICION, FECHA_TOMA_MUESTRA, ESPECIE_SECUENCIA and MOTIVO_WGS")
          self.logger.info("2. Validate the modified file with:")
          self.logger.info(
              f"./epibac.py validate --samples {output_file} --outdir output/{self.args.run_name} --run_name {self.args.run_name} --mode {self.args.mode}"
          )
          self.logger.info("3. If the validation is successful, run the analysis with:")
          self.logger.info(
              f"./epibac.py run --samples {output_file} --outdir output/{self.args.run_name}  --run_name {self.args.run_name} --mode {self.args.mode}"
          )
         return result.returncode
     except subprocess.CalledProcessError as e:
         self.logger.error(f"Error executing build_samplesinfo.py: {e}")
         return e.returncode


def main():
    """Main function."""
    # Create main parser
    parser = argparse.ArgumentParser(
     description="EPIBAC: Pipeline for bacterial genomic analysis"
    )
    parser.add_argument(
     "-v", "--version", action="version", version=f"EPIBAC v{VERSION}"
    )
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)
    
    # === Define each subparser with its specific arguments ===
    
    # Command: check
    check_parser = subparsers.add_parser("check", help="Verify project structure and dependencies")
    
    # Command: setup
    # In the section where the parser for the 'setup' subcommand is defined
    setup_parser = subparsers.add_parser("setup", help="Configure the environment and download databases")

    # Command: validate
    validate_parser = subparsers.add_parser("validate", help="Validate sample file")
    
    # Command: run
    run_parser = subparsers.add_parser("run", help="Execute complete analysis")
    run_parser.add_argument(
     "--resume", action="store_true", help="Continue previous interrupted analysis"
    )
    
    # Command: clean
    # Parser for the 'clean' subcommand
    clean_parser = subparsers.add_parser("clean", help="Delete temporary files and logs")
    clean_parser.add_argument("--all", action="store_true", help="Also delete installed databases")
    clean_parser.add_argument("--logs", action="store_true", help="Delete only log files")
    
    # Command: samplesinfo
    samplesinfo_parser = subparsers.add_parser(
     "samplesinfo", help="Generate samples_info.csv file from FASTQ files"
    )
    samplesinfo_parser.add_argument("--run_name", type=str, required=True, 
                    help="Name of the run/experiment")
    samplesinfo_parser.add_argument("--platform", type=str, required=True, choices=["illumina", "nanopore"],
                    help="Sequencing platform (illumina or nanopore)")
    samplesinfo_parser.add_argument("--fastq", type=str, required=True,
                    help="Directory containing FASTQ files")
    samplesinfo_parser.add_argument("--output", type=str,
                    help="Output directory for the generated file")
    samplesinfo_parser.add_argument("--mode", choices=["gva", "normal"], default="gva",
                    help="Analysis mode (default: gva)")
    
    # === Add global arguments to ALL subparsers ===
    for subparser in [check_parser, setup_parser, validate_parser, run_parser, clean_parser, samplesinfo_parser]:
     # Execution options
     execution = subparser.add_mutually_exclusive_group()
     execution.add_argument("--conda", action="store_true", help="Use conda environments (default)")
     execution.add_argument("--singularity", action="store_true", help="Use Singularity/Apptainer containers")
     
     # Common options
     subparser.add_argument("--verbose", action="store_true", help="Show detailed information")
     subparser.add_argument("--dry-run", action="store_true", help="Show commands without executing")
     subparser.add_argument("--threads", type=int, default=4, help="Number of threads (default: 4)")
     subparser.add_argument("--config", type=str, help=f"Configuration file (default: {DEFAULT_CONFIG})")
     # Only add relevant arguments for certain commands
     if subparser in [validate_parser, run_parser]:
         subparser.add_argument("--samples", type=str, help="Sample file")
         subparser.add_argument("--outdir", type=str, help="Output directory")
         subparser.add_argument("--run_name", type=str, help="Name of the run/experiment")
         subparser.add_argument(
          "--mode", choices=["gva", "normal"], default="gva", help="Analysis mode (default: gva)"
         )
     # Proxy only for those who need it
     if subparser in [setup_parser, run_parser]:
         subparser.add_argument("--proxy", type=str, help="Proxy URL (e.g: http://proxy.example.com:8080)")
    
    args = parser.parse_args()

    # By default use conda if not specified
    if not getattr(args, 'conda', False) and not getattr(args, 'singularity', False):
     args.conda = True

    # Execute the command
    runner = EpibacRunner(args)
    return runner.run()

if __name__ == "__main__":
    sys.exit(main())
