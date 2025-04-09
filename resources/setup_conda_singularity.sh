#!/usr/bin/env bash
#
# setup_env.sh
#
# Script multifunción para:
#   - Desinstalar e instalar Singularity v3.8.7 (opción 'singularity').
#   - Desinstalar COMPLETAMENTE cualquier instalación de conda/Miniconda/Anaconda
#     y reinstalar la última versión de Miniconda + configuración básica (opción 'conda').
#
# Uso:
#   1) sudo ./setup_env.sh singularity
#   2) sudo ./setup_env.sh conda
#   3) sudo ./setup_env.sh conda http://proxy.ejemplo.com:8080
#
# ¡ATENCIÓN!: En el modo "conda" se borran todos los entornos y la instalación de conda.
#             Haz copia de seguridad si es necesario.
#
# Probado en sistemas tipo Debian/Ubuntu con 'apt'.
# -----------------------------------------------------------------------------

# Definición de colores y formatos
COLOR_RESET="\033[0m"
BOLD="\033[1m"
PREGUNTA="${BOLD}\033[33m"  # Dorado/amarillo en negrita
INFO="${BOLD}\033[90m"      # Gris en negrita
ERROR="${BOLD}\033[31m"     # Rojo en negrita
PELIGRO="${BOLD}\033[31m"     # Rojo en negrita
ADVERTENCIA="${BOLD}\033[38;5;208m"  # Naranja en negrita (requiere soporte de 256 colores)
SUGERENCIA="${BOLD}\033[38;5;208m"  # Naranja en negrita (requiere soporte de 256 colores
OK="${BOLD}\033[32m"     # Verde en negrita
FIN="${BOLD}\033[32m"     # Verde en negrita

# Función para usar en echo con colores
format_message() {
  local prefix="$1"
  local message="$2"
  local color="$3"
  
  echo -e "${color}[${prefix}]${COLOR_RESET} ${message}"
}

set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Uso: $0 {singularity|conda} [proxy_url]"
  echo "Ejemplos:"
  echo "  $0 singularity"
  echo "  $0 conda"
  echo "  $0 conda http://proxy.san.gva.es:8080"
  exit 1
fi

MODE="$1"
PROXY_URL=""

# Si hay un segundo parámetro, asumimos que es el proxy
if [[ $# -eq 2 ]]; then
  PROXY_URL="$2"
  format_message "INFO" "Se configurará proxy: $PROXY_URL" "$INFO"
fi

# Detectar el usuario que llama a sudo para editar sus ficheros .bashrc, .zshrc
REAL_USER="${SUDO_USER:-root}"
REAL_USER_HOME="$(eval echo ~"$REAL_USER")"

echo -e "${BOLD}======================================${COLOR_RESET}"
echo -e "${BOLD} Script setup_env.sh - Opción: $MODE ${COLOR_RESET}"
echo -e "${BOLD} Usuario real:       $REAL_USER${COLOR_RESET}"
echo -e "${BOLD} Directorio HOME:    $REAL_USER_HOME${COLOR_RESET}"
echo -e "${BOLD}======================================${COLOR_RESET}"

# Función para hacer preguntas con validación de respuestas
ask_question() {
  local prompt="$1"   # Mensaje de la pregunta
  local default="$2"  # Valor por defecto (S o N)

  while true; do
    # Colorear la pregunta
    read -rp "$(echo -e "${PREGUNTA}[PREGUNTA]${COLOR_RESET} $prompt")" answer
    
    # Si está vacía, usar el valor por defecto
    if [[ -z "$answer" ]]; then
      answer="$default"
    fi
    
    # Normalizar respuesta a minúsculas
    answer=$(echo "$answer" | tr '[:upper:]' '[:lower:]')
    
    case "$answer" in
      s|y|si|yes) return 0 ;;  # Éxito = Sí
      n|no) return 1 ;;        # Fallo = No
      q|quit|exit) 
        format_message "INFO" "Saliendo del script por petición del usuario." "$INFO"
        exit 0 
        ;;
      *) format_message "INFO" "Por favor responde (s)í, (n)o o (q) para salir." "$INFO" ;;
    esac
  done
}

# Función auxiliar para ejecutar comandos conda como el usuario real
run_as_user_with_conda() {
  local cmd="$1"
  sudo -u "$REAL_USER" /bin/bash -c "source $REAL_USER_HOME/miniconda3/etc/profile.d/conda.sh && $cmd"
}

