# EPIBAC

Pipeline for basic bioinformatic analysis of bacteria and study of AMR and MLST.

# Instalación de CONDA

```
# Creamos directorio donde tendremos instalado CONDA (donde tengamos permisos de escritura)
mkdir -p ~/miniconda3
# Descargamos última versión
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
# Damos permisos al script de instalación
chmod u+x ~/miniconda3/miniconda.sh
# Instalamos de manera desatendida
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
# Borramos archivo de instalación
rm -rf ~/miniconda3/miniconda.sh
```

## Cargamos ambiente inicital de CONDA (base)

Lo más sencillo sería salir y volver a abrir otra terminal, para que nos cargue el fichero `.bashrc` actualizado con la instalación de CONDA.

Si no podemos cargar de la manera:

```
# Cargamos fichero fuente configuración
source ~/.bashrc
# Aseguramos que se encuentre correctamente CONDA en nuestro sistema
export PATH="$HOME/miniconda3/bin:$PATH"
```
Veremos que en el `prompt` nos ha salid el prefijo `(base)` delante de nuestro usuario y máquina: `(base) usuario@máquina:$`.

Ya estamnos en la "anarquía" de CONDA ;), poder instalar paquetes sin permisos de administrador.

## Añadimos un par de canales básicos como repositorios de paquetes de instalación
```
conda config --add channels bioconda
conda config --add channels conda-forge
```


## Cambiamos opciones de prioridad de canales
```
conda config --set channel_priority strict
```

## Actualizamos CONDA a la última versión
```
conda update conda
```

## Podemos ver la información básica de la instalación realizada de CONDA
```
conda info -a
```



# Instalamos MAMBA, como gestor de paquetes en base (ambiente inicial de CONDA)
```
conda install mamba
```

# Creamos ambiente de SNAKEMAKE

Éste será el primer ambiente que instalemos que llamaremos `snake`. Al instalarlo con `mamba`, irá mucho más rápido.

```
mamba create -n snake -c conda-forge bioconda::snakemake=7.32 bioconda::snakemake-minimal=7.32 snakemake-wrapper-utils
```

## Cargamos ambiente SNAKE
```
conda activate snake
```
Veremos que el prefijo de `(base)` a cambiado a `(snake) usuario@máquina:$`. Deberemos cargar este ambiente siempre que querramos lanzar un pipeline de Snakemake.


# Puesta a punto pipeline EPIBAC

Es importante realizar los siguientes pasos en un sitio en el que tengamos al menos 50 GBs de espacio. El fichero de instalación GIT no ocupa mucho, pero sí que ocupa más los programas y bases de datos instalados.

## Clonamos repositorio GIT con el pipeline y los ficheros de prueba
```
git clone https://github.com/alesanzdro/epibac.git
```

## Corremos test de prueba que también nos servirá para instalar todos los programas necesarios y bases de datos
```
# Nos situamos dentro de la carpeta "epibac"
cd epibac	
```

Con la configuración actual es importante ejecutar todos los trabajos desde el mismo directorio, para no volver a instalar todos los recursos y bases de datos.
Snakemake los instalaría en una carpeta oculta llamada `.snakemake`, 

Si vamos cambiando de carpeta cada vez, estaríamos generando una nueva instalación desde cero.

Para cambiar de carrera, sería modificar el fichero `config.yaml` o modificar los directorios de ejecución al ejecutar el comando.

```
snakemake --config samples=test/samplesheet.tsv outdir=test/out logdir=test/log --use-conda -j 8
```

Aquí analizaremos una muestra anonimizada para comprobar que todos los pasos se realizan correctamente.


## Fichero config.yaml

Se especifica el número de procesadores (threads), RAM (MB), o tiempo máximo de ejecución de un proceso (minutos). Snakemake es un gestor de flujos de trabajo, por loque se podrá aprovechar el máximo potencial de nuestras máquinas.

Nótese que en el comando de ejemplo hemos especificado `-j 8`, eso es porque le hemos permitido a Snakemake emplear hasta un máximo de 8 CPUs.

Por lo tanto en equipos más potentes, con CPUs más rápidas y un mayor número de hilos, podremos obtener antes los resultados. Si tenemos un procesador i7-11700, con 8 cores / 16 threads, perfectamente podremos indicarle `-j 12`, teniendo en cuenta de reservar algo para nuestro aguantar nuestro sistema operativo y uso normal básico.

Durante las ejecuciones de los análisis es posible que notemos alguna ralentización del sistema.

En caso de correr los análisis bajo un entorno virtual como `VirtualBox`, habrá que tener en cuenta este coste, de mantener dos sistemas operativos en una misma máquina y tal vez reducir el número de procesadores empleados en `-j`.
