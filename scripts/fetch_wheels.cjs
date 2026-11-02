// Optional Windows CPython 3.11 bootstrap helper; downloads public wheels only.
const https = require('https');
const fs = require('fs');
const path = require('path');
const versions = {
 'numpy':'2.2.6','opencv-python-headless':'4.12.0.88','onnxruntime':'1.23.2','pydantic':'2.12.5','matplotlib':'3.10.8','pytest':'9.0.2',
 'coloredlogs':'15.0.1','flatbuffers':'25.12.19','protobuf':'7.36.2','sympy':'1.14.0','annotated-types':'0.8.0','pydantic-core':'2.41.5','typing-extensions':'4.16.0','typing-inspection':'0.4.2',
 'contourpy':'1.3.3','cycler':'0.12.1','fonttools':'4.68.0','kiwisolver':'1.5.1','pillow':'13.0.0','pyparsing':'3.3.3','python-dateutil':'4.0.0','colorama':'0.4.6','iniconfig':'2.3.1','pluggy':'1.7.0','pygments':'2.21.0','tzdata':'2026.6','humanfriendly':'10.0','pyreadline3':'3.5.6','mpmath':'1.3.0'
};
function get(url){return new Promise((resolve,reject)=>{https.get(url,r=>{if(r.statusCode!==200){r.resume();reject(new Error('HTTP '+r.statusCode));return;}const chunks=[];r.on('data',d=>chunks.push(d));r.on('end',()=>resolve(Buffer.concat(chunks)));r.on('error',reject)}).on('error',reject)})}
async function run(){
 const dir=path.join(__dirname,'..','downloads','wheels');fs.mkdirSync(dir,{recursive:true});
 const jobs=Object.entries(versions);let cursor=0;
 await Promise.all(Array.from({length:6},async()=>{while(cursor<jobs.length){const [pkg,v]=jobs[cursor++];const meta=JSON.parse((await get(`https://pypi.org/pypi/${pkg}/${v}/json`)).toString());const files=meta.urls.filter(x=>/\.whl$/.test(x.filename));const f=files.find(x=>/cp311-cp311-win_amd64/.test(x.filename))||files.find(x=>/cp3(?:7|8|9|10|11)-abi3-win_amd64/.test(x.filename))||files.find(x=>/(?:py3|py2.py3)-none-any/.test(x.filename));if(!f)throw Error('No compatible wheel '+pkg);const target=path.join(dir,f.filename);if(!fs.existsSync(target)){const b=await get(f.url);if(require('crypto').createHash('sha256').update(b).digest('hex')!==f.digests.sha256)throw Error('Hash mismatch');fs.writeFileSync(target,b)}console.log(pkg,v)}}));
 fs.writeFileSync(path.join(__dirname,'..','requirements-lock.txt'),Object.entries(versions).map(([k,v])=>`${k}==${v}`).join('\n')+'\n');
}
run().catch(e=>{console.error(e.message);process.exitCode=1});