###############################
# FUNCIONES: DESINSTALACIÓN   #
###############################

# ----- Verificar espacio en disco -----
check_disk_space() {
  local required_space_mb=5000  # ~5GB para la instalación completa
  local available_space_mb=$(df -m /usr/local | awk 'NR==2 {print $4}')
  
  format_message "INFO" "Espacio disponible: ${available_space_mb}MB, requerido: ${required_space_mb}MB" "$INFO"
  
  if [[ $available_space_mb -lt $required_space_mb ]]; then
    format_message "ERROR" "Espacio insuficiente en disco. Se necesitan al menos ${required_space_mb}MB" "$ERROR"
    return 1
  fi
  
  return 0
}

# Usar la función antes de la instalación
echo
if ! check_disk_space; then
  read -rp "$(echo -e "${PREGUNTA}[PREGUNTA]${COLOR_RESET} ¿Continuar a pesar de la advertencia de espacio? (s/N): ")" ans
  case "$ans" in
    [sS]|[sS][iI]) format_message "INFO" "Continuando con espacio limitado..." "$INFO" ;;
    *) format_message "INFO" "Instalación cancelada." "$INFO" && exit 1 ;;
  esac
fi

# ----- Desinstalar Go -----
remove_go() {
  echo
  format_message "INFO" "Eliminando Go..." "$INFO"

  # 1. Quitar paquetes de apt
  format_message "INFO" "Buscando paquetes 'golang-go', 'golang-*' en apt..." "$INFO"
  GO_PKGS="$(dpkg -l | grep -E 'golang-go|golang-[0-9\.]+|golang-doc' || true)"
  if [[ -n "$GO_PKGS" ]]; then
    format_message "INFO" "Se encontraron paquetes de Go instalados:" "$INFO"
    echo "$GO_PKGS"
    format_message "INFO" "Procediendo a desinstalarlos..." "$INFO"
    apt remove --purge -y golang-go golang-doc || true
    apt autoremove --purge -y || true
  else
    format_message "INFO" "No hay paquetes de Go instalados con apt (o no se han encontrado)." "$INFO"
  fi

  # 2. Borrar /usr/local/go si existe (instalaciones manuales)
  if [[ -d /usr/local/go ]]; then
    format_message "INFO" "Eliminando /usr/local/go..." "$INFO"
    rm -rf /usr/local/go
  fi

  # 3. Eliminar directorio ~/go (GOPATH) si el usuario desea
  if [[ -d "$REAL_USER_HOME/go" ]]; then
    echo
    if ask_question " ¿Eliminar también la carpeta '$REAL_USER_HOME/go' (GOPATH)? (s/N): " "n"; then
      rm -rf "$REAL_USER_HOME/go"
      format_message "OK" "Se eliminó $REAL_USER_HOME/go." "$OK"
    else
      format_message "INFO" "Se mantiene $REAL_USER_HOME/go." "$INFO"
    fi
  fi

  # 4. Eliminar exportaciones en .bashrc y .zshrc
  echo
  format_message "INFO" "Limpiando referencias a Go en .bashrc / .zshrc del usuario $REAL_USER..." "$INFO"

  for SHELL_RC in "$REAL_USER_HOME/.bashrc" "$REAL_USER_HOME/.zshrc"
  do
    [[ -f "$SHELL_RC" ]] || continue
    # Backup
    cp "$SHELL_RC" "$SHELL_RC.bak_$(date +%Y%m%d%H%M%S)"
    
    # Usar múltiples patrones simples en lugar de uno complejo
    sed -i '/usr\/local\/go\/bin/d' "$SHELL_RC"
    sed -i '/GOROOT/d' "$SHELL_RC"
    sed -i '/GOPATH/d' "$SHELL_RC"
  done

  format_message "INFO" "Referencias a Go eliminadas de los archivos de configuración del shell." "$INFO"
  format_message "INFO" "(Reinicia o abre una nueva shell para que surta efecto)." "$INFO"
}

