"""Local, bounded tool loop sharing the canonical University-Skills files.

The runner produces reviewable drafts, not scientific approval or submission.
"""
from pathlib import Path
import argparse,csv,hashlib,json,secrets,sys,datetime,math,copy
from provider_adapter import ProviderConfig,ChatCompletionsAdapter,ProviderError

SOURCE=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)

def runtime_identity():
    return {name:sha(SOURCE/'tools'/name) for name in ('local_skill_runner.py','provider_adapter.py','local_document_export.py','local_data_figure.py','task_preflight.py')}

def validate_resume(checkpoint,inventory,config_sha256,run_root,runner_hashes=None):
    if checkpoint['input_hashes']!=inventory:raise ProviderError('INPUTS_CHANGED','Inputs or Skills changed; start a new run and retain the old evidence.')
    if checkpoint['config_sha256']!=config_sha256:raise ProviderError('CONFIG_CHANGED','Provider configuration changed; start a new comparison run.')
    if runner_hashes is not None and checkpoint.get('runner_hashes')!=runner_hashes:raise ProviderError('RUNNER_CHANGED','Runner source changed or its version was not recorded; start a new run.')
    run_root=Path(run_root).resolve()
    for node in checkpoint['completed_nodes']:
        p=Path(node['checkpoint']).resolve()
        if not p.is_relative_to(run_root) or not p.is_file() or sha(p)!=node['sha256']:raise ProviderError('CHECKPOINT_CHANGED','A completed checkpoint is missing, moved or changed.')
        obj=json.loads(p.read_text('utf-8'))
        for artifact in obj['artifacts']:
            p2=p.parent/artifact['name']
            if not p2.resolve().is_relative_to(run_root) or not p2.is_file() or sha(p2)!=artifact['sha256']:
                raise ProviderError('ARTIFACT_CHANGED','A previously completed artifact changed; automatic continuation was refused.')
            if p2.name.endswith('.render-manifest.json'):
                for item in json.loads(p2.read_text('utf-8'))['files']:
                    rendered=(p2.parent/item['path']).resolve()
                    if not rendered.is_relative_to(run_root) or not rendered.is_file() or sha(rendered)!=item['sha256']:raise ProviderError('RENDER_CHANGED','A previously rendered PDF or page image changed.')
    return checkpoint['completed_nodes']

