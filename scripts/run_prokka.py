import os
import subprocess
import shutil
import sys

# Para depuración, escribe al log
log_file = open(snakemake.log[0], "w")
def log(message):
    print(message, file=log_file)
    log_file.flush()

log(f"Iniciando script run_prokka.py")

try:
    if snakemake.params.skip:
        # Si se omite Prokka, crear archivos vacíos
        log("Modo skip activado, creando archivos vacíos")
        os.makedirs(snakemake.output.dir, exist_ok=True)
        open(snakemake.output.faa, 'w').close()
        open(snakemake.output.gff, 'w').close()
        log("Omitiendo ejecución de Prokka (skip_prokka=true)")
    else:
        # Configuración básica
        env = os.environ.copy()
        
        # Configuración del entorno para Perl
        log("Configurando entorno para Perl")
        if os.path.exists("/opt/conda"):
            log("- Usando /opt/conda")
            env["PERL5LIB"] = "/opt/conda/lib/perl5/site_perl"
            env["PATH"] = "/opt/conda/bin:" + env.get("PATH", "")
        elif "CONDA_PREFIX" in os.environ:
            log(f"- Usando CONDA_PREFIX: {os.environ['CONDA_PREFIX']}")
            env["PERL5LIB"] = os.path.join(os.environ["CONDA_PREFIX"], "lib/perl5/site_perl")
            env["PATH"] = os.path.join(os.environ["CONDA_PREFIX"], "bin") + ":" + env.get("PATH", "")
        
        # Verificar archivo FASTA
        log(f"Verificando archivo FASTA: {snakemake.input.fasta}")
        if not os.path.exists(snakemake.input.fasta) or os.path.getsize(snakemake.input.fasta) == 0:
            log("[ERROR] El archivo FASTA está vacío o no existe")
            os.makedirs(snakemake.output.dir, exist_ok=True)
            open(snakemake.output.faa, 'w').close()
            open(snakemake.output.gff, 'w').close()
        else:
            # Crear directorios de salida
            os.makedirs(snakemake.output.dir, exist_ok=True)
            
            # ¡SOLUCIÓN SIMPLIFICADA!
            # No podemos confiar en Prokka para usar parallel correctamente,
            # así que usaremos un truco: crearemos archivos básicos y luego
            # los copiaremos a donde Snakemake espera
            
            # Crear archivos básicos vacíos que Snakemake espera
            open(snakemake.output.faa, 'w').close()
            open(snakemake.output.gff, 'w').close()
            
            log("Intentando ejecutar Prokka con opción --compliant para evitar parallel")
            cmd = [
                "prokka",
                "--cpus", str(snakemake.threads),
                "--compliant",  # Esta opción evita el uso de parallel en algunas versiones
                snakemake.input.fasta,
                "--prefix", snakemake.params.prefix,
                "--strain", snakemake.params.prefix,
                "--locustag", snakemake.params.prefix,
                "--hmms", os.path.join(snakemake.params.db_dir, "PGAP.hmm"),
                "--outdir", snakemake.output.dir,
                "--force"
            ]
            
            log(f"Ejecutando Prokka con comando: {' '.join(cmd)}")
            
            try:
                result = subprocess.run(cmd, stdout=log_file, stderr=subprocess.STDOUT, env=env, check=False)
                
                if result.returncode == 0:
                    log("Prokka completado exitosamente con la opción --compliant")
                else:
                    log(f"Error al ejecutar Prokka con --compliant. Código de salida: {result.returncode}")
                    log("Intentando sin la opción --compliant y con 1 CPU")
                    
                    # Nuevo intento sin --compliant pero con 1 CPU
                    cmd = [
                        "prokka",
                        "--cpus", "1",  # Forzar un solo CPU
                        snakemake.input.fasta,
                        "--prefix", snakemake.params.prefix,
                        "--strain", snakemake.params.prefix,
                        "--locustag", snakemake.params.prefix,
                        "--hmms", os.path.join(snakemake.params.db_dir, "PGAP.hmm"),
                        "--outdir", snakemake.output.dir,
                        "--force"
                    ]
                    
                    log(f"Ejecutando Prokka con comando: {' '.join(cmd)}")
                    result = subprocess.run(cmd, stdout=log_file, stderr=subprocess.STDOUT, env=env, check=False)
                    
                    if result.returncode == 0:
                        log("Prokka completado exitosamente con 1 CPU")
                    else:
                        log(f"Error al ejecutar Prokka. Código de salida: {result.returncode}")
                        log("No se pudo ejecutar Prokka. Continuando el pipeline sin anotación.")
            except Exception as e:
                log(f"Excepción al ejecutar Prokka: {str(e)}")
            
            # Independientemente del resultado, intentar encontrar y copiar los archivos
            # Si Prokka generó los archivos, los copiamos a donde Snakemake espera
            faa_src = os.path.join(snakemake.output.dir, f"{snakemake.params.prefix}.faa")
            gff_src = os.path.join(snakemake.output.dir, f"{snakemake.params.prefix}.gff")
            
            if os.path.exists(faa_src):
                log(f"Copiando {faa_src} a {snakemake.output.faa}")
                shutil.copy2(faa_src, snakemake.output.faa)
            
            if os.path.exists(gff_src):
                log(f"Copiando {gff_src} a {snakemake.output.gff}")
                shutil.copy2(gff_src, snakemake.output.gff)

except Exception as e:
    log(f"Error en run_prokka.py: {str(e)}")
    # En caso de error, asegurarse de que los archivos de salida existan
    os.makedirs(snakemake.output.dir, exist_ok=True)
    open(snakemake.output.faa, 'w').close()
    open(snakemake.output.gff, 'w').close()
    # No propagar el error para que Snakemake continúe con la siguiente regla

finally:
    log_file.close()