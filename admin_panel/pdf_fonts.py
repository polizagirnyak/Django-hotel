import os
import glob
import shutil
from pathlib import Path
from django.conf import settings
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


#Шрифты с кириллицы
_FONT_CANDIDATES = [
# DejaVu — есть на Linux по умолчанию
('DejaVuSans.ttf',      'DejaVuSans-Bold.ttf'),
# Liberation — Linux (аналог Arial)
('LiberationSans-Regular.ttf', 'LiberationSans-Bold.ttf'),
# FreeSans — Linux
('FreeSans.ttf',        'FreeSansBold.ttf'),
# Arial — Windows / macOS
('arial.ttf',           'arialbd.ttf'),
('Arial.ttf',           'Arial Bold.ttf'),
# Tahoma — Windows
('tahoma.ttf',          'tahomabd.ttf'),
# Verdana — Windows
('verdana.ttf',         'verdanab.ttf'),
# Calibri — Windows / Office
('calibri.ttf',         'calibrib.ttf'),
# Segoe UI — Windows 10+
('segoeui.ttf',         'segoeuib.ttf'),
]

#Директории поиска
_SEARCH_DIRS = [
    str(Path(settings.BASE_DIR)/'static'/'fonts'),
    str(Path(settings.BASE_DIR)/'fonts'),
    #linux
    '/usr/share/fonts/truetype/dejavu',
    '/usr/share/fonts/truetype/liberation',
    '/usr/share/fonts/truetype/freefont',
    '/usr/share/fonts/truetype/ubuntu',
    '/usr/share/fonts/truetype/noto',
    '/usr/share/fonts/truetype',
    '/usr/share/fonts',
    '/usr/local/share/fonts',
    os.path.expanduser('~/.fonts'),

    #MacOs
    '/System/Library/Fonts/Supplemental',
    '/System/Library/Fonts',
    '/Library/Fonts',
    os.path.expanduser('~/Library/Fonts'),

    #Windows
    'C:/Windows/Fonts',
    '/mnt/c/Windows/Fonts',
    os.path.expanduser('~/AppData/Local/Microsoft/Windows/Fonts'),
]

def _find_font_file(file_name):
    for directory in _SEARCH_DIRS:
        candidate = os.path.join(directory, file_name)
        if os.path.isfile(candidate):
            return candidate
    for found in glob.glob('/usr/share/fonts/**/'+file_name, recursive=True):
        return found
    return None

def _check_static_fonts_dir():
    fonts_dir = Path(settings.BASE_DIR)/'static'/'fonts'
    fonts_dir.mkdir(parents=True, exist_ok=True)
    return fonts_dir

def get_cyrillic_fonts():
    fonts_dir = _check_static_fonts_dir()
    for regular_name, bold_name in _FONT_CANDIDATES:
        project_regular = fonts_dir/regular_name
        project_bold = fonts_dir/bold_name

        if project_regular.exists() and project_bold.exists():
            return str(project_regular), str(project_bold)

        sys_regular = _find_font_file(regular_name)
        sys_bold = _find_font_file(bold_name)

        if sys_regular and sys_bold:
            try:
                shutil.copyfile(sys_regular, project_regular)
                shutil.copyfile(sys_bold, project_bold)
            except OSError:
                return sys_regular, sys_bold
            return str(project_regular), str(project_bold)
        if sys_regular:
            try:
                shutil.copyfile(sys_regular, project_regular)
                shutil.copyfile(sys_regular, project_bold)
            except OSError:
                return sys_regular, sys_bold
            return str(project_regular), str(project_bold)


_registered = {}
def register_cyrillic_fonts():
    regular_path, bold_path = get_cyrillic_fonts()
    regular_name = 'CyrillicRegular'
    bold_name = 'CyrillicBold'


    if regular_path not in _registered:
        pdfmetrics.registerFont(TTFont(regular_name, regular_path))
        pdfmetrics.registerFont(TTFont(bold_name, bold_path))
        pdfmetrics.registerFontFamily(
            'Cyrillic',
            normal= regular_name,
            bold=bold_name,
            italic=regular_name,
            boldItalic=bold_name
        )
        _registered[regular_path] = regular_name
        _registered[bold_path] = bold_name
    return regular_name, bold_name