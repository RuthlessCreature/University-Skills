"""Read-only task and material checks. Does not use model credentials or HTTP."""
from pathlib import Path
import argparse,json,sys
from zipfile import ZipFile
from xml.etree import ElementTree as E
from local_skill_runner import SOURCE,sha,runtime_identity

TEXT_SUFFIXES={'.txt','.md','.json','.csv','.tex','.bib','.py','.svg','.mmd','.xml','.drawio','.docx'}

def check_task(path):
    path=Path(path).resolve();task=json.loads(path.read_text('utf-8'));case=path.parent
    errors=[];materials={};steps=task.get('steps',[]);contracts=task.get('node_contracts',{})
    def error(kind,detail):errors.append({'kind':kind,'detail':detail})
    if not steps or len(steps)!=len(set(steps)) or set(steps)!=set(contracts):error('TASK_SCHEMA','Steps must be nonempty, unique and correspond exactly to node_contracts.')
    manifest=json.loads((SOURCE/'skills-manifest.json').read_text('utf-8'));skills={s['id']:SOURCE/s['path'] for s in manifest['skills']}
    candidates={'task':path,'prompt':case/'PROMPT.md'}
    input_dir=case/'input'
    if not input_dir.is_dir():error('MISSING_INPUT_DIRECTORY',str(input_dir))
    else:
        for p in input_dir.iterdir():
            if p.is_file():candidates['input/'+p.name]=p
    for alias,value in task.get('runner_materials',{}).items():
        if alias in candidates or alias.startswith(('skill/','skillref/','previous/','current/')) or alias=='workflow-sop':error('ALIAS_COLLISION',alias)
        else:candidates[alias]=(case/value).resolve()
    for name in task.get('skills',[]):
        if name not in skills:error('UNKNOWN_SKILL',name)
        else:
            candidates['skill/'+name]=skills[name]
            for p in (skills[name].parent/'references').glob('*.md'):candidates['skillref/'+name+'/'+p.name]=p
    for step,c in contracts.items():
        if not c.get('goal') or not c.get('output') or not c.get('required_tools'):error('INCOMPLETE_NODE',step)
        relevant=c.get('skill_ids',[])
        if not relevant or not set(relevant).issubset(set(task.get('skills',[]))):error('NODE_SKILL_MAPPING',step)
    for alias,p in candidates.items():
        if not p.is_file():error('MISSING_FILE',alias+': '+str(p));continue
        materials[alias]={'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
        if p.suffix.lower() not in TEXT_SUFFIXES:error('UNREADABLE_TYPE',alias)
        if p.stat().st_size>250000:error('OVERSIZED_MATERIAL',alias)
        if p.suffix.lower()!='.docx':
            try:p.read_text('utf-8-sig')
            except UnicodeError:error('NON_UTF8_TEXT',alias)
        else:
            try:
                with ZipFile(p) as archive:E.fromstring(archive.read('word/document.xml'))
            except Exception as exc:error('UNREADABLE_DOCX',alias+': '+type(exc).__name__)
    if task.get('word_export_required'):
        if 'export-profile' not in candidates:error('MISSING_EXPORT_PROFILE','Word-required task has no export-profile alias.')
        elif candidates['export-profile'].is_file():
            profile=json.loads(candidates['export-profile'].read_text('utf-8'))
            if profile.get('mode')=='ooxml-slots':
                ref=candidates.get(profile.get('reference_alias'))
                if ref is None or not ref.is_file():error('MISSING_TEMPLATE','Profile reference alias has no actual file.')
                elif sha(ref)!=profile.get('reference_sha256'):error('TEMPLATE_CHANGED','Template differs from registered profile hash.')
    return {'task':task.get('id'),'status':'READY_FOR_PROVIDER_PROBE' if not errors else 'TASK_PREPARATION_REQUIRED','errors':errors,'materials':materials,'runner_hashes':runtime_identity(),'network_called':False,'semantic_or_scientific_acceptance':False,'scope':'File existence, format, size, node Skill mapping and template hash only; scientific sufficiency must be assessed in intake.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--task',required=True);parser.add_argument('--report',required=True);args=parser.parse_args()
    report=check_task(args.task);target=Path(args.report);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps({'task':report['task'],'status':report['status'],'error_count':len(report['errors']),'network_called':False},ensure_ascii=False));return 0 if not report['errors'] else 2

if __name__=='__main__':sys.exit(main())
