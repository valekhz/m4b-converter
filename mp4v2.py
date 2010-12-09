import ctypes
import sys


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

class Chapter:
    def __init__(self, title=None, duration=None):
        self.title = title
        self.duration = duration

class MP4:
    def __init__(self, filename):
        self.filename = filename
        self.__load()
    
    def __load(self):
        fileHandle = libmp4v2.MP4Read(self.filename, 0)
        self.__load_chapters(fileHandle)
        libmp4v2.MP4Close(fileHandle)
    
    def __load_chapters(self, fileHandle):
        chapter_list = ctypes.POINTER(libmp4v2.MP4Chapter)()
        chapter_count = ctypes.c_uint32(0)
        chapter_type = libmp4v2.MP4GetChapters(fileHandle, ctypes.byref(chapter_list),
            ctypes.byref(chapter_count), libmp4v2.MP4ChapterType.Any)
        chapters = []
        for n in range(0, chapter_count.value):
            chapter = chapter_list[n]
            chapters.append(Chapter(title=chapter.title, duration=chapter.duration))
        self.chapters = chapters
        self.chapter_type = chapter_type


if sys.platform.startswith('linux'):
    try:
        dll = ctypes.CDLL('libvlc.so')
    except OSError:
        dll = ctypes.CDLL('libvlc.so.5')
elif sys.platform.startswith('win'):
    dll = ctypes.CDLL('libmp4v2.dll')


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
