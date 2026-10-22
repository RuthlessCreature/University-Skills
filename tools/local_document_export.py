"""Registered-template Word draft export and explicit render evidence.

Content preparation, file generation, rendering and scientific review are separate.
"""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from copy import deepcopy
import hashlib,json,os,re,subprocess,sys

sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def filename(name,suffix=None):
    if not isinstance(name,str) or not name or Path(name).name!=name or '/' in name or '\\' in name or ':' in name:raise ValueError('Use one output filename without directory components')
    if suffix and Path(name).suffix.lower()!=suffix:raise ValueError('Unexpected output file type')
    return name

def text_list(value,label,allow_empty=False):
    if not isinstance(value,list) or (not value and not allow_empty) or len(value)>80 or any(not isinstance(t,str) or not t.strip() or len(t)>12000 for t in value):raise ValueError('Invalid paragraph list: '+label)
    return value

def inspect_reference(path):
    from lxml import etree as E
    with ZipFile(path) as z:root=E.fromstring(z.read('word/document.xml'))
    ns={'w':W};paras=root.findall('w:body/w:p',ns)
    return {'sha256':sha(path),'paragraphs':[{'index':i,'xml_sha256':hashlib.sha256(E.tostring(p)).hexdigest(),'text':''.join(p.xpath('.//w:t/text()',namespaces=ns))} for i,p in enumerate(paras)],'scope':'Body paragraph inventory; template profile controls allowed insertions and instruction removal.'}

def new_paragraph(text,anchor):
    from lxml import etree as E
    p=E.Element('{'+W+'}p');original=anchor.find('{'+W+'}pPr')
    props=deepcopy(original) if original is not None else E.Element('{'+W+'}pPr')
    for key in ['pageBreakBefore','keepNext','keepLines','rPr','snapToGrid','spacing','jc','numPr']:
        for node in props.findall('{'+W+'}'+key):props.remove(node)
    E.SubElement(props,'{'+W+'}snapToGrid').set('{'+W+'}val','0')
    space=E.SubElement(props,'{'+W+'}spacing');space.set('{'+W+'}line','360');space.set('{'+W+'}lineRule','auto');space.set('{'+W+'}after','100');p.append(props)
    run=E.SubElement(p,'{'+W+'}r');rp=E.SubElement(run,'{'+W+'}rPr');fonts=E.SubElement(rp,'{'+W+'}rFonts')
    for key,value in [('ascii','Times New Roman'),('hAnsi','Times New Roman'),('eastAsia','宋体')]:fonts.set('{'+W+'}'+key,value)
    E.SubElement(rp,'{'+W+'}color').set('{'+W+'}val','000000');E.SubElement(rp,'{'+W+'}sz').set('{'+W+'}val','28')
    node=E.SubElement(run,'{'+W+'}t');node.text=text;node.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    return p

