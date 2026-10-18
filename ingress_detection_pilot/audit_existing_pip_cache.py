"""Readonly detailed cache inventory for user review; never deletes files.

Local-machine package inventory stays outside the public research repository.
No cached Python/pickle/native code is executed. ZIP metadata is read only.
"""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from email.parser import BytesParser
import gzip
import hashlib
import html
import json
from pathlib import Path
import re
import stat
import zipfile
from pip._vendor import msgpack

SOURCE = Path(r'C:\Users\Admin\AppData\Local\pip\cache')
OUTPUT = Path(r'E:\Caches\audit\pip-cache-20261018-v2')


def headers(path):
    try:
        blob = path.read_bytes()
        if not blob.startswith(b'cc=4,') or len(blob)>1024**2: return {}
        data = msgpack.unpackb(blob[5:], raw=False)
        return {str(k).lower():str(v) for k,v in data.get('response',{}).get('headers',{}).items()}
    except Exception:
        return {}


def identify(path):
    package,version,description='','',''
    with path.open('rb') as stream: head=stream.read(128*1024)
    kind='其他缓存文件（具体用途未确认）'
    h=headers(Path(str(path)[:-5])) if path.suffix=='.body' else headers(path)
    if head.startswith(b'cc=4,'):
        return 'HTTP响应缓存元数据','','','CacheControl MessagePack：状态和响应头；不包含已安装环境',h
    if zipfile.is_zipfile(path):
        kind='ZIP/wheel安装包副本'
        try:
            with zipfile.ZipFile(path) as archive:
                members=archive.infolist()
                metadata=next((x for x in members if x.filename.endswith('.dist-info/METADATA')),None)
                if metadata and metadata.file_size<=2*1024**2:
                    parsed=BytesParser().parsebytes(archive.read(metadata),headersonly=True)
                    package,version=str(parsed.get('Name','')),str(parsed.get('Version',''))
                    kind='wheel安装包副本'
                roots=sorted({x.filename.split('/')[0] for x in members})
                description=f'压缩包含{len(members)}个成员；顶层：'+', '.join(roots[:8])
        except Exception:description='ZIP可识别，具体成员读取未完成'
    elif head.startswith(b'\x1f\x8b'):
        kind='gzip压缩下载副本'
        try:
            with gzip.open(path,'rb') as stream: block=stream.read(8*1024**2+1)
            if block.lstrip().startswith((b'{',b'[')):
                kind='gzip压缩JSON包索引'
                description='压缩的JSON索引，不是已安装包或环境'
                if len(block)<=8*1024**2:
                    data=json.loads(block)
                    if isinstance(data,dict):
                        package=str(data.get('name',''))
                        if isinstance(data.get('files'),list):description+=f"；{len(data['files'])}个发行文件条目"
            elif block[257:262]==b'ustar':
                member=block[:100].split(b'\0')[0].decode('utf-8',errors='replace')
                description='tar归档首成员：'+member
            else:
                description='gzip压缩内容，未确认具体格式；不执行或猜测为归档'
        except Exception:description='gzip头部可识别，内部内容未确认'
    elif head.startswith(b'Metadata-Version:'):
        kind='包METADATA文本'
        parsed=BytesParser().parsebytes(head,headersonly=True)
        package,version=str(parsed.get('Name','')),str(parsed.get('Version',''))
        description='包名称、版本、依赖和说明的缓存文本'
    elif head.lstrip().startswith((b'{',b'[')):
        kind='JSON索引/检查信息'
        if path.stat().st_size<4*1024**2:
            try:
                data=json.loads(path.read_bytes())
                if isinstance(data,dict):
                    package=str(data.get('name',''))
                    description='JSON顶层字段：'+', '.join(list(data)[:10])
                    if isinstance(data.get('files'),list):description+=f"；{len(data['files'])}个发行文件条目"
            except Exception:description='JSON样式文本，未完整解析'
    elif b'<html' in head[:500].lower() or b'<!doctype html' in head[:500].lower():
        kind='HTML包索引缓存';description='包索引页面，不执行或导出页面中的链接'
    if not package:package=h.get('x-pypi-file-project','')
    if not version:version=h.get('x-pypi-file-version','')
    if not description:description=h.get('content-type','未知二进制/文本缓存')
    return kind,package,version,description,h


