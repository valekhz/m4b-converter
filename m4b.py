import argparse
import logging
import os
import re
import subprocess
import sys


def exit():
    raw_input("Press 'Enter' to quit.")
    sys.exit()

class M4BConverter:

    """
    Initiate converter.
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
        if len(self.chapters) == 0:
            self.log.warning('No chapter information was found. Skipping chapter splitting...')
            self.skip_chapters = True

        if self.skip_chapters:
            self.temp_dir = self.output_dir
        else:
            self.temp_dir = os.path.join(self.output_dir, 'temp')
        if not os.path.isdir(self.temp_dir):
            os.makedirs(self.temp_dir)
        
        self.encoded_file = os.path.join(self.temp_dir, '%s.%s' % (os.path.splitext(os.path.basename(self.filename))[0], self.ext))

        # Skip encoding if the encoded filename already exists.
        if not os.path.isfile(self.encoded_file):
            encode_cmd = [self.ffmpeg_bin, '-i', self.filename]
            for arg in self.encode_str.split(' '):
                encode_cmd.append(arg)
            encode_cmd.append(self.encoded_file)
            self.log.debug('Encoding with command: %s' % ' '.join(encode_cmd))
            ret = subprocess.call(encode_cmd)
            if not ret == 0:
                self.log.error('An error occurred while encoding audio book.')
                exit()
        else:
            self.log.info("Found a previously encoded file. Delete '%s' if you wish to re-encode." % self.encoded_file)
    
    """
    Split encoded file by chapter.
    """
    def split(self):
        for chapter in self.chapters:
            n = list.index(self.chapters, chapter) + 1
            filename = os.path.join(self.output_dir,
                '%s.%s' % (chapter['title'], self.ext))
            split_cmd = [self.ffmpeg_bin, '-acodec', 'copy', '-t',
                         str(chapter['duration']), '-ss', str(chapter['start']),
                         '-i', self.encoded_file, filename]
            if self.debug:
                self.log.debug("Splitting chapter %2d/%2d with command: %s" % (n,
                    len(self.chapters), ' '.join(split_cmd)))
            else:
                self.log.info("Splitting chapter %2d/%2d '%s'..." % (n,
                    len(self.chapters), chapter['title']))
            ret = subprocess.call(split_cmd)
            if not ret == 0:
                self.log.error('An error occurred while splitting encoded file.')
                exit()

    
    """
    Parse chapter data from ffmpeg output.
    """
    def __get_chapters(self):
        cmd = '%s -i "%s"' % (self.ffmpeg_bin, self.filename)
        self.log.debug('Retrieving chapter data from output of command: %s' % cmd)
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        output = proc.communicate()[0]

        raw = output.split("    Chapter ")[1:]
        re_chapter = re.compile('^#[\d\.]+: start ([\d|\.]+), end ([\d|\.]+)[\s]+Metadata:[\s]+title[\s]+: (.*)')
        
        chapters = []
        for raw_chapter in raw:
            m = re.match(re_chapter, raw_chapter.strip())
            start = float(m.group(1))
            e = float(m.group(2))
            duration = e - start
            title = unicode(m.group(3), errors='ignore').strip()
            chapter = dict(title=title, start=start, duration=duration)
            chapters.append(chapter)

        self.chapters = chapters
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
        
        self.args = parser.parse_args()

        # TODO: Fix drop m4b file on py file
        #os.chdir(os.path.abspath(os.path.dirname(__file__)))

        if self.args.output_dir is None:
            self.output_dir = os.path.join(os.path.dirname(__file__),
                os.path.splitext(os.path.basename(self.args.filename))[0])
        else:
            self.output_dir = self.args.output_dir
        self.ffmpeg_bin = self.args.ffmpeg_bin
        self.encode_str = self.args.encode_str
        self.ext = self.args.ext
        self.skip_chapters = self.args.skip_chapters
        self.debug = self.args.debug
        self.filename = self.args.filename
    
    def __setup_logging(self):
        logger = logging.getLogger('m4b')

        if self.debug:
            level = logging.DEBUG
            ch = logging.StreamHandler()
            fh = logging.FileHandler(os.path.join(os.path.dirname(__file__),
                                     'm4b_debug.log'), 'w')
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
    skip-chapters: %s''' % (self.filename, self.output_dir,
            self.ffmpeg_bin, self.skip_chapters))


if __name__ == '__main__':
    m4b = M4BConverter()
    m4b.encode()
    if not m4b.skip_chapters:
        m4b.split()
        m4b.log.info('Conversion finished successfully!')