# ----- Instalar Go (v1.24.1) -----
install_go() {
  echo
  format_message "INFO" "Instalando Go 1.24.1..."

  # Asegurarnos de tener wget
  apt-get update -y
  apt-get install -y wget

  # Creamos un directorio de trabajo temporal
  WORK_DIR="/tmp/go-install.$$"
  mkdir -p "$WORK_DIR"
  cd "$WORK_DIR"

  # Descargar Go con verificación de integridad
  format_message "INFO" "Descargando Go 1.24.1..." "$INFO"
  wget -q https://go.dev/dl/go1.24.1.linux-amd64.tar.gz

  # Verificación SHA256 (opcional pero recomendado)
  # Puedes obtener el valor actual desde https://go.dev/dl/
  EXPECTED_SHA256="cb2396bae64183cdccf81a9a6df0aea3bce9511fc21469fb89a0c00470088073"
  ACTUAL_SHA256=$(sha256sum go1.24.1.linux-amd64.tar.gz | cut -d' ' -f1)
  if [[ "$EXPECTED_SHA256" != "$ACTUAL_SHA256" ]]; then
    format_message "ERROR" "Verificación de integridad fallida para go1.24.1.linux-amd64.tar.gz" "$ERROR"
    exit 1
  fi

  # Extraer en /usr/local
  format_message "INFO" "Extrayendo Go en /usr/local..." "$INFO"
  rm -rf /usr/local/go
  tar -C /usr/local -xzf go1.24.1.linux-amd64.tar.gz

  # Añadir PATH y GOPATH a la shell del usuario
  format_message "INFO" "Configurando variables de entorno para Go..." "$INFO"
  for SHELL_RC in "$REAL_USER_HOME/.bashrc" "$REAL_USER_HOME/.zshrc"
  do
    [[ -f "$SHELL_RC" ]] || continue
    # Backup antes de modificar
    cp "$SHELL_RC" "$SHELL_RC.bak_$(date +%Y%m%d%H%M%S)"
    
    # Añadir las líneas de configuración
    {
      echo -e "\n# Configuración de Go (añadido por setup_env.sh)"
      echo "export GOPATH=\${HOME}/go"
      echo "export PATH=/usr/local/go/bin:\${PATH}:\${GOPATH}/bin"
    } >> "$SHELL_RC"
  done

  # Verificar la instalación
  export PATH=/usr/local/go/bin:$PATH
  if command -v go &>/dev/null; then
    format_message "OK" "Go 1.24.1 instalado correctamente:" "$OK"
    go version
  else
    format_message "ERROR" "No se pudo verificar la instalación de Go" "$ERROR"
  fi

  # Limpieza
  cd /
  rm -rf "$WORK_DIR"
}