def schema(name,description,properties):
    return {'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}}}

TOOLS=[schema('read_material','Read one registered material by its exact alias. Returns actual text and SHA256.',{'alias':{'type':'string'}}),schema('save_draft','Save a new editable UTF-8 draft in the output folder. Never overwrites an existing file.',{'name':{'type':'string'},'text':{'type':'string'}}),schema('summarize_csv','Calculate counts and means from an actual registered CSV. Empty/NA numeric values are excluded and counted. No causal inference.',{'alias':{'type':'string'},'filter_column':{'type':'string'},'filter_value':{'type':'string'},'group_column':{'type':'string'},'numeric_column':{'type':'string'}}),schema('inspect_template','Read actual DOCX body paragraph indices, text and XML fingerprints before filling a registered template.',{'alias':{'type':'string'}}),schema('export_word','Create an editable draft using a registered export profile and a JSON payload already saved in this output directory. Never overwrites. Read the profile schema first.',{'name':{'type':'string'},'profile_alias':{'type':'string'},'content_name':{'type':'string'}}),schema('render_word','Render a Word file produced by export_word into actual PDF and page PNG files. Returns pending visual/scientific review, never approval.',{'name':{'type':'string'}})]
TOOLS.append(schema('assemble_word_content','Merge actual registered section JSON artifacts without asking the model to rewrite a long manuscript. Duplicate slots or missing required slots fail.',{'name':{'type':'string'},'profile_alias':{'type':'string'},'section_aliases':{'type':'array','items':{'type':'string'}}}))
TOOLS.append(schema('plot_csv','Calculate and draw actual registered CSV records as editable SVG and PNG with raw points and group means. No inferred confidence intervals. Unit must be supplied from the material.',{'prefix':{'type':'string'},'alias':{'type':'string'},'filter_column':{'type':'string'},'filter_value':{'type':'string'},'group_column':{'type':'string'},'numeric_column':{'type':'string'},'unit':{'type':'string'},'title':{'type':'string'}}))

class LocalTools:
    def __init__(self,materials,output):
        self.materials={k:Path(v).resolve() for k,v in materials.items()};self.output=Path(output).resolve();self.output.mkdir(parents=True,exist_ok=True)
        self.inventory={k:{'sha256':sha(v),'bytes':v.stat().st_size} for k,v in self.materials.items()}

    def register_previous(self,nodes,run_root):
        root=Path(run_root).resolve();aliases=[]
        for node in nodes:
            checkpoint=Path(node['checkpoint']).resolve()
            if not checkpoint.is_relative_to(root) or sha(checkpoint)!=node['sha256']:raise ValueError('Cannot register an unverified prior checkpoint')
            for artifact in json.loads(checkpoint.read_text('utf-8'))['artifacts']:
                name=artifact['name'];p=(checkpoint.parent/name).resolve()
                if not p.is_relative_to(root) or not p.is_file() or sha(p)!=artifact['sha256']:raise ValueError('Prior artifact changed before registration')
                alias='previous/'+node['node']+'/'+name
                if alias in self.materials and self.materials[alias]!=p:raise ValueError('Prior artifact alias collision')
                self.materials[alias]=p;self.inventory[alias]={'sha256':sha(p),'bytes':p.stat().st_size};aliases.append(alias)
        return aliases

    def read(self,alias):
        if alias not in self.materials:raise ValueError('Unregistered material alias')
        p=self.materials[alias]
        if sha(p)!=self.inventory[alias]['sha256']:raise ValueError('Input changed since the run started')
        if p.stat().st_size>250000:raise ValueError('Material exceeds node input limit; prepare a documented excerpt')
        if p.suffix.lower()=='.docx':
            from zipfile import ZipFile
            from xml.etree import ElementTree as E
            with ZipFile(p) as z:text='\n'.join(E.fromstring(z.read('word/document.xml')).itertext())
        elif p.suffix.lower() in ('.txt','.md','.json','.csv','.tex','.bib','.py','.svg','.mmd','.xml','.drawio'):text=p.read_text('utf-8-sig')
        else:raise ValueError('Unsupported binary material. Supply a verified text extraction and retain its original.')
        return {'alias':alias,'sha256':sha(p),'text':text,'verification_scope':'Actual file text only; not scientific truth verification'}

    def save(self,name,text):
        if not isinstance(name,str) or not name or Path(name).name!=name or '/' in name or '\\' in name or ':' in name or name in ('.','..'):
            raise ValueError('Use one filename without directory components')
        if Path(name).suffix not in ('.md','.json','.csv','.mmd','.txt','.tex','.bib','.svg'):raise ValueError('Unsupported output type')
        if not isinstance(text,str) or not text.strip() or len(text.encode('utf-8'))>200000:raise ValueError('Empty or oversized draft')
        if name.endswith('.json'):json.loads(text)
        p=self.output/name
        with p.open('x',encoding='utf-8') as f:f.write(text)
        return {'path':str(p),'sha256':sha(p),'status':'WRITTEN_DRAFT_REVIEW_REQUIRED'}

    def summarize(self,alias,filter_column,filter_value,group_column,numeric_column):
        self.read(alias)
        with self.materials[alias].open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f);fields=reader.fieldnames or [];rows=list(reader)
        if any(x not in fields for x in (filter_column,group_column,numeric_column)):raise ValueError('Unknown CSV column')
        chosen=[r for r in rows if r[filter_column]==filter_value];groups={};excluded=[]
        for line,r in enumerate(rows,2):
            if r[filter_column]!=filter_value:continue
            if r[group_column] in ('','NA') or r[numeric_column] in ('','NA'):excluded.append(line);continue
            value=float(r[numeric_column])
            if not math.isfinite(value):raise ValueError('Non-finite measurement')
            groups.setdefault(r[group_column],[]).append((line,value))
        return {'source_sha256':sha(self.materials[alias]),'all_rows':len(rows),'filtered_rows':len(chosen),'excluded_csv_lines':excluded,'groups':{k:{'n':len(v),'mean':math.fsum(x[1] for x in v)/len(v),'min':min(x[1] for x in v),'max':max(x[1] for x in v),'source_csv_lines':[x[0] for x in v]} for k,v in groups.items()},'scope':'Descriptive computation only'}

    def invoke(self,name,args):
        if name=='read_material':return self.read(**args)
        if name=='save_draft':return self.save(**args)
        if name=='summarize_csv':return self.summarize(**args)
        if name=='inspect_template':
            from local_document_export import inspect_reference
            self.read(args['alias']);return inspect_reference(self.materials[args['alias']])
        if name=='export_word':
            from local_document_export import export_word
            return export_word(self,**args)
        if name=='assemble_word_content':
            from local_document_export import assemble_word_content
            return assemble_word_content(self,**args)
        if name=='plot_csv':
            from local_data_figure import plot_csv
            return plot_csv(self,**args)
        if name=='render_word':
            from local_document_export import render_word
            return render_word(self,**args)
        raise ValueError('Unknown tool')

