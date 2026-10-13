#!/usr/bin/env python3
"""Check local Markdown links/anchors in public source, excluding local caches."""
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from grea.tools.check_skill import heading_ids, without_fences


def check(root):
    errors=[];count=0;documents=0
    for directory, dirs, files in os.walk(root):
        dirs[:]=[d for d in dirs if not d.startswith('.') and d not in {'__pycache__','node_modules','Library','Temp','dist','Build','build'}]
        for name in files:
            if not name.endswith('.md'):continue
            p=Path(directory)/name;documents+=1
            for raw in re.findall(r'\]\((<[^>]+>|[^\s)]+)\)',without_fences(p.read_text())):
                target=raw.strip('<>');url=urlsplit(target)
                if url.scheme or url.netloc:continue
                path=(p.parent/unquote(url.path)).resolve() if url.path else p.resolve();count+=1
                item={'file':str(p.relative_to(root)),'target':target}
                if root not in path.parents and path!=root:errors.append(dict(item,code='outside_source'))
                elif not path.exists():errors.append(dict(item,code='missing_target'))
                elif url.fragment and path.is_file() and path.suffix=='.md' and unquote(url.fragment) not in heading_ids(path.read_text()):errors.append(dict(item,code='missing_anchor'))
    return {'ok':not errors,'documents':documents,'localLinks':count,'errors':errors,'scope':'Local links/anchors only; external URLs not fetched.'}


if __name__=='__main__':
    result=check(ROOT);print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['ok'] else 1)
