"""Install canonical Skills into this package only; never changes global Codex files."""
from pathlib import Path
import json,shutil,hashlib

def main():
    source=Path(__file__).resolve().parents[1];root=source.parent;target=root/'.agents/skills'
    manifest=json.loads((source/'skills-manifest.json').read_text('utf-8'));checked=0
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    for skill in manifest['skills']:
        original=(source/skill['path']).parent;destination=target/skill['id']
        if destination.exists():
            expected={p.relative_to(original).as_posix():sha(p) for p in original.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
            actual={p.relative_to(destination).as_posix():sha(p) for p in destination.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
            if actual!=expected:raise ValueError('Installed Skill differs; preserve it and choose a fresh package directory: '+skill['id'])
        else:shutil.copytree(original,destination,ignore=shutil.ignore_patterns('__pycache__'))
        checked+=1
    print(json.dumps({'installed_skills':checked,'target':str(target),'global_configuration_changed':False,'byte_identical':True},ensure_ascii=False))

if __name__=='__main__':main()
