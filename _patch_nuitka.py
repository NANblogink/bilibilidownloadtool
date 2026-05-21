import sys

def patch_nuitka_tracing():
    try:
        import nuitka.Tracing as tracing
        original_my_print = tracing._my_print

        def patched_my_print(is_atty, args, kwargs):
            file_output = kwargs.get("file", sys.stdout)
            try:
                original_my_print(is_atty, args, kwargs)
                file_output.flush()
            except BrokenPipeError:
                pass
            except OSError:
                pass

        tracing._my_print = patched_my_print
    except Exception:
        pass

patch_nuitka_tracing()