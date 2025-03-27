# EPIBAC

Pipeline for basic bioinformatic analysis of bacteria and study of AMR and MLST.

Example of the excel obtained as analysis results from a run.


![Example_EXCEL](test/Ejemplo_resultados_run.png)


# Información

**VIDEO YOUTUBE INSTALACIÓN DESDE 0:** [https://youtu.be/9AVAYzeB3no](https://youtu.be/9AVAYzeB3no)

Este pipeline se ha probado en las distribuciones de Linux [Ubuntu 20.04.6 LTS (Focal Fossa)](https://releases.ubuntu.com/focal/) y [Ubuntu 22.04.3 LTS (Jammy Jellyfish)](https://releases.ubuntu.com/jammy/).



# Instalación de CONDA

```bash
# Descargamos última versión de CONDA en la HOME
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
# Damos permisos al script de instalación
chmod u+x ~/miniconda.sh
# Instalamos de manera desatendida
bash ~/miniconda.sh -b -u -p ~/miniconda3
# Borramos archivo de instalación
rm -rf ~/miniconda.sh
```


## Configuración inicial de CONDA

Cargamos conda:
```bash
source ~/miniconda3/etc/profile.d/conda.sh
```

Limpiamos canales anteriores:
```bash
conda config --remove-key channels
```

Añadimos canales de forma explícita:
```bash
conda config --append channels conda-forge
conda config --append channels bioconda
conda config --append channels defaults
```

Es posible que salga una advertencia sobre el canal `defaults`.


Configuramos PROXY GVA en CONDA (en caso que haga falta):
```bash
conda config --set proxy_servers.http http://proxy.san.gva.es:8080
conda config --set proxy_servers.https http://proxy.san.gva.es:8080
```

Configuramos conda para que se inicie automáticamente en nuevos shells:
```bash
conda init
```

Este comando configurará conda para que se inicie automáticamente cuando abres una nueva terminal.

> [!NOTE]
> Cerramos la terminal y abrimos una nueva, para asegurarnos de que los cambios surtan efecto.

Actualizamos a la última versión tanto de conda como de los paquetes del entorno base:
```bash
conda update conda
conda update --all
```

Veremos que en el `prompt` nos ha salido el prefijo `(base)` delante de nuestro usuario y máquina: `(base) usuario@máquina:$`.

Ya estramos en la libertad de CONDA ;), poder instalar paquetes sin permisos de administrador.


# Instalamos MAMBA mediante CONDA

Emplearemos **mamba** como gestor o instalador de paquetes en el ambiente inicial de conda, también llamado `base`. 

Para evitar problemas con `conda-libmamba-solver` establecemos primero la prioridad de canales en `strict`:

```bash
conda config --set channel_priority strict
```

En el contexto de Snakemake, el gestor de flujo de trabajo que emplearemos, la reproducibilidad y la consistencia son esenciales para garantizar que los flujos de trabajo se ejecuten de manera predecible en diferentes entornos, se recomienda establecer `channel_priority` en "strict". Esto ayudará a evitar problemas de resolución de dependencias que podrían surgir debido a la flexibilidad en la búsqueda de canales.

**OPCIÓN 1**
```bash
conda install -n base -c conda-forge mamba
```
(Puede tardar un par de minutos)

**OPCIÓN 2**
> [!NOTE]
> Es posible que si hay alguna instalación previa de CONDA, nos pueda dar errores por el orden de canales. 
> Se recomienda una instalación de CONDA desde cero, pero si se quiere partir de una instalación previa y
> hay conflictos de paquetes o se queda colgado durante mucho tiempo, se puede probar a instalar sin tener
> en cuenta el fichero de configuración que deberíamos tener en $HOME/.condarc añadiendo la opción de
> "--override-channels" a la hora de instalar algo en conda, por ejemplo:

```bash
conda install --override-channels -n base -c conda-forge mamba
```

Nos aseguramos tener mamba actualizado:
```bash
mamba update -n base -c conda-forge mamba
```


# Creamos ambiente con SNAKEMAKE mediante MAMBA

Éste será el único ambiente que instalaremos manualmente y que llamaremos `snake`. Al instalarlo con `mamba`, irá mucho más rápido.

```bash
mamba create -n snake -c conda-forge bioconda::snakemake=9.1.1 bioconda::snakemake-minimal=9.1.1 bioconda::snakemake-wrapper-utils=0.7.2 pandas openpyxl git
```


# Puesta a punto pipeline EPIBAC

Es importante realizar los siguientes pasos en un sitio en el que tengamos al menos 50 GBs de espacio. El fichero de instalación GIT no ocupa mucho, pero sí que ocupa más los programas y bases de datos instalados.

La instalación ocupa un mínimo de 26 GB, por lo que mínimo, para lanzar una carrera de Illumina, se necesitarían unos 70 GB - 100 GB.

En posteriores reuniones se hablará de la salida de datos que les interesa a los Hospitales. En caso de sólo querer el informe final, manteniendo siempre una copia de los `RAW_DATA`, se podría reducir algo el espacio final necesario. 

## Cargamos ambiente SNAKE
```bash
conda activate snake
```
Veremos que el prefijo de `(base)` a cambiado a `(snake) usuario@máquina:$`. Deberemos cargar este ambiente siempre que querramos lanzar un pipeline de Snakemake.

## Clonamos repositorio GIT con el pipeline y los ficheros de prueba
```bash
git clone https://github.com/EpiMol/epibac.git
```

## Corremos test de prueba que también nos servirá para instalar todos los programas necesarios y bases de datos
```bash
# Nos situamos dentro de la carpeta "epibac"
cd epibac	
```

Con la configuración actual es importante ejecutar todos los trabajos desde el mismo directorio, para no volver a instalar todos los recursos y bases de datos.
Snakemake los instalaría en una carpeta oculta llamada `.snakemake`, 

Si vamos cambiando de carpeta cada vez, estaríamos generando una nueva instalación desde cero.

Para cambiar de carrera, sería modificar el fichero `config.yaml` o modificar los directorios de ejecución al ejecutar el comando.

```bash
snakemake --config samples=test/samplesheet.tsv outdir=test/out logdir=test/log --use-conda -j 8
```

Aquí analizaremos una muestra anonimizada para comprobar que todos los pasos se realizan correctamente.

En el siguiente gráfico se muestra el esquema básico de trabajo para una muestra. Los pasos como instalación de las bases de datos sólo se realizaría una vez.


![Grafo flujo de trabajos con una muestra](test/dag.png)


Y el resultado debería dar:

| | | | | | | | | |
|-|-|-|-|-|-|-|-|-|
|Sample|Scheme_mlst|ST|MLST|AMR|VIRULENCE|SCOPE_core|GENE_resfinder|PHENO_resfinder|
|23_SALM_92123|senterica_achtman_2|1628|aroC(46) dnaN(60) hemD(10) hisD(9) purE(6) sucA(12) thrA(17)|fosA7.7 mdsA mdsB tet(C)|iroB iroC sinH|fosA7.7 tet(C)|aac(6')-Iaa fosA7 tet(C)|tobramycin-amikacin[aminoglycoside] fosfomycin[fosfomycin] tetracycline-doxycycline[tetracycline]|


## Relanzar pipeline
En caso de que hubiéramos tenido algún error podríamos volver a intentar lanzar el pipeline añadiendo la opción `--rerun-incomplete`
```bash
snakemake --config samples=test/samplesheet.tsv outdir=test/out logdir=test/log --use-conda -j 8 --rerun-incomplete
```

# Lanzar un análisis con mis propias muestras


> [!NOTE]
> IMPORTANTE, tenemos que ejecutar todos los análisis desde el directorio que hayamos instalado `epibac` o se nos volverá a instalar todo dentro de la carpeta oculta `.snakemake`


## Situar ficheros FASTQ para analizar

Si tenemos `epibac` dentro de nuestra HOME:
```bash
cd $HOME/epibac
```

Dentro de la carpeta epibac creo la carpeta RAWDATA
```bash
mkdir -p RAWDATA
```

Dentro es donde pondré las carpetas de las carreras, por ejemplo:

`RAWDATA/231004_NLSAR001`

Dentro de esa carpeta debe haber una carpeta llamada "fastq" conteniendo todos los FASTQ para analizar de esa carrera, tanto R1 como R2 y con un esquema similar de nombres (se puede adaptar a otras nomenclaturas).

De modo que si tenemos la carpeta `epibac` en nuestra HOME, tendríamos los *fastq.gz de la carrera que quiero analizar en `$HOME/epibac/RAWDATA/231004_NLSAR001/fastq`.

## Creamos samplesheet

```bash
# Para facilitar no redundar tanto el código asigno a la variable `NAME` el nombre de la carrera que queremos analizar
NAME="231004_NLSAR001"
python scripts/do_samplesheet.py RAWDATA/$NAME/fastq RAWDATA/$NAME/samplesheet_$NAME.csv
```

## Corremos análisis
```bash
NAME="231004_NLSAR001"
snakemake --config samples=RAWDATA/$NAME/samplesheet_$NAME.csv outdir=OUT/$NAME logdir=LOG/$NAME --use-conda -j 8
```

De esa manera tendremos los arhivos originales en `RAWDATA`, en `OUT` los resultados y en `LOG` los ficheros "log" de los trabajos realizados durante el flujo de trabajo.


## Fichero config.yaml

Se especifica el número de procesadores (threads), RAM (MB), o tiempo máximo de ejecución de un proceso (minutos). Snakemake es un gestor de flujos de trabajo, por loque se podrá aprovechar el máximo potencial de nuestras máquinas.

Nótese que en el comando de ejemplo hemos especificado `-j 8`, eso es porque le hemos permitido a Snakemake emplear hasta un máximo de 8 CPUs.

Por lo tanto en equipos más potentes, con CPUs más rápidas y un mayor número de hilos, podremos obtener antes los resultados. Si tenemos un procesador i7-11700, con 8 cores / 16 threads, perfectamente podremos indicarle `-j 12`, teniendo en cuenta de reservar algo para nuestro aguantar nuestro sistema operativo y uso normal básico.

Durante las ejecuciones de los análisis es posible que notemos alguna ralentización del sistema.

En caso de correr los análisis bajo un entorno virtual como `VirtualBox`, habrá que tener en cuenta este coste, de mantener dos sistemas operativos en una misma máquina y tal vez reducir el número de procesadores empleados en `-j`.

## Si queremos borrar la instalación de snakemake
```bash
rm -r $HOME/epibac/.snakemake
```

## Ejecución SNAKEMAKE + SLURM
Snakemake permite la integración con SLURM, a falta de configurar, para lanzar todos los trabajos por el gestor de colas. Haría falta una configuración adicional, no planteada en esta primera versión.

[Snakemake Documentation on Cluster Execution](https://snakemake.readthedocs.io/en/stable/executing/cluster.html)

# Desistalación CONDA (¡en caso de que queramos restaurar lo que hayamos hecho!)

Eliminamos la inicialización de conda hecho con `conda init`, carpeta `miniconda3` y las carpetas o ficheros de configuración de conda ocultos. 
```bash
sudo sed '/# >>> conda initialize >>>/,/# <<< conda initialize <<</d' -i ~/.bashrc
sudo rm -r $HOME/miniconda3
sudo rm -r $HOME/.conda*
```

# Autores

- Alejandro Sanz-Carbonell
- Irving Cancino-Muñoz
- Carlos Valiente Mullor
- Fernando González-Candelas
