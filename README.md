# create a conda environment
conda create -n zai_assistant python=3.11

# activate the conda environment
conda activate zai_assistant

# install requirements with pip
pip install -r requirements.txt

# install ffmpeg
brew install ffmpeg

# run application
uvicorn app:app --reload 
# open the link http://127.0.0.1:8000 or whatever link it's presented to you in the terminal
