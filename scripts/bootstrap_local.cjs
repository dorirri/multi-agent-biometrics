// Public CPU runtime + one official small instruction model. No API keys.
const fs=require('fs'),https=require('https'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'..');
function response(url){return new Promise((resolve,reject)=>https.get(url,{headers:{'User-Agent':'ResearchTriage/1.0'}},r=>{if([301,302,303,307,308].includes(r.statusCode)){r.resume();response(new URL(r.headers.location,url).href).then(resolve,reject)}else if(r.statusCode===200)resolve(r);else{r.resume();reject(Error('HTTP '+r.statusCode))}}).on('error',reject))}
async function json(url){const r=await response(url);let s='';for await(const b of r)s+=b;return JSON.parse(s)}
async function download(url,relative,expected){
 const file=path.join(root,relative);fs.mkdirSync(path.dirname(file),{recursive:true});
 if(!fs.existsSync(file)){
  const r=await response(url);const out=fs.createWriteStream(file+'.part');let bytes=0,next=100e6;const hash=crypto.createHash('sha256');const started=Date.now();
  r.on('data',b=>{hash.update(b);bytes+=b.length;if(bytes>=next){console.log(relative,Math.round(bytes/1e6)+' MB');next+=100e6}});
  await new Promise((resolve,reject)=>{r.pipe(out);out.on('finish',resolve);out.on('error',reject);r.on('error',reject)});
  const digest=hash.digest('hex');if(expected&&digest!==expected)throw Error('SHA256 mismatch '+relative);fs.renameSync(file+'.part',file);return {path:relative,url,bytes,sha256:digest,download_seconds:(Date.now()-started)/1000};
 }
 const hash=crypto.createHash('sha256');for await(const b of fs.createReadStream(file))hash.update(b);const digest=hash.digest('hex');if(expected&&digest!==expected)throw Error('SHA256 mismatch '+relative);return {path:relative,url,bytes:fs.statSync(file).size,sha256:digest,cached:true};
}
async function main(){
 const info=await json('https://huggingface.co/api/models/Qwen/Qwen2.5-1.5B-Instruct-GGUF');const rev=info.sha;
 const tree=await json(`https://huggingface.co/api/models/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/${rev}`);const model=tree.find(x=>x.path==='qwen2.5-1.5b-instruct-q4_k_m.gguf');
 const release=await json('https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b12032');const asset=release.assets.find(x=>x.name==='llama-b12032-bin-win-cpu-x64.zip');
 console.log('Model bytes:',model.size,'CPU runtime bytes:',asset.size);
 const records=await Promise.all([
  download(`https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/${rev}/${model.path}`,'models/'+model.path,model.lfs.oid),
  download(asset.browser_download_url,'downloads/llama-b12032-bin-win-cpu-x64.zip',asset.digest?.replace('sha256:','')),
  download(`https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/${rev}/LICENSE`,'docs/third_party/QWEN_LICENSE.txt'),
  download('https://raw.githubusercontent.com/ggml-org/llama.cpp/b12032/LICENSE','docs/third_party/LLAMA_CPP_LICENSE.txt')]);
 const result={model:'Qwen2.5-1.5B-Instruct',quantization:'Q4_K_M',model_revision:rev,runtime_release:release.tag_name,records};
 fs.writeFileSync(path.join(root,'data/local_backend_manifest.json'),JSON.stringify(result,null,2));console.log('Verified downloads complete');
}
main().catch(e=>{console.error(e.message);process.exitCode=1});
