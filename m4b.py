#!/usr/bin/env python

import argparse
import ctypes
import datetime
import logging
import os
import re
import shutil
import subprocess
import sys
from textwrap import dedent


class Chapter:
    """MP4 Chapter.

    Start, end, and duration times are stored in seconds.
    """
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


def run_command(args, cmdstr, values, action, ignore_errors=False, **kwargs):
    cmd = []
    for opt in cmdstr.split(' '):
        cmd.append(opt % values)
    proc = subprocess.Popen(cmd, **kwargs)
    (stdout, output) = proc.communicate()
    if not ignore_errors and not proc.returncode == 0:
        msg = dedent('''
            An error occurred while %s.
              Command: %s
              Return code: %s
              Output: ---->
            %s''')
        args.log.error(msg % (action, cmdstr % values, proc.returncode, output))
        sys.exit(1)
    return output

def parse_args():
    """Parse command line arguments."""

    parser = argparse.ArgumentParser(
        description='Split m4b audio book by chapters.')

    parser.add_argument('-o', '--output-dir', help='directory to store encoded files',
                        metavar='DIR')
    parser.add_argument('--custom-name', default='%(title)s', metavar='"STR"',
                        help='customize chapter filenames (see README)')
    parser.add_argument('--ffmpeg', default='ffmpeg', metavar='BIN',
                        help='path to ffmpeg binary')
    parser.add_argument('--encoder', metavar='BIN',
                        help='path to encoder binary (default: ffmpeg)')
    parser.add_argument('--encode-opts', default='-y -i %(infile)s -acodec libmp3lame -ar %(sample_rate)s -ab %(bit_rate)sk %(outfile)s',
                        metavar='"STR"', help='custom encoding string (see README)')
    parser.add_argument('--ext', default='mp3', help='extension of encoded files')
    parser.add_argument('--generate-wav', action='store_true',
                        help='generate .wav file that other encoders can use')
    parser.add_argument('--skip-encoding', action='store_true',
                        help='do not encode audio (keep as .mp4)')
    parser.add_argument('--no-mp4v2', action='store_true',
                        help='use ffmpeg to retrieve chapters (not recommended)')
    parser.add_argument('--debug', action='store_true',
                        help='output debug messages and save to m4b.log')
    parser.add_argument('filename', help='m4b file to be converted')

    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = os.path.join(os.path.dirname(__file__),
            os.path.splitext(os.path.basename(args.filename)))[0]

    if args.encoder is None:
        args.encoder = args.ffmpeg

    if args.skip_encoding:
        args.temp_dir = args.output_dir
    else:
        args.temp_dir = os.path.join(args.output_dir, 'temp')

    return args

def setup_logging(args):
    """Setup logger. In debug mode debug messages will be saved to m4b.log."""

    log = logging.getLogger('m4b')

    sh = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s: %(message)s")

    sh.setFormatter(formatter)

    if args.debug:
        level = logging.DEBUG
        fh = logging.FileHandler(os.path.join(os.path.dirname(__file__), 'm4b.log'), 'w')
        fh.setLevel(level)
        log.addHandler(fh)
    else:
        level = logging.INFO

    log.setLevel(level)
    sh.setLevel(level)
    log.addHandler(sh)

    log.info('m4bsplit started.')
    if args.debug:
        s = ['Options:']
        for k, v in args.__dict__.items():
            s.append('    %s: %s' % (k, v))
        log.debug('\n'.join(s))
    return log

