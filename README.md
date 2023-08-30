# epibac
Pipeline for basic bioinformatic analysis of bacteria and study of AMR and MLST.


## Install CONDA + snakemake

```
wget https://repo.anaconda.com/miniconda/Miniconda3-py38_4.12.0-Linux-x86_64.sh
chmod u+x Miniconda3-py38_4.12.0-Linux-x86_64.sh
./Miniconda3-py38_4.12.0-Linux-x86_64.sh

source ~/.bashrc

conda config --set always_yes yes --set changeps1 yes
conda info -a
conda config --add channels defaults
conda config --add channels bioconda
conda config --add channels conda-forge
conda create -q -n snakemake snakemake=7.8 python=3.8.12 mamba=0.23.3
```

## Add your files

- [ ] [Create](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#create-a-file) or [upload](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#upload-a-file) files
- [ ] [Add files using the command line](https://docs.gitlab.com/ee/gitlab-basics/add-file.html#add-a-file-using-the-command-line) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://gitlab.com/asanzc/epiviral.git
git branch -M main
git push -uf origin main
```
