import ctypes
import os.path
import sys


if sys.platform.startswith('linux'):
    try:
        dll = ctypes.CDLL('libmp4v2.so')
    except OSError:
        dll = ctypes.CDLL('libmp4v2.so.0')
elif sys.platform.startswith('win'):
    p = os.path.join(os.path.dirname(__file__), 'libmp4v2.dll')
    if not os.path.isfile(p):
        p = 'libmp4v2.dll'
    dll = ctypes.CDLL(p)
else:
    raise NotImplementedError('O/S %r not supported' % sys.platform)


class _Enum(ctypes.c_ulong):
    _names={}

    def __str__(self):
        n = self._names.get(self.value, '') or ('FIXME_(%r)' % (self.value,))
        return '.'.join((self.__class__.__name__, n))

    def __repr__(self):
        return '.'.join((self.__class__.__module__, self.__str__()))

    def __eq__(self, other):
        return ( (isinstance(other, _Enum)       and self.value == other.value)
              or (isinstance(other, (int, long)) and self.value == other) )

    def __ne__(self, other):
        return not self.__eq__(other)

class MP4ChapterType(_Enum):
    _names = {
        0: 'None',
        1: 'Any',
        2: 'Qt',
        4: 'Nero'
    }
MP4ChapterType._None = MP4ChapterType(0)
MP4ChapterType.Any = MP4ChapterType(1)
MP4ChapterType.Qt = MP4ChapterType(2)
MP4ChapterType.Nero = MP4ChapterType(4)

class MP4Chapter(ctypes.Structure):
    _fields_ = [
        ('duration', ctypes.c_uint64),
        ('title', ctypes.c_char * 1024)
    ]


class MP4File:
    '''
    Helper class.
    '''
    def __init__(self, filename):
        self.filename = filename
        self.handle = MP4Read(self.filename, 0)

    def load_meta(self):
        from m4b import Chapter

        self.audio_track = self.__get_audio_track_id()
        self.sample_rate = MP4GetTrackTimeScale(self.handle, self.audio_track)
        self.bit_rate = round(MP4GetTrackBitRate(self.handle, self.audio_track) / 1000.0, 0)

        if not self.sample_rate:
            self.sample_rate = 44100
        if not self.bit_rate:
            self.bit_rate = 64

        # Chapters
        chapter_list = ctypes.POINTER(MP4Chapter)()
        chapter_count = ctypes.c_uint32(0)
        self.chapter_type = MP4GetChapters(self.handle, ctypes.byref(chapter_list),
            ctypes.byref(chapter_count), MP4ChapterType.Any)

        start = 0
        chapters = []
        for n in range(0, chapter_count.value):
            c = Chapter(title=chapter_list[n].title,
                        start=start,
                        end=start+int(chapter_list[n].duration),
                        num=n+1)
            chapters.append(c)
            start += chapter_list[n].duration
        self.chapters = chapters

    def close(self):
        MP4Close(self.handle)

    def __get_audio_track_id(self):
        tracks_count = MP4GetNumberOfTracks(self.handle, None, 0)
        for n in range(1, tracks_count+1):
            tt = MP4GetTrackType(self.handle, n)
            if tt == 'soun':
                return n
        raise Exception('No audio track found.')


if hasattr(dll, 'MP4Close'):
    p = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
    f = ((1,),)
    MP4Close = p(('MP4Close', dll), f)

if hasattr(dll, 'MP4Read'):
    p = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint)
    f = ((1,), (1,))
    MP4Read = p(('MP4Read', dll), f)

if hasattr(dll, 'MP4GetChapters'):
    p = ctypes.CFUNCTYPE(MP4ChapterType, ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(MP4Chapter)),
                         ctypes.POINTER(ctypes.c_uint32), MP4ChapterType)
    f = ((1,), (1,), (1,), (1,))
    MP4GetChapters = p(('MP4GetChapters', dll), f)

if hasattr(dll, 'MP4GetTrackLanguage'):
    p = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p)
    f = ((1,), (1,), (1,))
    MP4GetTrackLanguage = p(('MP4GetTrackLanguage', dll), f)

if hasattr(dll, 'MP4GetTrackType'):
    p = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_uint32)
    f = ((1,), (1,))
    MP4GetTrackType = p(('MP4GetTrackType', dll), f)

if hasattr(dll, 'MP4GetNumberOfTracks'):
    p = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint8)
    f = ((1,), (1,), (1,))
    MP4GetNumberOfTracks = p(('MP4GetNumberOfTracks', dll), f)

if hasattr(dll, 'MP4GetTrackTimeScale'):
    p = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32)
    f = ((1,), (1,))
    MP4GetTrackTimeScale = p(('MP4GetTrackTimeScale', dll), f)

if hasattr(dll, 'MP4GetTrackBitRate'):
    p = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32)
    f = ((1,), (1,))
    MP4GetTrackBitRate = p(('MP4GetTrackBitRate', dll), f)