def main():
    assert SOURCE.resolve()==Path(r'C:\Users\Admin\AppData\Local\pip\cache')
    assert not (SOURCE.stat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    OUTPUT.mkdir(parents=True,exist_ok=False)
    rows=[]
    for path in SOURCE.rglob('*'):
        if not path.is_file():continue
        info=path.stat()
        assert not (info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        assert path.resolve().is_relative_to(SOURCE.resolve())
        kind,package,version,description,h=identify(path)
        with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        rows.append({'path':str(path),'relative_path':str(path.relative_to(SOURCE)),
            'bytes':info.st_size,'MiB':round(info.st_size/1024**2,3),
            'modified_utc':datetime.fromtimestamp(info.st_mtime,timezone.utc).isoformat(),
            'sha256':digest,'kind':kind,'package':package,'version':version,
            'content_type':h.get('content-type',''),'content_summary':description})
    rows.sort(key=lambda r:r['bytes'],reverse=True)
    for row in rows:
        if row['kind']=='HTTP响应缓存元数据':
            body=next((b for b in rows if b['path']==row['path']+'.body'),None)
            if body:row['package'],row['version']=body['package'],body['version']
    total=sum(r['bytes'] for r in rows)
    with (OUTPUT/'all_files.csv').open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with (OUTPUT/'all_files.json').open('x',encoding='utf-8') as stream:json.dump(rows,stream,ensure_ascii=False,indent=2)
    grouped=defaultdict(lambda:{'files':0,'bytes':0})
    for row in rows:
        key=(row['package'] or '未识别包名',row['version'] or '未知版本',row['kind'])
        grouped[key]['files']+=1;grouped[key]['bytes']+=row['bytes']
    groups=[{'package':k[0],'version':k[1],'kind':k[2],**v} for k,v in grouped.items()]
    groups.sort(key=lambda r:r['bytes'],reverse=True)
    with (OUTPUT/'by_package.csv').open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['package','version','kind','files','bytes']);writer.writeheader();writer.writerows(groups)
    report={'status':'READ_ONLY_INVENTORY_FOR_OWNER_APPROVAL','source':str(SOURCE),'files':len(rows),
        'total_bytes':total,'GB_decimal':total/10**9,'GiB_binary':total/1024**3,
        'deleted_files':0,'all_file_sha256_recorded':True,'outside_cache_files_in_scope':False,
        'kinds':{k:{'files':sum(r['kind']==k for r in rows),'bytes':sum(r['bytes'] for r in rows if r['kind']==k)} for k in sorted({r['kind'] for r in rows})},
        'largest_packages':groups[:25], 'private_local_inventory_not_for_public_git':True,
        'created_utc':datetime.now(timezone.utc).isoformat()}
    (OUTPUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 待核对的C盘pip旧缓存清单','',f"根目录：`{SOURCE}`。共 **{len(rows)}个文件、{total:,} bytes（{total/10**9:.3f} GB / {total/1024**3:.3f} GiB）**。本轮只读，没有删除或迁移。",'',
      '完整逐文件路径、大小、SHA256、包名/版本、类型和内容概要见[all_files.csv](all_files.csv)或[可搜索完整表](all_files.html)。按包汇总见[by_package.csv](by_package.csv)。未知包名/未知内容如实标出，没有执行任何缓存代码。','',
      '## 内容是什么','',
      'wheel/压缩包是pip下载或构建的安装包副本，内部可能有.py源码、.pyd/.dll等二进制及.dist-info元数据；它们是缓存副本，不是当前已安装环境。HTTP元数据保存响应状态/头，.body保存对应下载内容；JSON/HTML通常是版本/包索引；selfcheck是pip版本检查记录。没有将pickle或原生代码作为程序运行。','',
      '批准删除会移除该目录内所有旧包副本和索引，使这些副本不能继续用于离线重装，日后需要时重新下载到E盘。范围不含D盘Python、E盘venv/模型、HF登录token、研究数据或其他C盘目录。具体包内容仅按文件识别，不对未知类型作“完全确认”的承诺。','',
      '## 最大的25个文件','', '| 包/版本 | 类型 | MiB | 完整路径 |','| --- | --- | --- | --- |']
    for r in rows[:25]:lines.append(f"| {r['package'] or '未识别'} {r['version']} | {r['kind']} | {r['MiB']:.3f} | `{r['path']}` |")
    lines+=['','## 全部类型','', '| 类型 | 文件数 | MiB |','| --- | --- | --- |']
    for kind,v in report['kinds'].items():lines.append(f"| {kind} | {v['files']} | {v['bytes']/1024**2:.3f} |")
    lines+=['','## 批准范围','',f'待你核对后，删除范围仅为上述`{SOURCE}`，并在删除前再次对照本清单检查文件未被新增/改写。该清单不是已经执行删除的证明。']
    (OUTPUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    cols=['package','version','kind','MiB','path','content_summary','sha256','modified_utc']
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>pip缓存逐文件清单</title><style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{padding:7px;border:1px solid #ddd;text-align:left;overflow-wrap:anywhere}th{position:sticky;top:0;background:#eef}input{padding:10px;width:70%}</style><h1>只读pip旧缓存清单，尚未删除</h1><p>搜索包名、版本、路径或类型；详情只保存在本机E盘。</p><input id="q" placeholder="筛选"><p id="n"></p><table><thead><tr>'''+''.join('<th>'+html.escape(c)+'</th>' for c in cols)+'</tr></thead><tbody>'
    for r in rows:page+='<tr>'+''.join('<td>'+html.escape(str(r[c]))+'</td>' for c in cols)+'</tr>'
    page+='''</tbody></table><script>const rows=[...document.querySelectorAll('tbody tr')];function f(){let n=0,q=document.getElementById('q').value.toLowerCase();for(const r of rows){const yes=r.textContent.toLowerCase().includes(q);r.hidden=!yes;n+=yes}document.getElementById('n').textContent=n+' / '+rows.length+' 个文件'}document.getElementById('q').oninput=f;f()</script></html>'''
    (OUTPUT/'all_files.html').write_text(page,encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