def loop(adapter,messages,local,record,limit=16):
    for turn in range(limit):
        message=adapter.complete(messages,TOOLS,record);messages.append(message)
        calls=message.get('tool_calls') or []
        if not calls:return message.get('content','')
        for call in calls:
            try:
                args=json.loads(call['function']['arguments']);name=call['function']['name']
                result=local.invoke(name,args);record({'event':'tool_completed','name':name,'arguments':args,'result':result})
            except Exception as e:
                result={'error':type(e).__name__,'detail':str(e)};record({'event':'tool_failed','name':call.get('function',{}).get('name'),'result':result})
            messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result,ensure_ascii=False)})
    raise ProviderError('TOOL_LIMIT','Tool loop exceeded the node limit; checkpoint retained.')

def validate_node_checkpoint(checkpoint,local,node_events,task,step):
    obj=json.loads(checkpoint.read_text('utf-8'))
    if obj.get('status') not in ('NEEDS_INPUT','DRAFT_READY') or any(k not in obj for k in ('artifacts','source_locators','unresolved_questions')):
        raise ProviderError('INVALID_CHECKPOINT','Node checkpoint lacks status, artifacts, source locators or unresolved questions.')
    if any(not isinstance(obj[k],list) for k in ('artifacts','source_locators','unresolved_questions')) or not obj['artifacts'] or not obj['source_locators']:
        raise ProviderError('INVALID_CHECKPOINT','Node artifacts and source locators must be nonempty lists.')
    if obj['status']=='NEEDS_INPUT' and not obj['unresolved_questions']:
        raise ProviderError('INVALID_CHECKPOINT','A missing-input checkpoint must name what is missing.')
    read_aliases={e.get('arguments',{}).get('alias','') for e in node_events if e.get('event')=='tool_completed' and e.get('name')=='read_material'}
    if not {'task','prompt'}.issubset(read_aliases) or not any(x.startswith('skill/') for x in read_aliases) or not any(x.startswith('input/') or x=='template' for x in read_aliases):
        raise ProviderError('INVALID_CHECKPOINT','Required actual material and Skill reads are missing from this node.')
    relevant=task.get('node_contracts',{}).get(step,{}).get('skill_ids',[])
    if relevant and not any('skill/'+skill in read_aliases for skill in relevant):raise ProviderError('WRONG_SKILL','Read one of the Skills assigned to the current node: '+', '.join(relevant))
    for artifact in obj['artifacts']:
        name=artifact.get('name','')
        if not name or Path(name).name!=name or '/' in name or '\\' in name:raise ProviderError('INVALID_CHECKPOINT','Artifact must use an output filename.')
        f=local.output/name
        if f==checkpoint or not f.is_file() or sha(f)!=artifact.get('sha256'):raise ProviderError('INVALID_CHECKPOINT','Artifact is missing or its SHA256 does not match actual bytes.')
    for citation in obj['source_locators']:
        alias=citation.get('alias');excerpt=citation.get('excerpt')
        if alias not in read_aliases or not citation.get('locator') or not isinstance(excerpt,str) or not excerpt or excerpt not in local.read(alias)['text']:
            raise ProviderError('INVALID_CHECKPOINT','Source excerpt does not match material actually read in this node.')
    if 'export' in step and task.get('word_export_required') and (obj['status']=='DRAFT_READY' or not obj.get('blocking',False)):
        completed=[e for e in node_events if e.get('event')=='tool_completed']
        exports=[e for e in completed if e.get('name')=='export_word']
        renders=[e for e in completed if e.get('name')=='render_word']
        names={a['name'] for a in obj['artifacts']}
        if not exports or not renders:raise ProviderError('MISSING_EXPORT','This node must actually export and render Word; textual claims are insufficient.')
        exported=Path(exports[-1]['result']['path']).name
        if exported not in names or exported+'.render-manifest.json' not in names:raise ProviderError('MISSING_EXPORT','List the actual Word file and its render manifest in checkpoint artifacts.')
        if renders[-1]['arguments'].get('name')!=exported or renders[-1]['result'].get('word_sha256')!=exports[-1]['result']['sha256']:raise ProviderError('MISSING_EXPORT','The render must correspond to the actual exported Word version.')
    contract=task.get('node_contracts',{}).get(step,{})
    if obj['status']=='DRAFT_READY':
        completed=[e for e in node_events if e.get('event')=='tool_completed']
        for tool in contract.get('required_tools',[]):
            if not any(e.get('name')==tool for e in completed):raise ProviderError('MISSING_REQUIRED_TOOL','Node requires actual tool execution: '+tool)
        required_slots=set(contract.get('required_slots',[]))
        if required_slots:
            fragments=[]
            for artifact in obj['artifacts']:
                if artifact['name'].endswith('.json'):
                    content=json.loads((local.output/artifact['name']).read_text('utf-8'))
                    if isinstance(content,dict) and 'slots' in content:fragments.append(content)
            if len(fragments)!=1 or set(fragments[0]['slots'])!=required_slots:raise ProviderError('INVALID_SECTION','Write exactly the slots assigned to this node, in one section JSON.')
            for value in fragments[0]['slots'].values():
                if not isinstance(value,list) or not value or any(not isinstance(v,str) or not v.strip() for v in value):raise ProviderError('INVALID_SECTION','Each slot requires a nonempty paragraph array.')
        if task.get('figure_export_required') and step=='draw':
            plots=[e for e in completed if e.get('name')=='plot_csv']
            if not plots:raise ProviderError('MISSING_FIGURE','Actual plot_csv execution is required.')
            names={a['name'] for a in obj['artifacts']}
            plotted={a['name']:a['sha256'] for a in plots[-1]['result']['files']}
            for suffix in ('.svg','.png','.statistics.json','.clean.csv','.caption.md'):
                matches=[n for n in plotted if n.endswith(suffix)]
                if len(matches)!=1 or matches[0] not in names or sha(local.output/matches[0])!=plotted[matches[0]]:raise ProviderError('MISSING_FIGURE','Checkpoint must include actual figure artifact '+suffix)
    return obj

