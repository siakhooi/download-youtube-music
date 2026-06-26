url := "https://www.youtube.com/watch?v=JEoNjnyd56s"
info:
install-pip:
    pip -r requirements.txt
install-ffmpeg:
    sudo apt install -y ffmpeg
full:
    python3 download_audio.py -o ./ --audio-format remux {{url}}
mp3:
    python3 download_audio.py -o ./ --audio-format mp3 {{url}}
split:
    python3 download_audio.py -o ./ --split-chapters {{url}}
split-flac:
    python3 download_audio.py -o ./ --audio-format flac --split-chapters {{url}}
split-mp3:
    python3 download_audio.py -o ./ --audio-format mp3 --split-chapters {{url}}
split-opus:
    python3 download_audio.py -o ./ --audio-format opus --split-chapters {{url}}
split-remux:
    python3 download_audio.py -o ./ --audio-format remux --split-chapters {{url}}
