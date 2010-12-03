# Convert m4b audio book to mp3

This is a simple python script to convert m4b audio books to a group of mp3
files split by chapter.


## Requirements

* Python (tested with 2.7)
* ffmpeg (make sure it's in your `PATH` or use `--ffmpeg-bin`)


## Usage

There are two ways to run this script:

1. Drag your `.m4b` file onto `m4b.py` and it will automatically convert with
   the standard settings.
2. Using the command line which also offers more advanced options.


### Command Line Help

    m4b.py [-h] [-o DIR] [--ffmpeg-bin EXE] [--encode [STR]] [--ext EXT] [--skip-chapters] [--debug] <m4b file>

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


### Examples

Simple conversion using default settings:

    python m4b.py myfile.m4b

Using a custom ffmpeg encode string:

    python m4b.py --encode "-acodec libmp3lame -ar 22050 -ab 128k" myfile.m4b
