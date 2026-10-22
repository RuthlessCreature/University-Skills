"""Replay prepared teaching content through actual local tools, without a model API."""
from pathlib import Path
import argparse,json,sys,datetime
from local_skill_runner import LocalTools,runtime_identity,sha

def run(output,render=False):
    root=Path(__file__).resolve().parents[2]
    cases=root/'University-Agent/training/p2-20261022/examples'
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    events=[];results=[]
    def invoke(local,name,args):
        try:result=local.invoke(name,args)
        except Exception as error:
            events.append({'event':'tool_failed','name':name,'arguments':args,'error':str(error)})
            raise
        events.append({'event':'tool_completed','name':name,'arguments':args,'result':result})
        return result
    try:
        for route,folder in [('grant','01-complete-teaching'),('paper','01-public-data'),('patent','01-simulated-device')]:
            case=cases/route/folder;task=json.loads((case/'task.json').read_text('utf-8'))
            materials={'profile':case/'export-profile.json','prepared-content':case/'export-content.json'}
            if route!='paper':materials['template']=(case/task['runner_materials']['template']).resolve()
            local=LocalTools(materials,output/route)
            content=json.loads(invoke(local,'read_material',{'alias':'prepared-content'})['text'])
            invoke(local,'read_material',{'alias':'profile'})
            if route!='paper':invoke(local,'inspect_template',{'alias':'template'})
            if route=='grant':
                fragments={}
                for node,contract in task['node_contracts'].items():
                    if not contract.get('required_slots'):continue
                    part={'material_type':content.get('material_type','teaching-simulation'),'slots':{slot:content['slots'][slot] for slot in contract['required_slots']},'source_notes':content.get('source_notes',[]),'unresolved_questions':content.get('unresolved_questions',[])}
                    result=invoke(local,'save_draft',{'name':node+'-section.json','text':json.dumps(part,ensure_ascii=False,indent=2)})
                    fragments['section/'+node]=Path(result['path'])
                # New instance reopens actual fragment files; no chat memory is used.
                local=LocalTools({**materials,**fragments},output/route)
                invoke(local,'assemble_word_content',{'name':'word-content.json','profile_alias':'profile','section_aliases':list(fragments)})
            else:invoke(local,'save_draft',{'name':'word-content.json','text':json.dumps(content,ensure_ascii=False,indent=2)})
            word=invoke(local,'export_word',{'name':route+'-local-draft.docx','profile_alias':'profile','content_name':'word-content.json'})
            item={'route':route,'word':word,'content_origin':'Prepared teaching draft, not new model prose'}
            if render:item['rendered']=invoke(local,'render_word',{'name':route+'-local-draft.docx'})
            results.append(item)
        figure=LocalTools({'data':cases/'figure/01-public-data/input/penguins.csv'},output/'figure')
        drawn=invoke(figure,'plot_csv',{'prefix':'adelie','alias':'data','filter_column':'species','filter_value':'Adelie','group_column':'sex','numeric_column':'flipper_length_mm','unit':'mm','title':'Adelie flipper length by sex'})
        results.append({'route':'figure','figure':drawn})
        status='LOCAL_FILE_REPLAY_COMPLETE_REVIEW_REQUIRED'
    except Exception as error:
        status='LOCAL_FILE_REPLAY_FAILED';events.append({'event':'replay_failed','error_type':type(error).__name__,'error':str(error)})
        raise
    finally:
        report={'status':locals().get('status','LOCAL_FILE_REPLAY_FAILED'),'actual_time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runner_hashes':runtime_identity(),'entrypoint_sha256':sha(Path(__file__)),'provider_api_called':False,'content_generation_by_model':False,'scientific_review':'NOT_PERFORMED','render_requested':render,'results':results,'events':events}
        (output/'RUN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);parser.add_argument('--render',action='store_true');args=parser.parse_args()
    result=run(args.output,args.render);print(json.dumps({'status':result['status'],'routes':len(result['results']),'provider_api_called':False,'output':str(Path(args.output).resolve())},ensure_ascii=False))

if __name__=='__main__':main()
