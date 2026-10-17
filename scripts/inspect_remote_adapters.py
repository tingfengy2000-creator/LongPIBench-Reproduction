"""Inspect ZIP central directories and adapter JSON using bounded HTTP ranges.

Never retrieves weight tensors, never deserializes pickle/bin payloads.
"""
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'audit/evidence/adapter_metadata.json'

class RemoteZip(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.pos, self.bytes_read = url, size, 0, 0
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        self.pos = offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        return self.pos
    def read(self,n=-1):
        n = self.size-self.pos if n<0 else min(n,self.size-self.pos)
        if not n: return b''
        if n>1024*1024 or self.bytes_read+n>5*1024*1024:
            raise ValueError('Metadata-only download limit exceeded')
        req=urllib.request.Request(self.url,headers={'Range':f'bytes={self.pos}-{self.pos+n-1}'})
        with urllib.request.urlopen(req,timeout=45) as r:
            if r.status!=206:
                raise ValueError(f'Expected HTTP 206, received {r.status}; refusing whole-file download')
            result=r.read(n)
        self.pos+=len(result)
        self.bytes_read+=len(result)
        return result

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    probes=json.loads((ROOT/'audit/evidence/weight_byte_probes.json').read_text(encoding='utf-8-sig'))
    results=[]
    for p in probes:
        row={'name':p['name'],'url':p['url']}
        try:
            remote=RemoteZip(p['url'],int(p['content_range'].split('/')[-1]))
            with zipfile.ZipFile(remote) as archive:
                row['entries']=[{'name':i.filename,'bytes':i.file_size,'compressed_bytes':i.compress_size} for i in archive.infolist()]
                row['adapter_configs']={}
                for entry in archive.infolist():
                    if entry.filename.endswith('adapter_config.json') and not entry.filename.startswith('__MACOSX/'):
                        if entry.file_size>65536: raise ValueError('Unexpectedly large adapter config')
                        row['adapter_configs'][entry.filename]=json.loads(archive.read(entry))
            row['metadata_bytes_transferred']=remote.bytes_read
            row['status']='METADATA_ONLY_VERIFIED'
        except Exception as e:
            row.update(status='UNVERIFIED',error=str(e))
        results.append(row)
    OUT.write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(results,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
