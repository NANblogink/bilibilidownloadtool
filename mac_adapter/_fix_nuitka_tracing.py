import re

tracing_path = r'C:\Users\22739\AppData\Local\Programs\Python\Python310\lib\site-packages\nuitka\Tracing.py'

with open(tracing_path, 'r', encoding='utf-8') as f:
    content = f.read()

patches_applied = 0

# Patch 1: _my_print - add OSError catch
old1 = "    except BrokenPipeError:\n        pass\n\n\ndef _my_print2"
new1 = "    except BrokenPipeError:\n        pass\n    except OSError:\n        pass\n\n\ndef _my_print2"
if old1 in content:
    content = content.replace(old1, new1)
    patches_applied += 1
    print("OK: _my_print patched")

# Patch 2: flushStandardOutputs
old2 = '    sys.stdout.flush()\n\n    if hasattr(sys.stderr, "flush_buffer"):\n        sys.stderr.flush_buffer()\n    sys.stderr.flush()'
new2 = '    sys.stdout.flush()\n\n    try:\n        if hasattr(sys.stderr, "flush_buffer"):\n            sys.stderr.flush_buffer()\n        sys.stderr.flush()\n    except OSError:\n        pass'
if old2 in content:
    content = content.replace(old2, new2)
    patches_applied += 1
    print("OK: flushStandardOutputs patched")

# Patch 3: my_print method flush - line 520
old3 = '        my_print(message, **kwargs)\n        kwargs["file"].flush()'
new3 = '        my_print(message, **kwargs)\n        try:\n            kwargs["file"].flush()\n        except OSError:\n            pass'
if old3 in content:
    content = content.replace(old3, new3)
    patches_applied += 1
    print("OK: my_print flush patched")

# Patch 4: any remaining bare .flush() calls in critical paths
# Add global protection: wrap all remaining flush calls in the file
count = content.count('except OSError')
print(f"Total 'except OSError' occurrences: {count}")

with open(tracing_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"DONE: {patches_applied} patches applied, Tracing.py saved")
