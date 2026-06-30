#!/data/data/com.termux/files/usr/bin/bash

set -euxo pipefail

options=()
usage() {
	echo "Usage: $(basename "$0") [-h] [-s] file_list"
	echo "  -s: Split chapters"
}
while getopts "hs" arg; do
	case $arg in
	h)
		usage
		exit 0
		;;
	s)
		options+=("--split-chapters")
		;;
	*)
		usage
		exit 1
		;;
	esac
done
shift $((OPTIND - 1))
if [[ $# -ne 1 ]]; then
	usage
	exit 0
fi

options+=("--trim-silence")

file_list=$1

if [[ ! -f $file_list ]]; then
	echo "File not found: $file_list"
	exit 1
fi

while read -r line; do
	python3 download_audio.py -o ./ --audio-format remux "${options[@]}" "$line"
done <$file_list
