# -*- coding: utf-8 -*-
import json, glob, os, re

usage = json.load(open('usage_dump.json'))
paths_all = json.load(open('api_paths_dump.json'))

# module name for each json file
def modname(base): return base.replace('-','_')

# 1) zombie JSON entries: a path (group,...,key) in file F never referenced in module modname(F)
#    We compare the leaf key (last component) usage within the module, but also whole-file to be safe.
print("== A. JSON entries never referenced (candidates) ==")
for base, paths in sorted(paths_all.items()):
    mod = modname(base)
    modsrc = ""
    for cand in ([mod, mod+'_video', mod+'_audio', mod+'_rank', mod+'_user', mod+'_article']):
        p = f'bilibili_api/{cand}.py'
        if os.path.exists(p):
            modsrc += open(p, encoding='utf8').read()
    if not modsrc:
        print(f"[NO MODULE] {base}")  # e.g. json has no python module (like live-area? hot? etc)
        continue
    for path in paths:
        leaf = path[-1]
        # check leaf key present anywhere in matching modules
        if f'"{leaf}"' not in modsrc and f"'{leaf}'" not in modsrc:
            print(f"  {base}:{'.'.join(path)}   (leaf '{leaf}' never a literal in code)")

print()
print("== B. dangling / suspicious structure check (json group keys never referenced as first index) ==")
# for each file & module, find usage with first key not in json root keys OR second key not under it
jsonroot = {os.path.basename(f)[:-5]: json.load(open(f,encoding='utf8')) for f in glob.glob('bilibili_api/data/api/*.json')}
for mod, rows in usage.items():
    for ln, v, keys in rows:
        if len(keys) < 1: continue
        if v.startswith('get_api:'):
            base = v[len('get_api:'):]
        else:
            # find file from module mapping
            files = [b for b in jsonroot if modname(b)==mod]
            # api var may map to different file; search var-file map? approximate: try each file whose key present
            files = [b for b in jsonroot if keys[0] in jsonroot[b]]
            if not files: 
                print(f"  {mod}.py L{ln}: {v}{keys} -> key '{keys[0]}' not top-level in any JSON")
                continue
            base = files[0]
        tree = jsonroot[base]
        node = tree
        ok = True
        for i,k in enumerate(keys):
            if not isinstance(node, dict) or k not in node:
                print(f"  {mod}.py L{ln}: {base}.json {list(keys)} -> '{k}' NOT FOUND at depth {i} (path {'/'.join(keys[:i])})")
                ok = False; break
            node = node[k]
        if ok and len(keys)>=2:
            # deeper than entry level?
            pass