# ----- Desinstalar Singularity -----
remove_singularity() {
  echo
  format_message "INFO" "Procediendo a eliminar Singularity..." "$INFO"

  # Mostrar la versión actual si está disponible
  if command -v singularity &>/dev/null; then
    CURRENT_VERSION=$(singularity --version 2>/dev/null || echo "Versión desconocida")
    format_message "INFO" "Versión detectada: $CURRENT_VERSION" "$INFO"
  fi

  # 1. Quitar paquetes singulares de apt (búsqueda más específica)
  format_message "INFO" "Buscando paquetes 'singularity' en apt..." "$INFO"
  SING_PKGS="$(dpkg -l | grep -E 'singularity|apptainer' || true)"
  if [[ -n "$SING_PKGS" ]]; then
    format_message "INFO" "Se encontraron paquetes instalados:" "$INFO"
    echo "$SING_PKGS"
    format_message "INFO" "Desinstalando con apt..." "$INFO"
    apt remove --purge -y singularity-container apptainer || true
    apt autoremove --purge -y || true
  else
    format_message "INFO" "No hay paquetes 'singularity' instalados con apt." "$INFO"
  fi

  # 2. Eliminar binarios locales
  for BIN in singularity apptainer; do
    if command -v $BIN &>/dev/null; then
      BIN_PATH="$(which $BIN)"
      format_message "INFO" "Eliminando binario $BIN_PATH..." "$INFO"
      rm -f "$BIN_PATH"
    fi
  done

  # 3. Eliminar directorios de configuración y librerías
  for DIR in /usr/local/libexec/singularity /usr/local/etc/singularity \
             /usr/local/libexec/apptainer /usr/local/etc/apptainer; do
    if [[ -d "$DIR" ]]; then
      format_message "INFO" "Eliminando $DIR..." "$INFO"
      rm -rf "$DIR"
    fi
  done

  format_message "INFO" "Singularity ha sido eliminado (o no se encontraba)." "$INFO"
}
# ----- Desinstalar COMPLETAMENTE conda/Miniconda/Anaconda -----
remove_conda() {
  echo
  echo -e "${BOLD}\033[38;5;208m!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  echo -e "${BOLD} ADVERTENCIA: Se eliminarán TODOS los entornos conda,       \033[38;5;208m"
  echo -e "${BOLD} la instalación de Miniconda/Anaconda y las referencias en  \033[38;5;208m"
  echo -e "${BOLD} .bashrc / .zshrc.                                          \033[38;5;208m"
  echo -e "${BOLD}!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!${COLOR_RESET}"
  echo
  read -rp "$(echo -e "${PREGUNTA}[PREGUNTA]${COLOR_RESET} ¿Realmente deseas borrar TODAS las instalaciones de conda? (s/N): ")" ans
  case "$ans" in
    [sS]|[sS][iI])
      format_message "INFO" "Procediendo a eliminación total de conda..." "$INFO"

      # 1. Intentar desactivar conda (por si está activa)
      #    Evita algunos bloqueos, pero puede no ser esencial.
      if command -v conda &>/dev/null; then
        conda deactivate || true
      fi

      # 2. Eliminar directorios típicos de conda/Anaconda/Miniconda
      #    (Hay gente que lo instala en ~/anaconda3 o ~/miniconda3)
      # Antes de eliminar directorios importantes
      for cdir in "$REAL_USER_HOME/miniconda3" "$REAL_USER_HOME/anaconda3" "$REAL_USER_HOME/conda" "$REAL_USER_HOME/.conda"; do
        if [[ -d "$cdir" && "$cdir" != "/" && "$cdir" != "$REAL_USER_HOME" ]]; then
          format_message "INFO" "Eliminando directorio $cdir..." "$INFO"
          rm -rf "$cdir"
        elif [[ -d "$cdir" ]]; then
          format_message "PELIGRO" "No se eliminará $cdir por seguridad" "$PELIGRO"
        fi
      done

      # Eliminar también el archivo .condarc si existe
      if [[ -f "$REAL_USER_HOME/.condarc" ]]; then
        format_message "INFO" "Eliminando archivo de configuración $REAL_USER_HOME/.condarc..." "$INFO"
        # Crear backup primero
        cp "$REAL_USER_HOME/.condarc" "$REAL_USER_HOME/.condarc.bak_$(date +%Y%m%d%H%M%S)"
        rm -f "$REAL_USER_HOME/.condarc"
      fi

      # 3. Eliminar líneas en .bashrc / .zshrc que hagan 'conda init' o similar
      for SHELL_RC in "$REAL_USER_HOME/.bashrc" "$REAL_USER_HOME/.zshrc"
      do
        [[ -f "$SHELL_RC" ]] || continue
        cp "$SHELL_RC" "$SHELL_RC.bak_$(date +%Y%m%d%H%M%S)"
        
        # Eliminar el bloque completo de inicialización de conda
        sed -i '/# >>> conda initialize >>>/,/# <<< conda initialize <<</d' "$SHELL_RC"
        
        # También eliminar líneas sueltas que contengan referencias a conda por seguridad
        sed -i '/conda\.sh\|conda activate\|conda init\|\.conda\|anaconda3\|miniconda3/d' "$SHELL_RC"
        
        format_message "INFO" "Se ha limpiado el archivo $SHELL_RC de referencias a conda." "$INFO"
      done

      format_message "INFO" "Se han eliminado referencias a conda de los archivos de configuración." "$INFO"
      format_message "INFO" "Para que surtan efecto, cierra y vuelve a abrir la terminal (o haz 'source' manual)." "$INFO"
      ;;
    *)
      format_message "INFO" "Se aborta la eliminación de conda." "$INFO"
      ;;
  esac
}

###############################
# FUNCIONES: INSTALACIONES    #
###############################

