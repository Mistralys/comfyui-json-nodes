"""Quick verification script for WP-003 (LoadJsonNode) acceptance criteria."""
import json, os, sys, tempfile, time
from unittest.mock import MagicMock

class _Custom:
    def __call__(self, nm): return _CT(nm)
class _CT:
    def __init__(self, nm): self.name = nm
    def Input(self, p, **kw): return dict(__ci__=self.name, param=p, **kw)
    def Output(self, l, **kw): return dict(__co__=self.name, label=l, **kw)
class _io:
    Custom = _Custom()
    class Schema:
        def __init__(self, *, node_id, display_name, category, inputs=None, outputs=None, is_output_node=False, not_idempotent=False):
            self.node_id = node_id; self.display_name = display_name; self.category = category
            self.inputs = inputs or []; self.outputs = outputs or []
    class Combo:
        @staticmethod
        def Input(p, *, options, **kw): return dict(__combo__=True, param=p, options=options, **kw)
    class String:
        @staticmethod
        def Input(p, **kw): return dict(__si__=True, param=p, **kw)
        @staticmethod
        def Output(l, **kw): return dict(__so__=True, label=l, **kw)
    class Int:
        @staticmethod
        def Input(p, **kw): return dict(__ii__=True, param=p, **kw)
        @staticmethod
        def Output(l, **kw): return dict(__io__=True, label=l, **kw)
    class Float:
        @staticmethod
        def Input(p, **kw): return dict(__fi__=True, param=p, **kw)
        @staticmethod
        def Output(l, **kw): return dict(__fo__=True, label=l, **kw)
    class Boolean:
        @staticmethod
        def Input(p, **kw): return dict(__bi__=True, param=p, **kw)
        @staticmethod
        def Output(l, **kw): return dict(__bo__=True, label=l, **kw)
    class NodeOutput:
        def __init__(self, *a): self.values = a
    class ComfyNode: pass

tmpdir = tempfile.mkdtemp()

class _fp:
    _d = tmpdir
    @classmethod
    def get_input_directory(cls): return cls._d
    @classmethod
    def get_output_directory(cls): return tempfile.mkdtemp()

cm = MagicMock()
cm.latest.io = _io
cm.latest.ComfyExtension = object
sys.modules['comfy_api'] = cm
sys.modules['comfy_api.latest'] = cm.latest
sys.modules['folder_paths'] = _fp
sys.modules['typing_extensions'] = MagicMock()

repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo)
import nodes as nd
L = nd.LoadJsonNode
lf = nd._list_json_files

passed = 0; failed = 0

def ok(name):
    global passed; passed += 1; print(f"  PASS: {name}")
def fail(name, msg):
    global failed; failed += 1; print(f"  FAIL: {name} -- {msg}")

# AC1
schema = L.define_schema()
assert schema.node_id == 'Mistralys_LoadJson', schema.node_id
assert schema.display_name == 'JSON Load File', schema.display_name
assert schema.category == 'json'
ok("AC1: node_id='Mistralys_LoadJson', display_name='JSON Load File', category='json'")

# AC2
f1 = os.path.join(tmpdir, 'config.json')
subdir = os.path.join(tmpdir, 'sub')
os.makedirs(subdir, exist_ok=True)
f2 = os.path.join(subdir, 'data.json')
open(f1, 'w').write('{}'); open(f2, 'w').write('{}')
files = lf()
assert 'config.json' in files, files
assert 'sub/data.json' in files, files
assert files == sorted(files), f"not sorted: {files}"
ok("AC2: file listing includes subdirectory files, sorted")

# AC3
with open(f1, 'w') as fh: fh.write('{"key": "value", "n": 42}')
result = L.execute('config.json')
assert result.values[0] == {"key": "value", "n": 42}, result.values[0]
ok("AC3: valid dict file executes and returns correct JSON_OBJECT")

# AC4
with open(f1, 'w') as fh: fh.write('[1, 2, 3]')
try:
    L.execute('config.json')
    fail("AC4", "no ValueError raised for array top-level")
except ValueError as e:
    assert 'dict' in str(e).lower() or 'object' in str(e).lower(), str(e)
    ok("AC4: non-dict raises clear ValueError")

# AC5
with open(f1, 'w') as fh: fh.write('{bad json}')
try:
    L.execute('config.json')
    fail("AC5", "no ValueError raised for malformed JSON")
except ValueError as e:
    assert 'malformed' in str(e).lower() or 'json' in str(e).lower(), str(e)
    ok("AC5: malformed JSON raises clear ValueError with parse info")

# AC6
try:
    L.execute('../../etc/passwd')
    fail("AC6", "path traversal not rejected")
except ValueError:
    ok("AC6: path traversal rejected")

# AC7/8
with open(f1, 'w') as fh: fh.write('{"x": 1}')
fp1 = L.fingerprint_inputs('config.json')
fp2 = L.fingerprint_inputs('config.json')
assert fp1 == fp2, f"same file, different fingerprint: {fp1!r} vs {fp2!r}"
time.sleep(0.05)
with open(f1, 'w') as fh: fh.write('{"x": 2}')
fp3 = L.fingerprint_inputs('config.json')
assert fp3 != fp1, f"mtime unchanged after write: {fp1!r} vs {fp3!r}"
ok("AC7/8: fingerprint_inputs uses mtime — cache hit on unchanged, miss on modified")

# AC9
with open(os.path.join(repo, '__init__.py')) as fh:
    init_src = fh.read()
assert 'LoadJsonNode' in init_src
ok("AC9: LoadJsonNode registered in __init__.py")

# REWORK: Empty-filename guard
try:
    L.execute('')
    fail("REWORK-empty-filename", "no ValueError raised for empty filename")
except ValueError as e:
    assert 'no file selected' in str(e).lower(), str(e)
    ok("REWORK-empty-filename: empty string raises clear ValueError")

# REWORK: File-size cap
import nodes as nd_mod
old_max = nd_mod._MAX_JSON_FILE_SIZE
try:
    nd_mod._MAX_JSON_FILE_SIZE = 10  # 10 bytes
    with open(f1, 'w') as fh:
        fh.write('{"key": "a very long value that exceeds 10 bytes"}')
    try:
        L.execute('config.json')
        fail("REWORK-file-size-cap", "no ValueError raised for oversized file")
    except ValueError as e:
        assert 'exceeds' in str(e).lower() or 'limit' in str(e).lower(), str(e)
        ok("REWORK-file-size-cap: oversized file raises clear ValueError")
finally:
    nd_mod._MAX_JSON_FILE_SIZE = old_max

# REWORK: _guard_input_path helper
from nodes import _guard_input_path
try:
    _guard_input_path('')
    fail("REWORK-guard-empty", "no ValueError for empty filename")
except ValueError:
    ok("REWORK-guard-empty: _guard_input_path rejects empty filename")

try:
    _guard_input_path('../../etc/passwd')
    fail("REWORK-guard-traversal", "no ValueError for path traversal")
except ValueError:
    ok("REWORK-guard-traversal: _guard_input_path rejects traversal")

with open(f1, 'w') as fh: fh.write('{"x": 1}')
result = _guard_input_path('config.json')
assert os.path.isabs(result), f"expected absolute path, got: {result}"
ok("REWORK-guard-valid: _guard_input_path returns resolved path for valid file")

# REWORK: fingerprint_inputs returns "" for empty filename
fp_empty = L.fingerprint_inputs('')
assert fp_empty == '', repr(fp_empty)
ok("REWORK-fingerprint-empty: fingerprint_inputs('') returns '' without raising")

print(f"\nResult: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
