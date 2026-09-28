import {text} from './text';
export const base=(import.meta as unknown as {env:Record<string,string>}).env.VITE_API_URL||'http://localhost:8000';
export function token(){return sessionStorage.getItem('asset-token')||'';}
export async function request(path:string,options:RequestInit={}){
 const headers:Record<string,string>={Authorization:`Bearer ${token()}`};
 if(options.body&&!(options.body instanceof FormData))headers['Content-Type']='application/json';
 const response=await fetch(base+path,{...options,headers:{...headers,...options.headers}});
 if(response.status===401&&!path.startsWith('/auth')){sessionStorage.removeItem('asset-token');location.assign('/sign-in');}
 if(!response.ok){const result=await response.json().catch(()=>({message:text.failed}));throw Error(result.message||text.failed);}
 return response;
}
export async function get(path:string){return (await request(path)).json();}
export async function send(path:string,body:unknown,method='POST'){return (await request(path,{method,body:body instanceof FormData?body:JSON.stringify(body)})).json();}
export async function openFile(path:string){const response=await request(path);const url=URL.createObjectURL(await response.blob());window.open(url,'_blank','noopener');setTimeout(()=>URL.revokeObjectURL(url),60000);}
export async function shrinkPhoto(file:File){const bitmap=await createImageBitmap(file);const scale=Math.min(1,1600/Math.max(bitmap.width,bitmap.height));const canvas=document.createElement('canvas');canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);canvas.getContext('2d')!.drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();return new Promise<Blob>((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(Error(text.failed)),'image/jpeg',.8));}
