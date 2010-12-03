# Convert m4b audio book to mp3

This is a simple python script to convert m4b audio books
to mp3 files (or any other format ffmpeg supports), split into chapters.


## Requirements

* Python (tested with 2.7)
* ffmpeg


## Usage

$ m4b.py [-h] [-o DIR] [--ffmpeg-bin EXE] [--encode [STR]] [--ext EXT] [--skip-chapters] [--debug] &lt;m4b file&gt;

    <m4b file>            m4b file to be converted>

    optional arguments:
    -h, --help            show this help message and exit
    -o DIR,
    --output-dir DIR      directory to store encoded files
    --ffmpeg-bin EXE      path to ffmpeg binary
    --encode [STR]        custom encoding string (see below)
    --ext EXT             extension of encoded files
    --skip-chapters       do not split files by chapter
    --debug               display debug messages and save to log file

Use `--encode` if you wish to do more advanced encoding than the
default setting (`--encode "-acodec libmp3lame -ar 44100"`). For more options
visit the [ffmpeg docs](http://www.ffmpeg.org/ffmpeg-doc.html).