def export_template(reference,profile,payload,target):
    from lxml import etree as E
    if sha(reference)!=profile.get('reference_sha256'):raise ValueError('Template version does not match the registered export profile')
    slots=profile.get('slots');values=payload.get('slots')
    if not isinstance(slots,list) or not slots or not isinstance(values,dict):raise ValueError('A registered slot map and slot values are required')
    keys={slot['id'] for slot in slots}
    if set(values)-keys:raise ValueError('Unknown template slot: '+', '.join(sorted(set(values)-keys)))
    for slot in slots:
        if slot.get('required',True) and slot['id'] not in values:raise ValueError('Missing required template slot: '+slot['id'])
        if slot['id'] in values:text_list(values[slot['id']],slot['id'])
    with ZipFile(reference) as z:
        root=E.fromstring(z.read('word/document.xml'));ns={'w':W};paras=root.findall('w:body/w:p',ns)
        for slot in slots:
            index=slot['paragraph_index']
            if not isinstance(index,int) or not 0<=index<len(paras):raise ValueError('Profile paragraph index is invalid')
            if hashlib.sha256(E.tostring(paras[index])).hexdigest()!=slot['anchor_xml_sha256']:raise ValueError('Template anchor does not match the registered slot')
        removed=profile.get('remove_guidance_indices',[])
        protected=profile.get('protected_paragraph_indices',[])
        if set(removed)&set(protected) or any(not isinstance(i,int) or not 0<=i<len(paras) for i in removed):raise ValueError('Profile attempts to remove protected or invalid paragraphs')
        for slot in sorted(slots,key=lambda s:s['paragraph_index'],reverse=True):
            cursor=paras[slot['paragraph_index']]
            for text in values.get(slot['id'],[]):
                node=new_paragraph(text,cursor);cursor.addnext(node);cursor=node
        for i in removed:paras[i].getparent().remove(paras[i])
        body=root.find('w:body',ns);end=body.find('w:sectPr',ns)
        notes=payload.get('source_notes',[])+['待核实：'+q for q in payload.get('unresolved_questions',[])]
        if notes:
            anchor=paras[-1]
            for text in ['来源与待核实事项']+notes:
                p=new_paragraph(text,anchor)
                for size in p.findall('.//w:sz',ns):size.set('{'+W+'}val','22')
                spacing=p.find('w:pPr/w:spacing',ns);spacing.set('{'+W+'}line','276');spacing.set('{'+W+'}after','40')
                if end is not None:end.addprevious(p)
                else:body.append(p)
        # Preserve source formatting; pagination flags prevent split instructions.
        for i,p in enumerate(paras):
            if i in removed or not ''.join(p.itertext()).strip():continue
            props=p.find('{'+W+'}pPr')
            if props is None:props=E.Element('{'+W+'}pPr');p.insert(0,props)
            if props.find('{'+W+'}keepLines') is None:E.SubElement(props,'{'+W+'}keepLines')
            if re.match(r'^\s*(?:（[一二三四]）|[1-8][、．])',''.join(p.itertext())) and props.find('{'+W+'}keepNext') is None:E.SubElement(props,'{'+W+'}keepNext')
        with target.open('xb') as stream:
            with ZipFile(stream,'w',ZIP_DEFLATED) as out:
                for item in z.infolist():out.writestr(item,E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True) if item.filename=='word/document.xml' else z.read(item.filename))
    with ZipFile(reference) as a,ZipFile(target) as b:
        preserved=[n for n in a.namelist() if n!='word/document.xml' and a.read(n)==b.read(n)]
        if len(preserved)!=len(a.namelist())-1:raise ValueError('A preserve-only Word package part changed')
    return {'reference_sha256':sha(reference),'preserved_package_parts':len(preserved),'filled_slots':list(values),'removed_guidance_indices':removed,'pagination_changes':['keepLines','keepNext']}

def export_course_document(payload,target):
    from docx import Document
    from docx.shared import Cm,Pt,RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    title=payload.get('title');sections=payload.get('sections')
    if not isinstance(title,str) or not title.strip() or not isinstance(sections,list) or not sections:raise ValueError('Course Word export requires a title and sections')
    for section in sections:
        if not isinstance(section.get('heading'),str) or not section['heading'].strip():raise ValueError('Each section requires a heading')
        text_list(section.get('paragraphs'),section['heading'])
    doc=Document();sec=doc.sections[0];sec.page_width=Cm(21);sec.page_height=Cm(29.7);sec.top_margin=sec.bottom_margin=Cm(2);sec.left_margin=sec.right_margin=Cm(2.3)
    for name,size in [('Normal',11),('Title',20),('Heading 1',14)]:
        style=doc.styles[name];style.font.name='Times New Roman';style.font.size=Pt(size);style.font.color.rgb=RGBColor(0,0,0)
        props=style._element.get_or_add_rPr();fonts=props.rFonts;fonts.set(qn('w:eastAsia'),'宋体')
        for key in ['asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme','csTheme']:fonts.attrib.pop(qn('w:'+key),None)
        for border in style._element.findall('.//'+qn('w:pBdr')):border.getparent().remove(border)
    doc.styles['Normal'].paragraph_format.line_spacing=1.25;doc.styles['Normal'].paragraph_format.space_after=Pt(6)
    doc.add_paragraph(title,style='Title')
    doc.add_paragraph('课程工作稿。资料和模型输出仍需核对；文件生成不代表科学审核、署名确认或正式提交。')
    for section in sections:
        doc.add_heading(section['heading'],level=1)
        for text in section['paragraphs']:doc.add_paragraph(text)
    for heading,key in [('来源记录','source_notes'),('待核实事项','unresolved_questions')]:
        if payload.get(key):
            doc.add_heading(heading,level=1)
            for text in payload[key]:doc.add_paragraph(text)
    for table in payload.get('tables',[]):
        columns=text_list(table.get('columns'),'table columns');rows=table.get('rows')
        if not isinstance(rows,list) or any(not isinstance(row,list) or len(row)!=len(columns) or any(not isinstance(cell,(str,int,float)) for cell in row) for row in rows):raise ValueError('Table rows must match the declared columns')
        if table.get('title'):doc.add_paragraph(str(table['title']))
        t=doc.add_table(rows=1,cols=len(columns));t.style='Table Grid'
        t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
        for i,value in enumerate(columns):t.rows[0].cells[i].text=value
        for row in rows:
            cells=t.add_row().cells
            for i,value in enumerate(row):cells[i].text=str(value)
    for p in list(doc.paragraphs)+[p for t in doc.tables for row in t.rows for cell in row.cells for p in cell.paragraphs]:
        for run in p.runs:
            props=run._element.get_or_add_rPr();fonts=props.rFonts
            if fonts is None:fonts=OxmlElement('w:rFonts');props.insert(0,fonts)
            for key,value in [('ascii','Times New Roman'),('hAnsi','Times New Roman'),('eastAsia','宋体')]:fonts.set(qn('w:'+key),value)
            for key in ['asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme','csTheme']:fonts.attrib.pop(qn('w:'+key),None)
    with target.open('xb') as stream:doc.save(stream)
    return {'template_status':'COURSE_WORKING_DOCUMENT_NOT_OFFICIAL_JOURNAL_WORD_TEMPLATE','section_count':len(sections),'native_table_count':len(doc.tables)}