# ----- Instalar Singularity (v3.8.7) -----
install_singularity() {
  echo
  format_message "INFO" "Instalando Singularity v3.8.7..." "$INFO"

  # Dependencias
  apt-get update -y
  apt-get install -y build-essential libseccomp-dev pkg-config squashfs-tools cryptsetup runc git

  # Usar PID para crear un nombre único de directorio temporal
  WORK_DIR="/tmp/singularity-install.$$"
  mkdir -p "$WORK_DIR"
  cd "$WORK_DIR"

  # Clonar y compilar
  git clone https://github.com/hpcng/singularity.git
  cd singularity
  
  # Verificar que la versión existe antes de hacer checkout
  SINGULARITY_VERSION="3.8.7"
  format_message "INFO" "Verificando que v${SINGULARITY_VERSION} existe en el repositorio..." "$INFO"
  if ! git tag | grep -q "v${SINGULARITY_VERSION}"; then
    format_message "ERROR" "Versión ${SINGULARITY_VERSION} no encontrada" "$ERROR"
    exit 1
  fi
  
  git checkout "v${SINGULARITY_VERSION}"

  ./mconfig
  make -C ./builddir
  make -C ./builddir install

  # Verificar la instalación
  if command -v singularity &>/dev/null; then
    format_message "OK" "Singularity v${SINGULARITY_VERSION} instalado correctamente:" "$OK"
    singularity --version
  else
    format_message "ERROR" "No se pudo verificar la instalación de Singularity" "$ERROR"
  fi

  # Limpieza
  cd /
  rm -rf "$WORK_DIR"
}

# ----- Instalar entorno virtual de Python con Snakemake -----
install_python_venv() {
  echo
  format_message "INFO" "Instalando Python 3.12 y creando entorno virtual..." "$INFO"

  # Instalar Python 3.12 y herramientas necesarias
  apt-get update -y
  apt-get install -y python3.12 python3.12-venv python3.12-dev
  
  # Crear el directorio para el entorno virtual si no existe
  ENV_DIR="$REAL_USER_HOME/snake_env"
  
  # Crear entorno como usuario real (no como root)
  sudo -u "$REAL_USER" python3.12 -m venv "$ENV_DIR"
  
  # Instalar paquetes dentro del entorno virtual
  sudo -u "$REAL_USER" bash -c "source $ENV_DIR/bin/activate && \
    pip install --upgrade pip && \
    pip install snakemake==9.1.1 snakemake-wrapper-utils==0.7.2 pandas openpyxl gitpython"
  
  # Verificar instalación
  if sudo -u "$REAL_USER" bash -c "source $ENV_DIR/bin/activate && snakemake --version"; then
    format_message "OK" "Entorno virtual creado correctamente en $ENV_DIR" "$OK"
  else
    format_message "ERROR" "Hubo un problema al crear el entorno virtual" "$ERROR"
    return 1
  fi
  echo
  # Opcional: Añadir un alias al .bashrc para activar fácilmente
  read -rp "$(echo -e "${PREGUNTA}[PREGUNTA]${COLOR_RESET} ¿Añadir alias 'snake_env' para activar el entorno? (s/N): ")" ans_alias
  case "$ans_alias" in
    [sS]|[sS][iI])
      echo
      for SHELL_RC in "$REAL_USER_HOME/.bashrc" "$REAL_USER_HOME/.zshrc"
      do
        [[ -f "$SHELL_RC" ]] || continue
        # Backup antes de modificar
        cp "$SHELL_RC" "$SHELL_RC.bak_$(date +%Y%m%d%H%M%S)"
        
        # Añadir alias
        echo -e "\n# Alias para activar entorno virtual snake_env (añadido por setup_env.sh)" >> "$SHELL_RC"
        echo "alias snake_env='source $ENV_DIR/bin/activate'" >> "$SHELL_RC"
        
        format_message "INFO" "Alias añadido a $SHELL_RC" "$INFO"
      done
      
      format_message "INFO" "Ahora puedes usar el comando 'snake_env' para activar el entorno" "$INFO"
      ;;
    *)
      format_message "INFO" "No se añadirá alias. Para activar el entorno usa:" "$INFO"
      echo "       source $ENV_DIR/bin/activate"
      ;;
  esac
  
  echo
  format_message "INFO" "También puedes añadir este entorno a VS Code:" "$INFO"
  echo "  1. Abre VS Code"
  echo "  2. Presiona Ctrl+Shift+P"
  echo "  3. Escribe 'Python: Select Interpreter'"
  echo "  4. Selecciona el entorno en $ENV_DIR/bin/python3.12"
  
  return 0
}

