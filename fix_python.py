from pathlib import Path

p = Path("src/sunnyware/tools/python_eval.py")
t = p.read_text(encoding="utf-8")

old_block = '''        timeout = _sandbox.DEFAULT_TIMEOUT
        ctx = mp.get_context("spawn")
        q = ctx.Queue()
        p = ctx.Process(target=_worker_proc, args=(code, q))

        p.start()
        p.join(timeout)

        if p.is_alive():
            p.terminate()
            p.join()
            return {"error": "execution timed out (" + str(timeout) + "s) and was killed"}

        try:
            result = q.get_nowait()
        except Exception:
            return {"error": "process failed without output"}'''

new_block = '''        timeout = _sandbox.DEFAULT_TIMEOUT
        
        def _execute_in_subprocess():
            ctx = mp.get_context("spawn")
            q = ctx.Queue()
            p = ctx.Process(target=_worker_proc, args=(code, q))
            p.start()
            p.join(timeout)
            if p.is_alive():
                p.terminate()
                p.join()
                return {"error": "execution timed out (" + str(timeout) + "s) and was killed"}
            try:
                res = q.get_nowait()
            except Exception:
                return {"error": "process failed without output"}
            return res

        # Run the blocking multiprocessing code in a thread
        result = await asyncio.to_thread(_execute_in_subprocess)'''

if old_block in t:
    t = t.replace(old_block, new_block)
    print("[ok] SUCCESS: Fixed blocking subprocess call in python_eval.py")
else:
    print("[ERROR] Could not find exact block. You may need to manually edit the file.")

p.write_text(t, encoding="utf-8")
print("[ok] python_eval.py saved")
EOFcd /h/sunnyware && cat << 'EOF' > fix_python.py
from pathlib import Path

p = Path("src/sunnyware/tools/python_eval.py")
t = p.read_text(encoding="utf-8")

old_block = '''        timeout = _sandbox.DEFAULT_TIMEOUT
        ctx = mp.get_context("spawn")
        q = ctx.Queue()
        p = ctx.Process(target=_worker_proc, args=(code, q))

        p.start()
        p.join(timeout)

        if p.is_alive():
            p.terminate()
            p.join()
            return {"error": "execution timed out (" + str(timeout) + "s) and was killed"}

        try:
            result = q.get_nowait()
        except Exception:
            return {"error": "process failed without output"}'''

new_block = '''        timeout = _sandbox.DEFAULT_TIMEOUT
        
        def _execute_in_subprocess():
            ctx = mp.get_context("spawn")
            q = ctx.Queue()
            p = ctx.Process(target=_worker_proc, args=(code, q))
            p.start()
            p.join(timeout)
            if p.is_alive():
                p.terminate()
                p.join()
                return {"error": "execution timed out (" + str(timeout) + "s) and was killed"}
            try:
                res = q.get_nowait()
            except Exception:
                return {"error": "process failed without output"}
            return res

        # Run the blocking multiprocessing code in a thread
        result = await asyncio.to_thread(_execute_in_subprocess)'''

if old_block in t:
    t = t.replace(old_block, new_block)
    print("[ok] SUCCESS: Fixed blocking subprocess call in python_eval.py")
else:
    print("[ERROR] Could not find exact block. You may need to manually edit the file.")

p.write_text(t, encoding="utf-8")
print("[ok] python_eval.py saved")