def ffmpeg_metadata(args):
    """Load metadata using the command output from ffmpeg.

    Note: Not all chapter types are supported by ffmpeg and there's no Unicode support.
    """

    chapters = []

    values = dict(ffmpeg=args.ffmpeg, infile=args.filename)
    cmd = '%(ffmpeg)s -i %(infile)s'
    args.log.debug('Retrieving metadata from output of command: %s' % (cmd % values))

    output = run_command(args, cmd, values, 'retrieving metadata from ffmpeg output',
        ignore_errors=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    raw_metadata = (output.split("    Chapter ")[0]).split('Input #')[1]
    raw_chapters = output.split("    Chapter ")[1:]

    # Parse stream and metadata
    re_stream = re.compile(r'[\s]+Stream .*: Audio: .*, ([\d]+) Hz, .*, .*, ([\d]+) kb\/s')
    re_duration = re.compile(r'[\s]+Duration: (.*), start: (.*), bitrate: ([\d]+) kb\/s')

    try:
        stream = re_stream.search(output)
        sample_rate, bit_rate = int(stream.group(1)), int(stream.group(2))
    except Exception:
        sample_rate, bit_rate = 44100, 64

    metadata = {}
    for meta in raw_metadata.split('\n')[2:]:
        if meta.startswith('  Duration: '):
            m = re_duration.match(meta)
            if m:
                metadata['duration'] = m.group(1).strip()
                metadata['start'] = m.group(2).strip()
        else:
            key = (meta.split(':')[0]).strip()
            value = (':'.join(meta.split(':')[1:])).strip()
            metadata[key] = value

    # Parse chapters
    re_chapter = re.compile('^#[\d\.]+: start ([\d|\.]+), end ([\d|\.]+)[\s]+Metadata:[\s]+title[\s]+: (.*)')
    n = 1
    for raw_chapter in raw_chapters:
        m = re.match(re_chapter, raw_chapter.strip())
        start = float(m.group(1)) * 1000
        e = float(m.group(2)) * 1000
        duration = e - start
        title = unicode(m.group(3), errors='ignore').strip()
        chapter = Chapter(num=n, title=title, start=start, end=e)
        chapters.append(chapter)
        n += 1

    return chapters, sample_rate, bit_rate, metadata

def mp4v2_metadata(args):
    """Load metadata with libmp4v2. Supports both chapter types and Unicode."""

    from libmp4v2 import MP4File

    mp4 = MP4File(args.filename)
    mp4.load_meta()

    chapters = mp4.chapters
    sample_rate = mp4.sample_rate
    bit_rate = mp4.bit_rate
    metadata = {}

    mp4.close()

    return chapters, sample_rate, bit_rate, metadata

def load_metadata(args):
    args.log.info('Loading metadata...')
    if args.no_mp4v2:
        return ffmpeg_metadata(args)
    else:
        return mp4v2_metadata(args)

def show_metadata_info(args, chapters, sample_rate, bit_rate, metadata):
    """Show a summary of the parsed metadata."""

    args.log.info(dedent('''
        Metadata:
          Chapters: %d
          Bit rate: %d kbit/s
          Sampling freq: %d Hz''' % (len(chapters), bit_rate, sample_rate)))

    if args.debug and chapters:
        args.log.debug(dedent('''
            Chapter data:
              %s''' % '\n'.join(['  %s' % c for c in chapters])))

    if args.no_mp4v2 and not chapters:
        args.log.warning("No chapters were found. There may be chapters present but ffmpeg can't read them. Try to enable mp4v2.")
        args.log.info('Do you want to continue? (y/N)')
        cont = raw_input('> ')
        if not cont.lower().startswith('y'):
            sys.exit(1)

def encode(args, sample_rate, bit_rate, metadata):
    """Encode audio."""

    # Create output and temp directory
    if not os.path.isdir(args.output_dir):
        os.makedirs(args.output_dir)
    if not os.path.isdir(args.temp_dir):
        os.makedirs(args.temp_dir)

    if args.skip_encoding:
        encoded_file = args.filename
        args.ext = 'mp4'
        return encode_file
    else:
        filename = '%s.%s' % (os.path.splitext(os.path.basename(args.filename))[0], args.ext)
        encoded_file = os.path.join(args.temp_dir, filename)

    if os.path.isfile(encoded_file):
        args.log.info("Found a previously encoded file '%s'. Do you want to re-encode it? (y/N/q)" % encoded_file)
        i = raw_input('> ')
        if i.lower().startswith('q'):
            sys.exit(0)
        elif not i.lower() == 'y':
            return encoded_file

    # Build encoding options
    values = dict(encoder=args.encoder, infile=args.filename,
        sample_rate=sample_rate, bit_rate=bit_rate, outfile=encoded_file)

    if not '%(infile)s' in args.encode_opts or not '%(outfile)s' in args.encode_opts:
        args.log.error('%(outfile)s needs to be present in the encoding options. See the README.')
        sys.exit(1)

    encode_cmd = '%%(encoder)s %s' % args.encode_opts

    args.log.info('Encoding audio...')
    args.log.debug('Encoding with command: %s' % (encode_cmd % values))

    run_command(args, encode_cmd, values, 'encoding audio')

    return encoded_file

def split(args, encoded_file, chapters):
    """Split encoded audio file into chapters.

    Note: ffmpeg on Windows can't take filenames with Unicode characters so we
    write the split file to a non-unicode temp file then rename it. This is not
    necessary on other platforms.
    """
    re_format = re.compile(r'%\(([A-Za-z0-9]+)\)')
    re_sub = re.compile(r'[\\\*\?\"\<\>\|]+')

    for chapter in chapters:
        values = dict(num=chapter.num, title=chapter.title, start=chapter.start, end=chapter.end, duration=chapter.duration())
        chapter_name = re_sub.sub('', (args.custom_name % values).replace('/', '-'))
        if not isinstance(chapter_name, unicode):
            chapter_name = unicode(chapter_name, 'utf-8')

        if sys.platform.startswith('win'):
            filename = os.path.join(args.output_dir, '_tmp_%d.%s' % (chapter.num, args.ext))
        else:
            filename = os.path.join(args.output_dir, '%s.%s' % (chapter_name, args.ext))

        values = dict(ffmpeg=args.ffmpeg, duration=str(chapter.duration()),
            start=str(chapter.start), outfile=encoded_file, infile=filename)
        split_cmd = '%(ffmpeg)s -y -acodec copy -t %(duration)s -ss %(start)s -i %(outfile)s %(infile)s'

        args.log.info("Splitting chapter %2d/%2d '%s'..." % (chapter.num, len(chapters), chapter_name))
        args.log.debug('Splitting with command: %s' % (split_cmd % values))

        run_command(args, split_cmd, values, 'splitting audio file', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Rename file
        if sys.platform.startswith('win'):
            new_filename = os.path.join(args.output_dir, '%s.%s' % (chapter_name, args.ext))
            args.log.debug('Renaming "%s" to "%s".\n' % (filename, new_filename))
            shutil.move(filename, new_filename)

def main():
    args = parse_args()
    args.log = setup_logging(args)

    chapters, sample_rate, bit_rate, metadata = load_metadata(args)
    show_metadata_info(args, chapters, sample_rate, bit_rate, metadata)

    encoded_file = encode(args, sample_rate, bit_rate, metadata)

    split(args, encoded_file, chapters)

if __name__ == '__main__':
    main()
