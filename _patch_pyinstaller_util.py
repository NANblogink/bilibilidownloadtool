import os

util_path = os.path.join(
    r'C:\Users\22739\AppData\Local\Programs\Python\Python310\lib\site-packages',
    'PyInstaller', 'lib', 'modulegraph', 'util.py'
)

with open(util_path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '    yield from (i for i in dis.get_instructions(code_object) if i.opname != "EXTENDED_ARG")'
new = '    try:\n        yield from (i for i in dis.get_instructions(code_object) if i.opname != "EXTENDED_ARG")\n    except IndexError:\n        pass'

if old in content and 'except IndexError' not in content:
    content = content.replace(old, new)
    with open(util_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('PATCHED successfully')
elif 'except IndexError' in content:
    print('Already patched')
else:
    print('Pattern not found - manual patch needed')
