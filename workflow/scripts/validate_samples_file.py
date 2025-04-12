#!/usr/bin/env python3
import os
import sys
import pandas as pd
import yaml
import json
from datetime import datetime
import re
import argparse

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Sample file validator for EPIBAC')
    parser.add_argument('--samples', '-s', required=True, help='Sample file to validate')
    parser.add_argument('--config', '-c', default='config.yaml', help='Configuration file')
    parser.add_argument('--mode', '-m', choices=['gva', 'normal'], help='Analysis mode (overrides config)')
    parser.add_argument('--output', '-o', help='Save validated version to this file (optional)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed information')
    return parser.parse_args()

def validate_samples(samples_file, config, mode=None, verbose=False):
    """
    Validates the sample file.
    
    Args:
        samples_file: Path to the sample file
        config: Configuration dictionary or path to config.yaml
        mode: Overrides the mode in config (gva or normal)
        verbose: If True, shows additional informational messages
    
    Returns:
        dict: With keys "status" (0-3), "warnings", "errors", "fatal_errors", and "validated_df"
    """
    warnings = []
    errors = []
    fatal_errors = []
    validated_df = None
    
    # Load configuration if it's a path
    if isinstance(config, str):
        try:
            with open(config, "r") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            fatal_errors.append(f"Error loading configuration: {e}")
            return {
                "status": 3,
                "warnings": warnings,
                "errors": errors,
                "fatal_errors": fatal_errors,
                "validated_df": None
            }
    
    # Determine the analysis mode
    mode = mode or config.get("mode", "normal")
    if verbose:
        print(f"Validation mode: {mode}")
    
    # Validate run_name in GVA mode
    if mode == "gva":
        run_name = config.get("run_name", "")
        if not run_name:
            fatal_errors.append("run_name not specified in configuration for GVA mode")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
            
        # Validate format AAMMDD_HOSPXXX
        run_pattern = re.compile(r"^\d{6}_[A-Z]{4}\d{3}$")
        if not run_pattern.match(run_name):
            fatal_errors.append(f"The run_name format '{run_name}' is invalid for GVA mode. " 
                               f"It must follow the format AAMMDD_HOSPXXX")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
        
        # Validate hospital code
        hospital_code = run_name.split("_")[1][:4]
        valid_hospitals = ["ALIC", "CAST", "ELCH", "GRAL", "PESE", "CLIN", "LAFE", "EPIM"]
        if hospital_code not in valid_hospitals:
            fatal_errors.append(f"Invalid hospital code '{hospital_code}'. " 
                               f"It must be one of: {', '.join(valid_hospitals)}")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
    
    # Load and detect file format
    try:
        try:
            df = pd.read_csv(samples_file, sep=";", dtype=str)
            separator = ";"
            if verbose:
                print(f"File loaded with separator: semicolon (;)")
        except:
            try:
                df = pd.read_csv(samples_file, sep=",", dtype=str)
                separator = ","
                if verbose:
                    print(f"File loaded with separator: comma (,)")
            except Exception as e:
                fatal_errors.append(f"Error loading sample file: {e}")
                return {"status": 3, "warnings": warnings, "errors": errors, 
                        "fatal_errors": fatal_errors, "validated_df": None}
    except Exception as e:
        fatal_errors.append(f"Unexpected error processing the file: {e}")
        return {"status": 3, "warnings": warnings, "errors": errors, 
                "fatal_errors": fatal_errors, "validated_df": None}

    # Verify columns based on the mode
    if mode == "gva":
        # Mandatory columns for GVA
        required_columns = ["PETICION", "CODIGO_MUESTRA_ORIGEN"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        # At least one of these must exist
        data_columns = ["ILLUMINA_R1", "ILLUMINA_R2", "NANOPORE"]
        has_data_column = any(col in df.columns for col in data_columns)
        
        if missing_columns:
            fatal_errors.append(f"Missing mandatory columns for GVA mode: {', '.join(missing_columns)}")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
                    
        if not has_data_column:
            fatal_errors.append(f"At least one of these columns must be included: {', '.join(data_columns)}")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
        
        # Important but not absolutely mandatory columns
        important_columns = ["FECHA_TOMA_MUESTRA", "ESPECIE_SECUENCIA", "MOTIVO_WGS"]
        missing_important = [col for col in important_columns if col not in df.columns]
        if missing_important:
            errors.append(f"Missing important columns: {', '.join(missing_important)}")
        
        # Map GVA columns to internal standard names
        rename_map_gva = {
            "CODIGO_MUESTRA_ORIGEN": "id",
            "PETICION": "id2",
            "FECHA_TOMA_MUESTRA": "collection_date",
            "ESPECIE_SECUENCIA": "organism",
            "MOTIVO_WGS": "relevance",
            "ILLUMINA_R1": "illumina_r1",
            "ILLUMINA_R2": "illumina_r2",
            "NANOPORE": "nanopore",
            "ID_WS": "scheme_mlst",
            "ST_WGS": "st",
            "MLST_WGS": "mlst",
            "R_Geno_WGS": "amr",
            "PHENO_WGS": "pheno_resfinder",
            "V_WGS": "virulence",
            "CONFIRMACION": "confirmation_note",
            "NUM_BROTE": "outbreak_id",
            "COMENTARIO_WGS": "comment",
        }

        # Apply only the columns that exist
        rename_dict = {k: v for k, v in rename_map_gva.items() if k in df.columns}
        validated_df = df.rename(columns=rename_dict)

        # In GVA mode, verify that the id column exists after renaming
        if "id" not in validated_df.columns:
            fatal_errors.append(f"The id column (mapped from CODIGO_MUESTRA_ORIGEN) does not exist after renaming")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
        
        # Verify mandatory fields are filled
        for i, row in validated_df.iterrows():
            # Verify PETICION (id2)
            if 'id2' in validated_df.columns:
                if pd.isna(row.get('id2')) or str(row.get('id2')).strip() == '':
                    errors.append(f"Error in row {i+2}: PETICION not specified")
            
            # Verify important fields
            if 'organism' in validated_df.columns:
                if pd.isna(row.get('organism')) or str(row.get('organism')).strip() == '':
                    errors.append(f"Error in row {i+2}: ESPECIE_SECUENCIA/organism not specified")
            
            if 'relevance' in validated_df.columns:
                if pd.isna(row.get('relevance')) or str(row.get('relevance')).strip() == '':
                    errors.append(f"Error in row {i+2}: MOTIVO_WGS/relevance not specified")
            
            if 'collection_date' in validated_df.columns:
                if pd.isna(row.get('collection_date')) or str(row.get('collection_date')).strip() == '':
                    warnings.append(f"Warning in row {i+2}: FECHA_TOMA_MUESTRA/collection_date not specified")
            
            # Verify it has at least one data source
            has_data = False
            for col in ['illumina_r1', 'nanopore']:
                if col in validated_df.columns:
                    if not pd.isna(row.get(col)) and str(row.get(col)).strip() != '':
                        has_data = True
                        break
            
            if not has_data:
                errors.append(f"Error in row {i+2}: No data source specified (illumina_r1 or nanopore)")
            
    else:  # normal mode
        required_columns = ["id"]
        data_columns = ["illumina_r1", "illumina_r2", "nanopore"]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        has_data_column = any(col in df.columns for col in data_columns)
        
        if missing_columns:
            fatal_errors.append(f"Missing mandatory columns for normal mode: {', '.join(missing_columns)}")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}
                    
        if not has_data_column:
            fatal_errors.append(f"At least one of these columns must be included: {', '.join(data_columns)}")
            return {"status": 3, "warnings": warnings, "errors": errors, 
                    "fatal_errors": fatal_errors, "validated_df": None}

        # In normal mode, no renaming is done
        validated_df = df.copy()

    # Verify all samples have a value in the primary ID column
    missing_ids = validated_df[validated_df["id"].isna() | (validated_df["id"] == "")].index.tolist()
    if missing_ids:
        fatal_errors.append(f"Rows without a value in the identification column: {[i+2 for i in missing_ids]}")
        return {"status": 3, "warnings": warnings, "errors": errors, 
                "fatal_errors": fatal_errors, "validated_df": None}
                
    # Verify special characters in IDs
    invalid_chars_pattern = re.compile(r'[^\w\-_]')
    for i, sample_id in enumerate(validated_df["id"]):
        if invalid_chars_pattern.search(str(sample_id)):
            errors.append(f"Error in row {i+2}: ID '{sample_id}' contains invalid special characters")
    # Verify existence of FASTQ files
    fastq_columns = [col for col in validated_df.columns 
                    if col in ["illumina_r1", "illumina_r2", "nanopore"]]
    for col in fastq_columns:
        for i, file_path in enumerate(validated_df[col]):
            if pd.notna(file_path) and file_path and not os.path.exists(file_path):
                warnings.append(f"The file {file_path} in column {col}, row {i+2} does not exist")

    # Format dates
    def parse_date(date_str):
        """Parses a date in various possible formats and converts it to YYYY-MM-DD."""
        if pd.isna(date_str) or date_str == "":
            return None
            
        date_patterns = [
            (r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2})$", "%d/%m/%y"),
            (r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$", "%d/%m/%Y"),
            (r"(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})$", "%Y/%m/%d"),
        ]

        for pattern, date_format in date_patterns:
            match = re.match(pattern, str(date_str))
            if match:
                try:
                    clean_date = re.sub(r"[.-]", "/", str(date_str))
                    parsed_date = datetime.strptime(clean_date, date_format)
                    return parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    continue
        return None

    # Process dates
    if "collection_date" in validated_df.columns:
        for i, date_str in enumerate(validated_df["collection_date"]):
            if pd.notna(date_str) and date_str:
                parsed_date = parse_date(str(date_str))
                if parsed_date:
                    validated_df.at[i, "collection_date"] = parsed_date
                else:
                    errors.append(f"Error in row {i+2}: Invalid date format: '{date_str}'")

    # Verify nanopore samples and dorado_model configuration
    has_nanopore = False
    if "nanopore" in validated_df.columns and not validated_df["nanopore"].isna().all() and not (validated_df["nanopore"] == "").all():
        has_nanopore = True

    if has_nanopore:
        dorado_model = config.get("params", {}).get("nanopore", {}).get("dorado_model", None)
        if not dorado_model:
            errors.append("Nanopore samples detected but dorado_model not specified in config.yaml")
        else:
            valid_models = [
                "dna_r10.4.1_e8.2_400bps_hac@v4.2.0",
                "dna_r10.4.1_e8.2_400bps_sup@v4.2.0",
                "dna_r9.4.1_450bps_hac@v3.3",
                "dna_r9.4.1_450bps_sup@v3.3",
            ]
            if dorado_model not in valid_models:
                errors.append(f"Invalid Dorado model '{dorado_model}'. It must be one of: {', '.join(valid_models)}")

    # Determine final status
    status = 0  # By default, everything is OK
    if fatal_errors:
        status = 3  # Fatal errors
        validated_df = None
    elif errors:
        status = 2  # Non-fatal errors
    elif warnings:
        status = 1  # Only warnings
        
    return {
        "status": status,
        "warnings": warnings,
        "errors": errors,
        "fatal_errors": fatal_errors,
        "validated_df": validated_df,
        "separator": separator if "separator" in locals() else ";"
    }

