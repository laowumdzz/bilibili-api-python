# -*- coding: utf-8 -*-
import json, glob, os, re

usage = json.load(open('usage_dump.json'))
paths_all = json.load(open('api_paths_dump.json'))
jsonroot = {os.path.basename(f)[:-5]: json.load(open(f,encoding='utf8')) for f in glob.glob('bilibili_api/data/api/*.json')}

# resolve var->file from module-level assignments again (get var file)
var_file = {}
for pf in glob.glob('bilibili_api/*.py'):
    mod = os.path.basename(pf)[:-3]
    if mod=='__init__': continue
    src = open(pf,encoding='utf8').read()
    for m in re.finditer(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*get_api\(\s*"([^"]+)"\s*\)', src):
        var_file[(mod,m.group(1))]=m.group(2)
# include utils modules for get_api direct use only
for pf in glob.glob('bilibili_api/utils/*.py'):
    mod = os.path.basename(pf)[:-3]
    if mod=='__init__': continue
    src = open(pf,encoding='utf8').read()
    for m in re.finditer(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*get_api\(\s*"([^"]+)"\s*\)', src):
        var_file[(mod,m.group(1))]=m.group(2)

print("== dangling references (code indexes key missing in JSON) ==")
dangling=[]
for mod, rows in usage.items():
    for ln, v, keys in rows:
        if len(keys)<1: continue
        if v.startswith('get_api:'):
            base = v[8:]
        else:
            base = var_file.get((mod,v))
            if base is None:
                continue
        tree = jsonroot.get(base)
        if tree is None: continue
        node=tree; miss=None
        for i,k in enumerate(keys):
            if not isinstance(node,dict) or k not in node:
                miss=(i,k); break
            node=node[k]
        if miss:
            dangling.append((mod,ln,base,keys,miss))
            print(f"  {mod}.py L{ln}: {base}.json {keys} -> '{miss[1]}' NOT FOUND at depth {miss[0]}")
print("dangling count:", len(dangling))

# == zombies: json api path never referenced ==
# coverage: for each json file, set of (sub-path up to entry length) referenced
print("\n== JSON entries with NO code reference (zombie candidates) ==")
covered = {}  # base -> set of key-tuples referenced at any length
for mod, rows in usage.items():
    for ln, v, keys in rows:
        if len(keys)<1: continue
        if v.startswith('get_api:'):
            base=v[8:]
        else:
            base = var_file.get((mod,v))
            if base is None: continue
        covered.setdefault(base,set())
        for i in range(1,len(keys)+1):
            covered[base].add(tuple(keys[:i]))
zcount=0
for base, paths in sorted(paths_all.items()):
    cs = covered.get(base,set())
    for p in paths:
        # entry considered referenced if its full path or its leaf-with-prefix-chain matched
        ref = any((p==c) or (len(c)==len(p) and c[-1]==p[-1] and c[:-1]==p[:-1]) for c in cs)
        if not ref:
            # soften: entry whose LEAF key alone appears anywhere (any file any depth) counts as maybe-referenced
            leaf_anywhere = any(p[-1]==c[-1] for c in cs)
            zcount+=1
            print(f"  {base}.json :: {'.'.join(p)}")
print("zombie candidate count:", zcount)
