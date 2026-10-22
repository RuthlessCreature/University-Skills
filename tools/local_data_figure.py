"""Reproducible raw-point/mean plot from an actual registered CSV."""
from pathlib import Path
import csv,json,math,random,subprocess,sys
from local_document_export import filename,sha

def plot_csv(local,prefix,alias,filter_column,filter_value,group_column,numeric_column,unit,title):
    filename(prefix)
    if Path(prefix).suffix or not isinstance(unit,str) or not unit.strip() or len(unit)>20:raise ValueError('Use a plain file prefix and an explicit measurement unit')
    if not isinstance(title,str) or not title.strip() or len(title)>70:raise ValueError('Provide a specific figure title of at most 70 characters')
    paths={ext:local.output/(prefix+ext) for ext in ['.svg','.png','.statistics.json','.clean.csv','.caption.md','.render.json']}
    if any(p.exists() for p in paths.values()):raise FileExistsError('Figure output already exists; use a new version prefix')
    result=local.summarize(alias,filter_column,filter_value,group_column,numeric_column)
    if not 1<=len(result['groups'])<=4:raise ValueError('This figure tool supports one to four nonempty groups; choose another layout for more groups')
    local.read(alias)
    with local.materials[alias].open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    groups={g:[(line,float(rows[line-2][numeric_column])) for line in values['source_csv_lines']] for g,values in sorted(result['groups'].items())}
    from reportlab.graphics.shapes import Drawing,Rect,Line,String,Circle
    from reportlab.graphics import renderSVG
    from reportlab.lib.colors import HexColor
    values=[value for group in groups.values() for _,value in group]
    low=math.floor(min(values)/5)*5;high=math.ceil(max(values)/5)*5
    if high==low:low-=1;high+=1
    y=lambda value:100+(value-low)/(high-low)*265
    d=Drawing(760,480);d.add(Rect(0,0,760,480,fillColor=HexColor('#ffffff'),strokeColor=None));ink=HexColor('#172f43')
    # Two title lines remain inside the canvas for Chinese and Latin labels.
    chunks=[];line='';weight=0
    for char in title:
        width=2 if ord(char)>127 else 1
        if weight+width>65:chunks.append(line);line='';weight=0
        line+=char;weight+=width
    if line:chunks.append(line)
    for i,text in enumerate(chunks):d.add(String(74,450-i*24,text,fontName='Helvetica-Bold',fontSize=18,fillColor=ink))
    d.add(String(74,396,'Points: actual observations | black line: mean | no error bars',fontSize=10,fillColor=ink))
    for i in range(6):
        tick=low+(high-low)*i/5;pos=y(tick)
        d.add(Line(80,pos,710,pos,strokeColor=HexColor('#dbe2e7'),strokeWidth=.6));d.add(String(32,pos-4,f'{tick:g}',fontSize=10,fillColor=ink))
    d.add(Line(80,100,80,370,strokeColor=ink));d.add(Line(80,100,710,100,strokeColor=ink));d.add(String(19,246,unit,fontSize=11,fillColor=ink))
    rng=random.Random(20261022);palette=['#256c98','#b4652c','#48794b','#96578a']
    for i,(group,data) in enumerate(groups.items()):
        center=80+(i+.5)*630/len(groups);half=min(45,150/len(groups));color=HexColor(palette[i]);mean=result['groups'][group]['mean']
        for _,value in data:d.add(Circle(center+rng.uniform(-half,half),y(value),2.8,fillColor=color,strokeColor=None))
        d.add(Line(center-half-6,y(mean),center+half+6,y(mean),strokeColor=ink,strokeWidth=2.2))
        d.add(String(center-half,75,group,fontSize=12,fillColor=ink));d.add(String(center-half,55,f'n={len(data)}, mean={mean:.2f} {unit}',fontSize=9,fillColor=ink))
    d.add(String(80,22,'Source alias: '+alias+' | complete grouping and measurement records | seed 20261022',fontSize=9,fillColor=ink))
    with paths['.svg'].open('x',encoding='utf-8') as f:f.write(renderSVG.drawToString(d))
    result.update(unit=unit,numeric_column=numeric_column,group_column=group_column,filter={filter_column:filter_value},plot_type='raw_points_and_mean',jitter_seed=20261022,error_bars='none')
    with paths['.statistics.json'].open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    with paths['.clean.csv'].open('x',encoding='utf-8',newline='') as f:
        writer=csv.writer(f);writer.writerow(['source_csv_line',group_column,numeric_column])
        for group,data in groups.items():
            for line,value in data:writer.writerow([line,group,value])
    caption=f'{title}。按 {filter_column}={filter_value} 筛选；分组字段为 {group_column}，测量字段为 {numeric_column}，单位 {unit}。点表示保留的原始观察，黑线表示组均值，无误差线。分组或测量缺失的记录排除，原 CSV 行号随文件保存。仅作描述性二次分析，不据此推断因果。来源别名 {alias}，SHA256 {result["source_sha256"]}。\n'
    with paths['.caption.md'].open('x',encoding='utf-8') as f:f.write(caption)
    dependencies=Path(sys.executable).parent.parent
    node=dependencies/'node/bin/node.exe';sharp=dependencies/'node/node_modules/sharp'
    if not node.is_file() or not sharp.is_dir():raise ValueError('Prepared Node/sharp renderer unavailable; SVG and calculation evidence retained, PNG not claimed')
    script="const s=require(process.argv[1]);s(process.argv[2]).resize(1520).png().toFile(process.argv[3]).catch(e=>{console.error(e.message);process.exit(2)});"
    command=[str(node),'-e',script,str(sharp),str(paths['.svg']),str(paths['.png'])]
    process=subprocess.run(command,capture_output=True,timeout=60)
    with paths['.render.json'].open('x',encoding='utf-8') as f:json.dump({'command':command,'exit_code':process.returncode,'stderr':process.stderr.decode('utf-8','replace')},f,ensure_ascii=False,indent=2)
    if process.returncode or not paths['.png'].is_file():raise ValueError('PNG rendering failed; preserve SVG and renderer log')
    return {'status':'FIGURE_WRITTEN_VISUAL_REVIEW_REQUIRED','files':[{'name':p.name,'sha256':sha(p)} for p in paths.values()],'source_sha256':result['source_sha256'],'groups':result['groups'],'error_bars':'none','scientific_review':'NOT_PERFORMED'}