def export_word(local,name,profile_alias,content_name):
    filename(name,'.docx');filename(content_name,'.json')
    profile_record=local.read(profile_alias);profile=json.loads(profile_record['text'])
    content=local.output/content_name;payload=json.loads(content.read_text('utf-8'))
    if len(content.read_bytes())>200000:raise ValueError('Export content exceeds the node size limit')
    target=local.output/name
    if target.exists() or (local.output/(name+'.export.json')).exists():raise FileExistsError('Word output or export log already exists; use a new version filename')
    mode=profile.get('mode')
    allowed={'material_type','source_notes','unresolved_questions'}|({'slots'} if mode=='ooxml-slots' else {'title','sections','tables'})
    if not isinstance(payload,dict) or set(payload)-allowed:raise ValueError('Unknown Word payload fields; do not silently drop content')
    for key in ['source_notes','unresolved_questions']:text_list(payload.get(key,[]),key,allow_empty=True)
    if mode=='ooxml-slots':
        alias=profile['reference_alias'];local.read(alias)
        detail=export_template(local.materials[alias],profile,payload,target)
    elif mode=='course-document':detail=export_course_document(payload,target)
    else:raise ValueError('Unknown registered export profile')
    record={'path':str(target),'sha256':sha(target),'profile_sha256':profile_record['sha256'],'content_sha256':sha(content),'detail':detail,'status':'WORD_DRAFT_WRITTEN_RENDER_REQUIRED','scientific_review':'NOT_PERFORMED','external_submission':False}
    with (local.output/(name+'.export.json')).open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
    return record