def validate_probe_proof(local,nonce,expected_mean,events):
    proof=json.loads((local.output/'proof.json').read_text('utf-8'))
    if proof!={'read_value':nonce,'n':3,'mean':expected_mean}:raise ProviderError('PROBE_FAILED','Read/write/calculation proof did not match the actual files.')
    required={'read_material','save_draft','summarize_csv'}
    if not required.issubset({e.get('name') for e in events if e.get('event')=='tool_completed'}):raise ProviderError('PROBE_FAILED','Required actual read, calculation and write tool calls are missing.')
    return proof

def run(args):
    config=ProviderConfig.load(args.config);adapter=ChatCompletionsAdapter(config)
    runner_hashes=runtime_identity()
    out=Path(args.output).resolve()
    if args.resume:
        if args.probe:raise ProviderError('INVALID_CONFIG','Capability probes use fresh output directories.')
        if not out.is_dir() or not (out/'run.json').is_file():raise ProviderError('INVALID_CONFIG','Resume requires an existing recorded run.')
        previous_state=json.loads((out/'run.json').read_text('utf-8'))
        if previous_state.get('config_sha256')!=sha(Path(args.config)):raise ProviderError('CONFIG_CHANGED','Provider configuration changed; create a new run.')
        if previous_state.get('runner_hashes')!=runner_hashes:raise ProviderError('RUNNER_CHANGED','Runner changed since this run; preserve it and start a new version.')
        history=out/'state-history';history.mkdir(exist_ok=True)
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        dump(history/(stamp+'.json'),previous_state)
    else:out.mkdir(parents=True,exist_ok=False)
    events=[]
    def record(event):
        event={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),**event};events.append(event)
        if event.get('event')=='provider_request':
            state['provider']['network_called']=True
            state['provider']['status']='REQUEST_ATTEMPTED'
        elif event.get('event')=='provider_response':state['provider']['status']='RESPONDED_UNVERIFIED_CAPABILITIES'
        with (out/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
    state={'status':'RUNNING','provider':adapter.preflight(),'config_sha256':sha(Path(args.config)),'runner_hashes':runner_hashes,'scientific_approval':False,'cloud_deployed':False,'runner':'local-skill-runner','version':'0.2'}
    try:
        if state['provider']['status']=='NOT_CONFIGURED':raise ProviderError('NOT_CONFIGURED','No API key is configured for this adapter.')
        if args.probe:
            nonce=secrets.token_hex(12);material=out/'probe-input.txt';material.write_text(nonce,encoding='utf-8')
            first=secrets.randbelow(1000)+10
            numbers=out/'probe-data.csv';numbers.write_text(f'kind,group,value\nprobe,check,{first}\nprobe,check,{first+2}\nprobe,check,{first+4}\n','utf-8')
            local=LocalTools({'probe':material,'probe-data':numbers},out/'drafts')
            prompt='Read registered material probe using read_material. Use summarize_csv on alias probe-data with filter_column=kind, filter_value=probe, group_column=group, numeric_column=value. Save proof.json using save_draft with exactly three fields: read_value (actual probe file text), n (numeric count from group check), mean (numeric mean from group check). All three tools must actually execute. Do not guess file contents or calculations.'
            final=loop(adapter,[{'role':'user','content':prompt}],local,record,8)
            validate_probe_proof(local,nonce,first+2,events)
            state.update(status='CAPABILITY_PROBE_PASSED',final=final,scope='Actual file read, CSV calculation and write tool round trips; not four-workflow acceptance')
        else:
            from task_preflight import check_task
            preparation=check_task(args.task);dump(out/'task-preflight.json',preparation)
            if preparation['errors']:raise ProviderError('TASK_PREPARATION_REQUIRED','Task preparation failed; inspect task-preflight.json before making a model request.')
            task_path=Path(args.task).resolve();task=json.loads(task_path.read_text('utf-8'));case=task_path.parent
            materials={'task':task_path,'prompt':case/'PROMPT.md'}
            for f in (case/'input').iterdir():
                if f.is_file():materials['input/'+f.name]=f
            # Optional explicit template/excerpt aliases; only local files named in this task are exposed.
            for alias,path in task.get('runner_materials',{}).items():materials[alias]=(case/path).resolve()
            manifest=json.loads((SOURCE/'skills-manifest.json').read_text('utf-8'))
            skill_paths={x['id']:SOURCE/x['path'] for x in manifest['skills']}
            for name in task['skills']:
                materials['skill/'+name]=skill_paths[name]
                for reference in (skill_paths[name].parent/'references').glob('*.md'):
                    materials['skillref/'+name+'/'+reference.name]=reference
            materials['workflow-sop']=SOURCE/'docs/LOCAL_RESEARCH_SOP.md'
            attempt=1
            while (out/'drafts'/f'attempt-{attempt:03}').exists():attempt+=1
            local=LocalTools(materials,out/'drafts'/f'attempt-{attempt:03}')
            base_inventory=copy.deepcopy(local.inventory)
            config_sha256=sha(Path(args.config));prior=[]
            saved=out/'checkpoint.json'
            if args.resume and saved.is_file():
                prior=validate_resume(json.loads(saved.read_text('utf-8')),base_inventory,config_sha256,out,runner_hashes)
                record({'event':'resume_validated','completed_nodes':len(prior),'attempt':attempt})
            elif args.resume:
                previous=json.loads((out/'inputs.json').read_text('utf-8'))
                if previous!=base_inventory:raise ProviderError('INPUTS_CHANGED','Inputs changed before the first checkpoint; start a new run.')
                record({'event':'resume_first_node','attempt':attempt})
            else:dump(out/'inputs.json',base_inventory)
            local.register_previous(prior,out)
            for index,step in enumerate(task['steps'],1):
                if index<=len(prior):continue
                node_event_start=len(events)
                instruction={'task':task['id'],'node':step,'step_index':index,'material_aliases':list(local.materials),'prior_checkpoint_summaries':[{k:v for k,v in node.items() if k!='summary'} for node in prior],'required_output':f'{index:02}-{step}.json','checkpoint_schema':{'status':'NEEDS_INPUT or DRAFT_READY','artifacts':[{'name':'a saved filename other than this checkpoint','sha256':'actual SHA256 returned by save_draft'}],'source_locators':[{'alias':'registered material alias','locator':'page, paragraph or field','excerpt':'exact source text'}],'unresolved_questions':['specific missing input']},'rules':'Read task, prompt, at least one input or template, and a relevant Skill using read_material in this node. Read earlier node artifacts through their previous/ aliases instead of reconstructing them from memory. Only perform this node. Save a substantive node artifact first, then the required checkpoint JSON. State actual actions. No invented data, citations, approvals or claimed tool executions. Do not submit externally. Missing material is not permission to guess. Write scientific prose as natural, precise Chinese. Retain uncertainty. At export nodes, use the registered Word profile, export_word and render_word; returned render status still requires visual and scientific review.'}
                instruction['node_contract']=task.get('node_contracts',{}).get(step,{})
                final=loop(adapter,[{'role':'system','content':(SOURCE/'docs/LOCAL_RESEARCH_SOP.md').read_text('utf-8')},{'role':'user','content':json.dumps(instruction,ensure_ascii=False)}],local,record)
                checkpoint=local.output/instruction['required_output']
                for repair in range(2):
                    try:
                        obj=validate_node_checkpoint(checkpoint,local,events[node_event_start:],task,step)
                        break
                    except (ProviderError,ValueError,KeyError,TypeError,OSError) as error:
                        record({'event':'checkpoint_rejected','node':step,'checkpoint':str(checkpoint),'repair_used':bool(repair),'error':str(error)})
                        if repair:raise
                        # Keep the failed checkpoint and all output files. A repaired checkpoint uses a fresh filename.
                        checkpoint=local.output/(f'{index:02}-{step}.repair1.json')
                        correction={**instruction,'node':step,'required_output':checkpoint.name,'validation_error':str(error),'rules':'Repair only this node once. Read actual existing files as needed, retain old files, use fresh filenames for corrections. Reuse actual verified artifacts where appropriate. Do not invent tool results or hashes. Save the corrected checkpoint at required_output.','contract':task.get('node_contracts',{}).get(step,{})}
                        repair_materials={**local.materials,**{'current/'+f.name:f for f in local.output.iterdir() if f.is_file() and f.suffix in ('.json','.md','.csv','.mmd','.txt','.svg')}}
                        for alias,path in repair_materials.items():
                            if alias not in local.materials:local.materials[alias]=path;local.inventory[alias]={'sha256':sha(path),'bytes':path.stat().st_size}
                        correction['material_aliases']=list(local.materials)
                        loop(adapter,[{'role':'system','content':(SOURCE/'docs/LOCAL_RESEARCH_SOP.md').read_text('utf-8')},{'role':'user','content':json.dumps(correction,ensure_ascii=False)}],local,record)
                if obj['status']=='NEEDS_INPUT':
                    dump(out/'needs-input.json',{'node':step,'checkpoint':str(checkpoint),'questions':obj['unresolved_questions']})
                    if not task.get('continue_with_documented_gaps') or obj.get('blocking',False):state.update(status='NEEDS_INPUT',node=step);break
                prior.append({'node':step,'checkpoint':str(checkpoint),'sha256':sha(checkpoint),'summary':obj})
                dump(out/'checkpoint.json',{'completed_nodes':prior,'input_hashes':base_inventory,'config_sha256':config_sha256,'runner_hashes':runner_hashes,'next_index':index+1,'resume_support':'HASH_GUARDED_RESTART_AT_NEXT_NODE'})
                local.register_previous([prior[-1]],out)
            else:
                gaps=[{'node':n['node'],'questions':n['summary'].get('unresolved_questions',[])} for n in prior if n['summary'].get('status')=='NEEDS_INPUT' or n['summary'].get('unresolved_questions')]
                state.update(status=('DRAFT_WITH_GAPS_RENDERED_REVIEW_REQUIRED' if gaps else 'DRAFT_RENDERED_REVIEW_REQUIRED') if task.get('word_export_required') else 'MODEL_DRAFTS_READY_REVIEW_REQUIRED',gaps=gaps,scope='Actual exported/rendered files when required; visual review and scientific approval remain separate')
        return 0
    except Exception as e:
        state.update(status=getattr(e,'status','FAILED'),error=str(e));record({'event':'run_failed','status':state['status'],'error':str(e)});return 2
    finally:dump(out/'run.json',state)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--resume',action='store_true')
    group=p.add_mutually_exclusive_group(required=True);group.add_argument('--probe',action='store_true');group.add_argument('--task')
    try:return run(p.parse_args())
    except (ProviderError,OSError,ValueError) as e:
        print(json.dumps({'status':getattr(e,'status','FAILED'),'error':str(e),'network_success_claimed':False},ensure_ascii=False),file=sys.stderr)
        return 2

if __name__=='__main__':sys.exit(main())