# ----- Instalar Miniconda (py312_25.1.1-2) -----
install_conda() {
  echo
  format_message "INFO" "Instalando la versión py312_25.1.1-2 de Miniconda3 para Linux x86_64..." "$INFO"

  # Asegurarnos de tener wget
  apt-get update -y
  apt-get install -y wget

  # Descargamos en home del usuario real (no en /root)
  cd "$REAL_USER_HOME"
  sudo -u "$REAL_USER" wget -q https://repo.anaconda.com/miniconda/Miniconda3-py312_25.1.1-2-Linux-x86_64.sh -O miniconda.sh

  # Verificar checksum SHA256
  EXPECTED_SHA256="4766d85b5f7d235ce250e998ebb5a8a8210cbd4f2b0fea4d2177b3ed9ea87884"
  ACTUAL_SHA256=$(sha256sum miniconda.sh | cut -d' ' -f1)
  if [[ "$EXPECTED_SHA256" != "$ACTUAL_SHA256" ]]; then
    format_message "ERROR" "Verificación de integridad fallida para miniconda.sh" "$ERROR"
    exit 1
  fi

  # Damos permisos de ejecución
  sudo -u "$REAL_USER" chmod u+x miniconda.sh

  # Instalación desatendida en ~/miniconda3
  sudo -u "$REAL_USER" bash miniconda.sh -b -p "$REAL_USER_HOME/miniconda3"

  # Borrar instalador
  sudo -u "$REAL_USER" rm -f miniconda.sh

  format_message "INFO" "Miniconda instalada en $REAL_USER_HOME/miniconda3." "$INFO"

  # Inicializar conda en shells del usuario
  run_as_user_with_conda "conda init bash"
  if [[ -f "$REAL_USER_HOME/.zshrc" ]]; then
    run_as_user_with_conda "conda init zsh"
  fi

  # Configurar proxy si se especificó
  if [[ -n "$PROXY_URL" ]]; then
    format_message "INFO" "Configurando proxy para conda: $PROXY_URL" "$INFO"
    run_as_user_with_conda "conda config --set proxy_servers.http $PROXY_URL && conda config --set proxy_servers.https $PROXY_URL"
    format_message "OK" "Proxy configurado para conda." "$OK"
  fi
  
  echo
  format_message "INFO" "Se ha inicializado conda en la shell del usuario $REAL_USER." "$INFO"
  format_message "INFO" "Reabriendo la terminal (o 'source ~/.bashrc') se activará conda (base)." "$INFO"

  # Verificación de instalación
  if command -v conda &>/dev/null; then
    format_message "OK" "Instalación de conda verificada:" "$OK"
    run_as_user_with_conda "conda --version"
  else
    format_message "ADVERTENCIA" "No se pudo verificar la instalación de conda" "$ADVERTENCIA"
    format_message "SUGERENCIA" "Reinicia la terminal y ejecuta 'conda --version' manualmente" "$SUGERENCIA"
  fi
}

