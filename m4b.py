import argparse
import ctypes
import datetime
import logging
import os
import re
import subprocess
import sys

import mp4v2


class Chapter:
    def __init__(self, title=None, start=None, end=None):
        self.title = title
        self.start = int(start)
        self.end = int(end)

    def duration(self):
        if self.start is None or self.end is None:
            return None
        else:
            return self.end - self.start

    def __str__(self):
        return '<Chapter Title="%s", Start=%s, End=%s, Duration=%s>' % (
            self.title,
            datetime.timedelta(seconds=self.start/1000),
            datetime.timedelta(seconds=self.end/1000),
            datetime.timedelta(seconds=self.duration()/1000))

class M4B:
    """
    Parse, encode, and split M4B file.
    """

    def __init__(self):
        self.__parse_args()
        self.__setup_logging()
        self.__get_chapters()
    
    """
    Encode m4b file with specified codec.
    """
    def encode(self):
        # Create output directory
        if not self.chapters:
            self.log.warning('No chapter information was found. Skipping chapter splitting...')
            self.skip_chapters = True

        if self.skip_chapters:
            self.temp_dir = self.output_dir
        else:
            self.temp_dir = os.path.join(self.output_dir, 'temp')
        if not os.path.isdir(self.temp_dir):
            os.makedirs(self.temp_dir)

        self.encoded_file = os.path.join(self.temp_dir, '%s.%s' % (os.path.splitext(os.path.basename(self.filename))[0], self.ext))

        # Skip encoding?
        if os.path.isfile(self.encoded_file):
            msg = "Found a previously encoded file '%s'. Do you want to overwrite it? (y/N/q)" % self.encoded_file
            self.log.info(msg)
            i = raw_input('')
            if i.lower() == 'q':
                self.log.debug('Quitting script.')
                sys.exit()
            elif i.lower() != 'y':
                return None

        encode_cmd = [self.ffmpeg_bin, '-y', '-i', self.filename]
        for arg in self.encode_str.split(' '):
            encode_cmd.append(arg)
        encode_cmd.append(self.encoded_file)
        self.log.info('Encoding audio book...')
        self.log.debug('Encoding with command: %s' % ' '.join(encode_cmd))
        try:
            subprocess.check_output(encode_cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as error:
            self.log.error('''An error occurred while encoding m4b file.
  Command: %s
  Return code: %s
  Output: --->
%s
''' % (' '.join(encode_cmd), error.returncode, error.output))
            sys.exit()
    
    """
    Split encoded file by chapter.
    """
    def split(self):
        for chapter in self.chapters:
            n = list.index(self.chapters, chapter) + 1
            filename = os.path.join(self.output_dir, '%s.%s' % (chapter.title, self.ext))
            split_cmd = [self.ffmpeg_bin, '-y', '-acodec', 'copy', '-t',
                         str(chapter.duration()/1000.0), '-ss', str(chapter.start/1000.0),
                         '-i', self.encoded_file, filename]
            self.log.info("Splitting chapter %2d/%2d '%s'..." % (n, len(self.chapters), chapter.title))
            self.log.debug('Splitting with command: %s\n' % ' '.join(split_cmd))
            try:
                subprocess.check_output(split_cmd, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as error:
                self.log.error('''An error occurred while splitting file.
  Command: %s
  Return code: %s
  Output: --->
%s
''' % (' '.join(split_cmd), error.returncode, error.output))
                sys.exit()

    
    """
    Parse chapter data from ffmpeg output.
    """
    def __get_chapters(self):
        fileHandle = mp4v2.MP4Read(self.filename, 0)

        chapter_list = ctypes.POINTER(mp4v2.MP4Chapter)()
        chapter_count = ctypes.c_uint32(0)
        chapter_type = mp4v2.MP4GetChapters(fileHandle, ctypes.byref(chapter_list),
            ctypes.byref(chapter_count), mp4v2.MP4ChapterType.Any)

        start = 0
        self.chapters = []
        for n in range(0, chapter_count.value):
            c = Chapter(title=chapter_list[n].title,
                        start=start,
                        end=start+int(chapter_list[n].duration))
            self.chapters.append(c)
            start += chapter_list[n].duration

        mp4v2.MP4Close(fileHandle)

        self.log.debug('Found %d chapter(s).' % len(self.chapters))

    """
    Parse command line arguments.
    """
    def __parse_args(self):
        parser = argparse.ArgumentParser(
            description='Convert m4b audio book to mp3 file(s).')
        
        parser.add_argument('-o', '--output-dir',
            dest='output_dir',
            help='directory to store encoded files',
            metavar='DIR')
        parser.add_argument('--ffmpeg-bin',
            default='ffmpeg',
            dest='ffmpeg_bin',
            help='path to ffmpeg binary',
            metavar='EXE')
        parser.add_argument('--encode', nargs='?',
            default='-acodec libmp3lame -ar 44100',
            dest='encode_str',
            help='custom encoding string (see README)',
            metavar='STR')
        parser.add_argument('--ext',
            default='mp3',
            dest='ext',
            help='extension of encoded files')
        parser.add_argument('--skip-chapters',
            action='store_true',
            dest='skip_chapters',
            help='do not split files by chapter')
        parser.add_argument('--debug',
            action='store_true',
            dest='debug',
            help='display debug messages and save to log file')
        parser.add_argument('filename',
            help='m4b file to be converted',
            metavar='<m4b file>')
        
        args = parser.parse_args()

        if args.output_dir is None:
            self.output_dir = os.path.join(os.path.dirname(__file__),
                os.path.splitext(os.path.basename(args.filename))[0])
        else:
            self.output_dir = args.output_dir
        self.ffmpeg_bin = args.ffmpeg_bin
        self.encode_str = args.encode_str
        self.ext = args.ext
        self.skip_chapters = args.skip_chapters
        self.debug = args.debug
        self.filename = args.filename
        self.args = args
    
    def __setup_logging(self):
        logger = logging.getLogger('m4b')

        if self.debug:
            level = logging.DEBUG
            ch = logging.StreamHandler()
            fh = logging.FileHandler(os.path.join(os.path.dirname(__file__),
                                     'm4b.log'), 'w')
        else:
            level = logging.INFO
            ch = logging.StreamHandler()

        formatter = logging.Formatter("%(levelname)s: %(message)s")
        ch.setFormatter(formatter)

        logger.setLevel(level)
        ch.setLevel(level)

        logger.addHandler(ch)
        if self.debug:
            fh.setLevel(level)
            logger.addHandler(fh)

        self.log = logger

        self.log.debug('Conversion script started.')
        self.log.debug('''Specified arguments:
    source: %s
    output: %s
    ffmpeg: %s
    encode: %s
    extension: %s
    skip-chapters: %s''' % (self.filename, self.output_dir,
            self.ffmpeg_bin, self.encode_str, self.ext, self.skip_chapters))


if __name__ == '__main__':
    book = M4B()
    book.encode()
    if not book.skip_chapters:
        book.split()
        book.log.info('Conversion finished successfully!')