def print_validation_result(result, verbose=False):
    """Prints the validation result in a user-friendly way."""
    if result["fatal_errors"]:
        print("\n┏━━━━━━━━━━━━━━━━━━━━━━ VALIDATION FAILED ❌ ━━━━━━━━━━━━━━━━━━━━┓")
        print("┃ Errors were found that prevent continuation:                   ┃")
        print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
        for error in result["fatal_errors"]:
            print(f"❌ {error}")
        return
        
    if result["errors"]:
        print("\n┏━━━━━━━━━━━━━━━━━━━━ VALIDATION WITH ERRORS ⚠️  ━━━━━━━━━━━━━━━━━┓")
        print("┃ The file has errors that should be corrected:                  ┃")
        print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
        for error in result["errors"]:
            print(f"⚠️ {error}")
        print("")
        
    if result["warnings"]:
        if not result["errors"]:
            print("\n┏━━━━━━━━━━━━━━━━━━ VALIDATION WITH WARNINGS ℹ️  ━━━━━━━━━━━━━━━━━┓")
            print("┃ The file has warnings that you might want to review:           ┃")
            print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
        for warning in result["warnings"]:
            print(f"ℹ️ {warning}")
        print("")
        
    if not result["errors"] and not result["warnings"]:
        print("\n┏━━━━━━━━━━━━━━━━━━━━━━ SUCCESSFUL VALIDATION ━━━━━━━━━━━━━━━━━━━┓")
        print("┃ The sample file has been successfully validated                ┃")
        print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")

def main():
    args = parse_arguments()
    
    # If a mode is provided on the command line, override the config
    if args.config and not os.path.exists(args.config):
        print(f"WARNING: Configuration file not found: {args.config}")
        print("Using default values")
        config = {"mode": args.mode} if args.mode else {"mode": "normal"}
    else:
        try:
            with open(args.config, "r") as f:
                config = yaml.safe_load(f)
                if args.mode:  # Override mode if specified
                    config["mode"] = args.mode
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return 1
    
    # Run validation
    print(f"Validating file: {args.samples}")
    result = validate_samples(args.samples, config, verbose=args.verbose)
    
    # Print results
    print_validation_result(result, verbose=args.verbose)
    
    # Save validated file if requested
    if args.output and result["status"] < 3 and result["validated_df"] is not None:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
            result["validated_df"].to_csv(args.output, index=False, sep=result["separator"])
            print(f"\nValidated file saved to: {args.output}")
        except Exception as e:
            print(f"\nError saving validated file: {e}")
    
    # Exit with appropriate code
    return 0 if result["status"] < 2 else 1

if __name__ == "__main__":
    sys.exit(main())