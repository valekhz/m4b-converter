#!/usr/bin/env python
import argparse
import ctypes
import datetime
import logging
import os
import re
import subprocess
import sys

import libmp4v2


class Chapter:
    def __init__(self, title=None, start=None, end=None, num=None):
        self.title = title
        self.start = round(int(start)/1000.0, 3)
        self.end = round(int(end)/1000.0, 3)
        self.num = num

    def duration(self):
        if self.start is None or self.end is None:
            return None
        else:
            return round(self.end - self.start, 3)

    def __str__(self):
        return '<Chapter Title="%s", Start=%s, End=%s, Duration=%s>' % (
            self.title,
            datetime.timedelta(seconds=self.start),
            datetime.timedelta(seconds=self.end),
            datetime.timedelta(seconds=self.duration()))

class M4B:
    """
    Parse, encode, and split M4B file.
    """

    def __init__(self):
        self.__parse_args()
        self.__setup_logging()
        self.__load_meta()

    """
    Encode and split files.
    """
    def convert(self):
        self.encode()
        self.split()
        self.log.info('Conversion finished successfully!')

    """
    Encode m4b file with specified codec.
    """
    def encode(self):
        # Create output directory
        if not self.chapters:
            self.log.warning('No chapter information was found. Skipping chapter splitting...')
            self.skip_splitting = True

        if self.skip_splitting or self.skip_encoding:
            self.temp_dir = self.output_dir
        else:
            self.temp_dir = os.path.join(self.output_dir, 'temp')
        if not os.path.isdir(self.temp_dir):
            os.makedirs(self.temp_dir)

        if self.skip_encoding:
            self.encoded_file = self.filename
            self.ext = 'mp4'
            return None
        else:
            self.encoded_file = os.path.join(self.temp_dir, '%s.%s' % (os.path.splitext(os.path.basename(self.filename))[0], self.ext))

        # Skip encoding?
        if os.path.isfile(self.encoded_file):
            msg = "Found a previously encoded file '%s'. Do you want to re-encode it? (y/N/q)" % self.encoded_file
            self.log.info(msg)
            i = raw_input('> ')
            if i.lower() == 'q':
                self.log.debug('Quitting script.')
                sys.exit()
            elif i.lower() != 'y':
                return None

        # Build encoding options unless already specified
        if self._encode is None:
            self._encode = '-acodec libmp3lame -ar %s -ab %sk' % (self.time_scale, self.bit_rate)

        encode_cmd = [self.ffmpeg_bin, '-y', '-i', self.filename]
        encode_cmd += self._encode.split(' ')
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
        if self.skip_splitting:
            return None
        
        re_format = re.compile(r'%\(([A-Za-z0-9]+)\)')
        re_sub = re.compile(r'[\\\*\?\"\<\>\|]+')

        for chapter in self.chapters:
            values = {}
            try:
                for x in re_format.findall(self.custom_name):
                    values[x] = getattr(chapter, x)
            except AttributeError:
                self.log.error('"%s" is an invalid variable. Check the README on how to use --custom-name.' % x)
                sys.exit()
            chapter_name = re.sub(re_sub, '', (self.custom_name % values).replace('/', '-'))
            filename = os.path.join(self.output_dir, '%s.%s' % (chapter_name, self.ext))
            split_cmd = [self.ffmpeg_bin, '-y', '-acodec', 'copy', '-t',
                         str(chapter.duration()), '-ss', str(chapter.start),
                         '-i', self.encoded_file, filename]
            self.log.info("Splitting chapter %2d/%2d '%s'..." % (chapter.num, len(self.chapters), chapter_name))
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
    Load chapters, bitrate, and more..
    """
    def __load_meta(self):
        self.log.info('Loading meta data...')

        fileHandle = libmp4v2.MP4Read(self.filename, 0)

        trackid = libmp4v2.get_audio_track_id(fileHandle)
        self.time_scale = libmp4v2.MP4GetTrackTimeScale(fileHandle, trackid)
        self.bit_rate = round(libmp4v2.MP4GetTrackBitRate(fileHandle, trackid) / 1000.0, 0)

        if not self.time_scale > 0:
            self.time_scale = 44100
        if not self.bit_rate > 0:
            self.bit_rate = 64

        self.log.debug('Time Scale: %s Hz, Bit Rate: %s kbit/s' % (self.time_scale, self.bit_rate))

        # Chapters
        chapter_list = ctypes.POINTER(libmp4v2.MP4Chapter)()
        chapter_count = ctypes.c_uint32(0)
        chapter_type = libmp4v2.MP4GetChapters(fileHandle, ctypes.byref(chapter_list),
            ctypes.byref(chapter_count), libmp4v2.MP4ChapterType.Any)

        start = 0
        self.chapters = []
        for n in range(0, chapter_count.value):
            c = Chapter(title=chapter_list[n].title,
                        start=start,
                        end=start+int(chapter_list[n].duration),
                        num=n+1)
            self.chapters.append(c)
            start += chapter_list[n].duration

        libmp4v2.MP4Close(fileHandle)

        self.log.info('Found %d chapter(s).' % len(self.chapters))
        self.log.debug('Chapter type: %s' % chapter_type)

    """
    Parse command line arguments.
    """
    def __parse_args(self):
        parser = argparse.ArgumentParser(
            description='Convert m4b audio book to mp3 file(s).')

        parser.add_argument('-o', '--output-dir',
            help='directory to store encoded files',
            metavar='DIR')
        parser.add_argument('--custom-name',
            default='%(title)s',
            help='Customize chapter filenames (see README)',
            metavar='STR',
            nargs='?')
        parser.add_argument('--ffmpeg-bin',
            default='ffmpeg',
            help='path to ffmpeg binary',
            metavar='EXE')
        parser.add_argument('--encode', nargs='?',
            dest='_encode',
            help='custom encoding string (see README)',
            metavar='STR')
        parser.add_argument('--ext',
            default='mp3',
            help='extension of encoded files')
        parser.add_argument('--skip-splitting',
            action='store_true',
            help='do not split files by chapter')
        parser.add_argument('--skip-encoding',
            action='store_true',
            help='do not encode audio (keep as .mp4)')
        parser.add_argument('--debug',
            action='store_true',
            help='display debug messages and save to log file')
        parser.add_argument('filename',
            help='m4b file to be converted',
            metavar='<m4b file>')

        args = parser.parse_args()

        if args.output_dir is None:
            args.output_dir = os.path.join(os.path.dirname(__file__),
                os.path.splitext(os.path.basename(args.filename))[0])
        self.output_dir = args.output_dir
        self.custom_name = args.custom_name
        self.ffmpeg_bin = args.ffmpeg_bin
        if sys.platform.startswith('win'):
            curr = os.path.join(os.path.dirname(__file__), 'ffmpeg.exe')
            if os.path.isfile(curr):
                self.ffmpeg_bin = curr
        self._encode = args._encode
        self.ext = args.ext
        self.skip_splitting = args.skip_splitting
        self.skip_encoding = args.skip_encoding
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
        if self.debug:
            s = ['Options:']
            for k, v in self.args.__dict__.items():
                s.append('    %s: %s' % (k, v))
            self.log.debug('\n'.join(s))


if __name__ == '__main__':
    book = M4B()
    book.convert()

