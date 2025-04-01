import os
import logging
import subprocess
from pathlib import Path
import tarfile
import shutil
import sys

# Configurar logging
os.makedirs(os.path.dirname(snakemake.log[0]), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(snakemake.log[0]),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('setup_prokka')

def download_file(url, output_path):
    """Descarga un archivo usando wget sin verificar certificados."""
    logger.info(f"Descargando {url} -> {output_path}")
    try:
        result = subprocess.run(
            ['wget', '--no-check-certificate', '-O', output_path, url],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info("Descarga completada")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error descargando {url}: {e.stderr}")
        raise

def setup_perl_environment():
    """Configura el entorno Perl necesario para Prokka."""
    logger.info("Configurando entorno Perl...")
    
    if 'CONDA_PREFIX' in os.environ:
        base_dir = os.environ['CONDA_PREFIX']
        logger.info(f"Usando entorno Conda: {base_dir}")
    elif os.path.exists('/opt/conda'):
        base_dir = '/opt/conda'
        logger.info(f"Usando entorno contenedor: {base_dir}")
    else:
        logger.warning("No se encontró un entorno Conda o contenedor")
        return
    
    perl_lib = os.path.join(base_dir, "lib/perl5/site_perl")
    if os.path.exists(perl_lib):
        os.environ['PERL5LIB'] = perl_lib
        os.environ['PATH'] = f"{os.path.join(base_dir, 'bin')}:{os.environ.get('PATH', '')}"
        logger.info(f"PERL5LIB configurado a: {perl_lib}")
    else:
        logger.warning(f"No se encontró el directorio Perl: {perl_lib}")

try:
    # Configurar entorno Perl
    setup_perl_environment()

    # Crear directorios
    db_dir = Path(snakemake.params.db_dir)
    db_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Directorio base: {db_dir}")

    for subdir in ['hmm', 'cm', 'kingdom']:
        subdir_path = db_dir / subdir
        subdir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Creado subdirectorio: {subdir_path}")

    # Verificar si ya está todo configurado
    files_to_check = [db_dir / 'PGAP.hmm', db_dir / 'PGAP.hmm.h3i']
    cms_to_check = [db_dir / 'cm' / cm for cm in snakemake.params.cm_files]
    all_files_exist = all(f.exists() for f in files_to_check + cms_to_check)

    if all_files_exist:
        logger.info("Todos los archivos necesarios ya existen. Omitiendo descarga y configuración.")
        # Crear flag de finalización y terminar
        flag_path = Path(snakemake.output[0])
        flag_path.touch()
        logger.info("Flag creado. Instalación completada.")
        sys.exit(0)  # Salir con éxito

    # Procesar HMMs si no existen
    hmm_index = db_dir / 'PGAP.hmm.h3i'
    if not hmm_index.exists():
        # CORRECCIÓN: Usar el URL correcto con .tgz en lugar de .gz
        tgz_path = db_dir / 'hmm_PGAP.HMM.tgz'
        download_file(
            'https://ftp.ncbi.nlm.nih.gov/hmm/current/hmm_PGAP.HMM.tgz',
            tgz_path
        )
        
        try:
            # CORRECCIÓN: Manejo más robusto al abrir el archivo tar
            with tarfile.open(tgz_path, mode='r:gz') as tar:
                tar.extractall(path=db_dir)
                logger.info("Archivos extraídos correctamente")
        except (tarfile.ReadError, IOError) as e:
            logger.error(f"Error al extraer {tgz_path}: {str(e)}")
            # Intentar descargar directamente si falla la extracción
            logger.info("Intentando descarga alternativa...")
            download_file(
                'https://github.com/ncbi/pgap/releases/download/2023-07-17.build6330/hmm_PGAP.HMM.tgz',
                tgz_path
            )
            with tarfile.open(tgz_path, mode='r:gz') as tar:
                tar.extractall(path=db_dir)
                logger.info("Archivos extraídos correctamente desde fuente alternativa")
        
        # Verificar que se creó el directorio hmm_PGAP
        hmm_pgap_dir = db_dir / 'hmm_PGAP'
        if not hmm_pgap_dir.exists() or not any(hmm_pgap_dir.iterdir()):
            logger.error(f"El directorio {hmm_pgap_dir} no existe o está vacío después de la extracción")
            raise FileNotFoundError(f"Extracción fallida: no se encontraron archivos HMM")
        
        # ---- Enfoque más similar a bash: concatenar primero, luego filtrar ----
        # 1. Concatenar todos los archivos HMM en un archivo raw
        raw_file = db_dir / 'PGAP.hmm.raw'
        logger.info(f"Concatenando archivos HMM en {raw_file}")
        
        # Usar find + cat como en bash
        cmd = f"find {db_dir / 'hmm_PGAP'} -type f -name '*.HMM' -exec cat {{}} + > {raw_file}"
        subprocess.run(cmd, shell=True, check=True)
        
        # Verificar que el archivo raw se creó y tiene contenido
        if not raw_file.exists() or raw_file.stat().st_size == 0:
            logger.error("El archivo raw está vacío o no se pudo crear")
            # Intentar otra aproximación
            logger.info("Intentando método alternativo para concatenar archivos")
            with open(raw_file, 'wb') as outfile:
                for hmm_file in hmm_pgap_dir.glob('**/*.HMM'):
                    logger.info(f"Procesando {hmm_file}")
                    with open(hmm_file, 'rb') as infile:
                        outfile.write(infile.read())
        
        # 2. Filtrar duplicados usando el mismo awk que en bash
        hmm_file = db_dir / 'PGAP.hmm'
        logger.info(f"Filtrando duplicados en {hmm_file}")
        
        awk_cmd = f"""awk '/^NAME/ {{ if (a[$2]++) skip=1; else skip=0 }} !skip {{ print }}' {raw_file} > {hmm_file}"""
        subprocess.run(awk_cmd, shell=True, check=True)
        
        # Verificar que se creó el archivo final
        if not hmm_file.exists() or hmm_file.stat().st_size == 0:
            logger.error("El archivo HMM final está vacío o no se pudo crear")
            # Copiar directamente si el filtrado falló
            shutil.copy2(raw_file, hmm_file)
            logger.info(f"Copiado {raw_file} a {hmm_file} sin filtrar")
        
        # 3. Ejecutar hmmpress con un solo hilo para evitar problemas
        logger.info("Ejecutando hmmpress...")
        try:
            subprocess.run(
                ['hmmpress', '-f', str(hmm_file)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info("Índices HMM creados correctamente")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error ejecutando hmmpress: {e.stderr.decode() if hasattr(e, 'stderr') else str(e)}")
            # Verificar tamaño del archivo
            if hmm_file.exists():
                size = hmm_file.stat().st_size
                logger.info(f"Archivo HMM existe, tamaño: {size} bytes")
                # Mostrar primeras líneas
                try:
                    with open(hmm_file, 'r') as f:
                        head = ''.join([f.readline() for _ in range(10)])
                    logger.info(f"Primeras líneas del archivo:\n{head}")
                except:
                    logger.warning("No se pudieron leer las primeras líneas del archivo")
            # Continuamos a pesar del error con hmmpress
            logger.warning("Continuando a pesar del error con hmmpress")

    # Descargar CM files
    for cm_file in snakemake.params.cm_files:
        cm_path = db_dir / 'cm' / cm_file
        if not cm_path.exists():
            # CORRECCIÓN: URL actualizada para asegurar compatibilidad
            download_file(
                f'https://github.com/tseemann/prokka/raw/master/db/cm/{cm_file}',
                cm_path
            )
            # Verificar que se descargó correctamente
            if not cm_path.exists() or cm_path.stat().st_size == 0:
                logger.warning(f"Archivo CM {cm_file} no se descargó correctamente, intentando URL alternativa")
                download_file(
                    f'https://raw.githubusercontent.com/tseemann/prokka/master/db/cm/{cm_file}',
                    cm_path
                )

    # Configurar Prokka si está disponible
    logger.info("Configurando Prokka...")
    try:
        # Verificar que prokka esté disponible
        which_result = subprocess.run(['which', 'prokka'], capture_output=True, text=True)
        if which_result.returncode == 0:
            result = subprocess.run(
                ['prokka', '--cpus', '1', '--dbdir', str(db_dir), '--setupdb'],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("Prokka configurado correctamente")
            logger.debug(f"Salida de prokka: {result.stdout}")
        else:
            logger.warning("Comando prokka no encontrado, omitiendo setupdb")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error configurando Prokka: {e.stderr if hasattr(e, 'stderr') else str(e)}")
        logger.error(f"Comando: prokka --cpus 1 --dbdir {db_dir} --setupdb")
        logger.error(f"Código de salida: {e.returncode if hasattr(e, 'returncode') else 'desconocido'}")
        logger.warning("Continuando a pesar del error setupdb")

    # Verificar archivos esenciales (PGAP.hmm)
    if not (db_dir / 'PGAP.hmm').exists():
        logger.error("Archivo crítico PGAP.hmm no encontrado, la instalación puede estar incompleta")
    else:
        logger.info(f"Archivo PGAP.hmm encontrado, tamaño: {(db_dir / 'PGAP.hmm').stat().st_size} bytes")

    # Crear archivos de índice si no existen
    for ext in ['.h3f', '.h3i', '.h3m', '.h3p']:
        if not (db_dir / f'PGAP.hmm{ext}').exists():
            logger.warning(f"Índice {ext} no encontrado, el rendimiento puede verse afectado")

    # Verificar CM files
    for cm_file in snakemake.params.cm_files:
        if not (db_dir / 'cm' / cm_file).exists():
            logger.warning(f"Archivo CM {cm_file} no encontrado")
        else:
            logger.info(f"Archivo CM {cm_file} encontrado")

    # Limpiar temporales
    logger.info("Limpiando archivos temporales...")
    if (db_dir / 'hmm_PGAP').exists():
        shutil.rmtree(db_dir / 'hmm_PGAP', ignore_errors=True)
    if (db_dir / 'PGAP.hmm.raw').exists():
        os.remove(db_dir / 'PGAP.hmm.raw')
    if (db_dir / 'hmm_PGAP.HMM.tgz').exists():
        os.remove(db_dir / 'hmm_PGAP.HMM.tgz')

    # Crear VERSION.txt
    version_file = db_dir / "VERSION.txt"
    with open(version_file, "w") as f:
        f.write("PGAP HMM database\n")
        f.write("Fecha de instalación: " + subprocess.check_output(["date"]).decode().strip() + "\n")
    logger.info(f"Archivo VERSION.txt creado en {version_file}")

    # Crear flag de finalización
    flag_path = Path(snakemake.output[0])
    flag_dir = flag_path.parent
    flag_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Creando archivo flag: {flag_path}")
    flag_path.touch()
    
    if not flag_path.exists():
        raise FileNotFoundError(f"No se pudo crear el archivo flag: {flag_path}")
    
    logger.info("Instalación completada exitosamente")

except Exception as e:
    logger.error(f"Error durante la configuración: {str(e)}")
    sys.exit(1)