def assemble_word_content(local,name,profile_alias,section_aliases):
    filename(name,'.json')
    profile=json.loads(local.read(profile_alias)['text'])
    if not isinstance(section_aliases,list) or not section_aliases or len(section_aliases)>40:raise ValueError('Provide the actual section artifact aliases to merge')
    mode=profile.get('mode');merged={'slots':{}} if mode=='ooxml-slots' else {'sections':[],'tables':[]}
    merged.update(material_type='AI-assisted-draft',source_notes=[],unresolved_questions=[])
    inputs=[]
    for alias in section_aliases:
        source=local.read(alias);part=json.loads(source['text']);inputs.append({'alias':alias,'sha256':source['sha256']})
        allowed={'material_type','source_notes','unresolved_questions'}|({'slots'} if mode=='ooxml-slots' else {'title','sections','tables'})
        if not isinstance(part,dict) or set(part)-allowed:raise ValueError('A section artifact contains unknown fields')
        if mode=='ooxml-slots':
            if not isinstance(part.get('slots'),dict):raise ValueError('Template section artifact requires slots')
            for key,value in part['slots'].items():
                if key in merged['slots']:raise ValueError('Two selected artifacts define the same slot; select the intended version explicitly: '+key)
                text_list(value,key);merged['slots'][key]=value
        else:
            if part.get('title'):
                if merged.get('title') and merged['title']!=part['title']:raise ValueError('Selected section titles disagree')
                merged['title']=part['title']
            for key in ['sections','tables']:
                if not isinstance(part.get(key,[]),list):raise ValueError('Sections and tables must be lists')
                merged[key].extend(part.get(key,[]))
        if part.get('material_type'):
            if merged['material_type']!='AI-assisted-draft' and merged['material_type']!=part['material_type']:raise ValueError('Material types disagree across selected sections')
            merged['material_type']=part['material_type']
        for key in ['source_notes','unresolved_questions']:
            for text in text_list(part.get(key,[]),key,allow_empty=True):
                if text not in merged[key]:merged[key].append(text)
    if mode=='ooxml-slots':
        missing=[slot['id'] for slot in profile['slots'] if slot.get('required',True) and slot['id'] not in merged['slots']]
        if missing:raise ValueError('Sections are missing required slots: '+', '.join(missing))
    result=local.save(name,json.dumps(merged,ensure_ascii=False,indent=2));result['assembled_from']=inputs
    return result

def render_word(local,name):
    filename(name,'.docx');source=local.output/name
    if not source.is_file() or not (local.output/(name+'.export.json')).is_file():raise ValueError('Render only a Word file created by this exporter in the current output directory')
    expected=json.loads((local.output/(name+'.export.json')).read_text('utf-8'))['sha256']
    if sha(source)!=expected:raise ValueError('Word file changed after export')
    override=os.environ.get('COURSE_DOCX_RENDERER')
    available=sorted((Path.home()/'.codex/plugins/cache/openai-primary-runtime/documents').glob('*/skills/documents/render_docx.py'))
    renderer=Path(override) if override else available[-1] if available else None
    if renderer is None or not renderer.is_file():raise ValueError('No prepared DOCX renderer; configure COURSE_DOCX_RENDERER locally')
    out=local.output/('render-'+source.stem)
    if out.exists():raise FileExistsError('Render directory already exists; preserve the previous evidence')
    base=Path(sys.executable).parent.parent;env=dict(os.environ)
    candidates=[Path('C:/Program Files/LibreOffice/program'),base/'native/poppler/Library/bin',Path(sys.executable).parent]
    env['PATH']=os.pathsep.join(str(x) for x in candidates if x.exists())+os.pathsep+env.get('PATH','')
    command=[sys.executable,'-X','utf8',str(renderer),str(source),'--output_dir',str(out),'--emit_pdf']
    try:
        result=subprocess.run(command,capture_output=True,env=env,timeout=240)
        record={'command':command,'exit_code':result.returncode,'stdout':result.stdout.decode('utf-8','replace'),'stderr':result.stderr.decode('utf-8','replace')}
    except subprocess.TimeoutExpired:record={'command':command,'status':'TIMEOUT'}
    log=local.output/(name+'.render.json')
    with log.open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
    pdfs=list(out.glob('*.pdf'));pngs=sorted(out.glob('page-*.png'))
    if record.get('exit_code')!=0 or len(pdfs)!=1 or not pngs:raise ValueError('Word rendering failed; keep the render log and partial output')
    from pypdf import PdfReader
    count=len(PdfReader(pdfs[0]).pages)
    if len(pngs)!=count:raise ValueError('Rendered PDF page count and PNG count differ')
    manifest={'kind':'RENDERED_WORD','files':[{'path':str(p.relative_to(local.output)),'sha256':sha(p)} for p in [pdfs[0],*pngs]],'word_sha256':sha(source),'review_status':'VISUAL_AND_SCIENTIFIC_REVIEW_PENDING'}
    with (local.output/(name+'.render-manifest.json')).open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
    return {'word_sha256':sha(source),'pdf':str(pdfs[0]),'pdf_sha256':sha(pdfs[0]),'pages':count,'page_images':[str(p) for p in pngs],'log':str(log),'status':'RENDERED_PENDING_VISUAL_AND_SCIENTIFIC_REVIEW'}
