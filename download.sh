#!/data/data/com.termux/files/usr/bin/bash

file=$1

if [[ ! -f $file ]] ; then
  echo "File not found: $file"
  exit 1
fi

while read -r line; do
  python3 download_audio.py -o ./ --audio-format remux "$line"
done < $file