###############################
# LÓGICA PRINCIPAL DE FLUJO   #
###############################
case "$MODE" in
  singularity)
    format_message "INFO" "Modo: Singularity" "$INFO"

    # 1. Ver si hay Go instalado y ofrecer desinstalarlo
    GO_AVAILABLE=false
    if command -v go &>/dev/null || [[ -d /usr/local/go ]] || [[ -d /opt/apps/go ]]; then
      GO_AVAILABLE=true
      GO_PATH=""

      # Determinar la ruta a Go buscando en ubicaciones comunes
      if command -v go &>/dev/null; then
        GO_PATH=$(command -v go)
        format_message "INFO" "Se ha detectado Go en el PATH: $GO_PATH" "$INFO"
      elif [[ -d /usr/local/go/bin ]]; then
        GO_PATH="/usr/local/go/bin/go"
        format_message "INFO" "Se ha detectado Go en: /usr/local/go" "$INFO"
      elif [[ -d /opt/apps/go/bin ]]; then
        GO_PATH="/opt/apps/go/bin/go"
        format_message "INFO" "Se ha detectado Go en: /opt/apps/go" "$INFO"
      fi

      # Mostrar versión con PATH expandido
      if [[ -n "$GO_PATH" ]] && [[ -x "$GO_PATH" ]]; then
        "$GO_PATH" version || true
      else
        # Intentar con PATH expandido manualmente
        PATH="$PATH:/usr/local/go/bin:/opt/apps/go/bin" go version || true
      fi

      if ask_question " ¿Desinstalar Go previo? (s/N): " "n"; then
        remove_go
        GO_AVAILABLE=false
      else
        format_message "INFO" "Se mantiene la instalación actual de Go." "$INFO"
      fi
    else
      format_message "INFO" "Go no se detecta en el sistema." "$INFO"
    fi

    # 2. Ofrecer instalar Go 1.24.1 si no está disponible
    if ! $GO_AVAILABLE; then
      if ask_question " ¿Instalar Go 1.24.1? (s/N): " "n"; then
        install_go
        GO_AVAILABLE=true
      else
        format_message "INFO" "No se instalará Go." "$INFO"
      fi
    fi

    # 3. Ver si hay Singularity y ofrecer desinstalar
    SINGULARITY_AVAILABLE=false
    if command -v singularity &>/dev/null; then
      SINGULARITY_AVAILABLE=true
      format_message "INFO" "Se ha detectado Singularity: $(which singularity)" "$INFO"
      singularity --version || true

      if ask_question " ¿Desinstalar Singularity previo? (s/N): " "n"; then
        remove_singularity
        SINGULARITY_AVAILABLE=false
      else
        format_message "INFO" "Se mantiene la instalación actual de Singularity." "$INFO"
      fi
    else
      format_message "INFO" "Singularity no se detecta en el sistema." "$INFO"
    fi

    # 4. Ofrecer instalar la versión 3.8.7
    if ! $SINGULARITY_AVAILABLE; then
      if ask_question " ¿Instalar Singularity v3.8.7? (s/N): " "n"; then
        # Comprobar si Go está disponible (requerido para compilar Singularity)
        if ! $GO_AVAILABLE; then
          format_message "ADVERTENCIA" "Go es necesario para instalar Singularity." "$ADVERTENCIA"
          if ask_question " ¿Instalar Go 1.24.1 primero? (S/n): " "s"; then
            install_go
            GO_AVAILABLE=true
          else
            format_message "INFO" "No se puede instalar Singularity sin Go." "$INFO"
            # No se puede usar break aquí ya que no estamos en un bucle
            continue 2
          fi
        fi

        install_singularity
        SINGULARITY_AVAILABLE=true
      else
        format_message "INFO" "No se instalará Singularity." "$INFO"
      fi
    fi

    # 5. Ofrecer instalar entorno Python para Snakemake
    if ask_question " ¿Crear entorno virtual de Python con Snakemake? (s/N): " "n"; then
      install_python_venv
    else
      format_message "INFO" "No se instalará entorno Python." "$INFO"
    fi
    ;;

  conda)
    format_message "INFO" "Modo: conda" "$INFO"

    # Variable para rastrear si conda está disponible
    CONDA_AVAILABLE=false

    # 1. Ver si conda está instalado - buscar en ubicaciones típicas
    if command -v conda &>/dev/null || [[ -f "$REAL_USER_HOME/miniconda3/bin/conda" ]] || [[ -f "$REAL_USER_HOME/anaconda3/bin/conda" ]]; then
      # Determinar la ruta a conda
      CONDA_PATH=""
      if command -v conda &>/dev/null; then
        CONDA_PATH=$(command -v conda)
      elif [[ -f "$REAL_USER_HOME/miniconda3/bin/conda" ]]; then
        CONDA_PATH="$REAL_USER_HOME/miniconda3/bin/conda"
      elif [[ -f "$REAL_USER_HOME/anaconda3/bin/conda" ]]; then
        CONDA_PATH="$REAL_USER_HOME/anaconda3/bin/conda"
      fi

      format_message "INFO" "Se detecta conda en: $CONDA_PATH" "$INFO"
      sudo -u "$REAL_USER" "$CONDA_PATH" --version || true
      echo
      format_message "ADVERTENCIA" "Esto puede corresponder a Anaconda, Miniconda u otra variante." "$ADVERTENCIA"
      echo
      # Preguntar si desinstalar usando la función ask_question
      if ask_question " ¿Desinstalar conda? (s/N): " "n"; then
        remove_conda
        CONDA_AVAILABLE=false
      else
        format_message "INFO" "Se mantiene la instalación actual de conda." "$INFO"
        CONDA_AVAILABLE=true
      fi
    else
      format_message "INFO" "No se detecta conda en el sistema." "$INFO"
    fi
    echo
    # 2. Si no hay conda disponible, ofrecer instalar
    if ! $CONDA_AVAILABLE; then
      if ask_question " ¿Instalar Miniconda3: Conda 25.1.1 - Python 3.12.9 (s/N): " "n"; then
        install_conda
        CONDA_AVAILABLE=true
      else
        format_message "INFO" "No se instalará Miniconda." "$INFO"
      fi
    fi

    # 3. Configuración de canales y mamba (solo si hay conda disponible)
    if $CONDA_AVAILABLE; then
      echo
      if ask_question " ¿Quieres configurar canales (conda-forge, bioconda) e instalar mamba? (s/N): " "n"; then
        format_message "INFO" "Configurando conda..." "$INFO"

        sudo -u "$REAL_USER" /bin/bash -c "source $REAL_USER_HOME/miniconda3/etc/profile.d/conda.sh && \
          conda config --remove-key channels || true && \
          conda config --add channels defaults && \
          conda config --add channels bioconda && \
          conda config --add channels conda-forge && \
          conda config --set channel_priority strict && \
          conda update -n base conda -y && \
          conda update --all -y && \
          conda install -n base -c conda-forge mamba -y"

        format_message "OK" "Canales configurados y mamba instalado." "$OK"

        # Variable para rastrear si mamba está disponible
        MAMBA_AVAILABLE=true
      else
        format_message "INFO" "No se configurarán canales ni mamba." "$INFO"
        MAMBA_AVAILABLE=false
      fi

      # 4. Creación del entorno snake
      echo
      if ask_question " ¿Quieres crear el entorno 'snake' con Snakemake? (s/N): " "n"; then
        format_message "INFO" "Creando entorno 'snake' con Snakemake..." "$INFO"

        # Si mamba está disponible, usarlo, sino usar conda
        # En la sección donde defines INSTALL_CMD, añade "conda" a los paquetes
        if $MAMBA_AVAILABLE; then
          INSTALL_CMD="mamba create -n snake -y -c conda-forge bioconda::snakemake=9.1.1 \
                      bioconda::snakemake-wrapper-utils=0.7.2 \
                      pandas openpyxl git"
        else
          INSTALL_CMD="conda create -n snake -y -c conda-forge bioconda::snakemake=9.1.1 \
                      bioconda::snakemake-wrapper-utils=0.7.2 \
                      pandas openpyxl git"
        fi

        # Ejecutar la instalación
        sudo -u "$REAL_USER" /bin/bash -c "source $REAL_USER_HOME/miniconda3/etc/profile.d/conda.sh && \
          $INSTALL_CMD && \
          conda activate snake && \
          snakemake --version"

        format_message "OK" "Entorno 'snake' creado correctamente." "$OK"

        # Asegurar que conda esté siempre disponible
        echo
        format_message "INFO" "Asegurando disponibilidad de conda en todos los entornos..." "$INFO"
        for SHELL_RC in "$REAL_USER_HOME/.bashrc" "$REAL_USER_HOME/.zshrc"
        do
          [[ -f "$SHELL_RC" ]] || continue
          
          # Verificar si ya existe una línea que añada miniconda3/bin al PATH
          if ! grep -q "miniconda3/bin" "$SHELL_RC"; then
            echo "# Asegurar acceso a conda en todos los entornos" >> "$SHELL_RC"
            echo 'export PATH="$HOME/miniconda3/bin:$PATH"' >> "$SHELL_RC"
            format_message "INFO" "Se ha añadido miniconda3/bin al PATH en $SHELL_RC" "$INFO"
          fi
        done
        format_message "INFO" "Para activarlo usa: conda activate snake" "$INFO"
      else
        format_message "INFO" "No se creará el entorno snake." "$INFO"
      fi
    else
      format_message "ADVERTENCIA" "Se requiere tener conda instalado para configurar canales, mamba o crear entornos." "$ADVERTENCIA"
    fi
    ;;

  *)
    format_message "ERROR" "Modo inválido: $MODE" "$ERROR"
    echo "Usa: $0 {singularity|conda}"
    exit 1
    ;;
esac

echo
echo -e "${BOLD}\033[32m====================================================================${COLOR_RESET}"
format_message "FIN" "Script 'setup_conda_singularity.sh' finalizado correctamente." "$FIN"
echo -e "${BOLD}\033[32m====================================================================${COLOR_RESET}"
exit 0