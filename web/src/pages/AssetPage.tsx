import {useEffect,useState} from 'react';
import {Link,useParams,useNavigate} from 'react-router-dom';
import {send,request,shrinkPhoto} from '../api';
import {text,label} from '../text';
import {useData,usePerson,Heading,Notice,Row,Stage,Badges,JsonView,DataTable,Pager,Select} from '../common';
import {MapCanvas} from './MapPage';

function Photo({row}:{row:Row}){
  const [url,setUrl]=useState('');
  useEffect(()=>{
    let current='';
    request('/photos/'+row.id+'/file').then(r=>r.blob()).then(blob=>{
      current=URL.createObjectURL(blob);
      setUrl(current);
    });
    return()=>{if(current)URL.revokeObjectURL(current)};
  },[row.id]);
  return (
    <figure>
      {url&&<img src={url} alt={text.photoAlt}/>}
      <figcaption>
        {new Date(row.created_at).toLocaleDateString()}
        {row.taken_lat!=null&&<small>{text.distanceHint.replace('{n}',String(row.distance_m))}</small>}
      </figcaption>
    </figure>
  );
}

export default function AssetPage(){
  const {id}=useParams();
  const navigate=useNavigate();
  const {data:asset,error,reload}=useData('/assets/'+id);
  const [page,setPage]=useState(1);
  const history=useData('/assets/'+id+'/history?page='+page);
  const person=usePerson();
  const isAdmin=person.role==='admin';
  const edit=['editor','admin'].includes(person.role);
  const notes=person.role!=='viewer';
  const [note,setNote]=useState('');
  const [kind,setKind]=useState('note');
  const [problem,setProblem]=useState('');
  const [urgency,setUrgency]=useState('minor');
  const [message,setMessage]=useState('');
  const [includeLocation,setIncludeLocation]=useState(false);
  const [isEditing,setIsEditing]=useState(false);
  const [editName,setEditName]=useState('');
  const [editStage,setEditStage]=useState('');
  const stagesList=useData('/asset-types').data||[];

  useEffect(()=>{
    if(asset){
      setEditName(asset.name||'');
      setEditStage(asset.stage_key||'');
    }
  },[asset]);

  if(!asset) return <><Notice error={error}/><p>{text.loading}</p></>;

  return (
    <>
      <Heading title={asset.name||text.noName} subtitle={asset.register_code+' · '+asset.type.name+' · '+asset.area}>
        <Stage value={asset.stage_key}/>
      </Heading>
      <Badges row={asset}/>
      <Notice error={message}/>

      {isAdmin&&(
        <section className="panel" style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <div>
            <strong>Administrator Controls:</strong> Manage this asset directly.
          </div>
          <div style={{display:'flex',gap:'0.5rem'}}>
            <button className="primary" onClick={()=>setIsEditing(!isEditing)}>
              {isEditing?text.cancel:text.edit}
            </button>
            {asset.is_active&&(
              <button className="danger" onClick={async ()=>{
                if(window.confirm(`Are you sure you want to deactivate ${asset.register_code}?`)){
                  try{
                    await send('/assets/'+id,{},'DELETE');
                    reload();
                    history.reload();
                  }catch(e){
                    setMessage((e as Error).message);
                  }
                }
              }}>
                {text.deactivate}
              </button>
            )}
          </div>
        </section>
      )}

      {isEditing&&isAdmin&&(
        <section className="panel">
          <h2>{text.edit} Asset</h2>
          <form onSubmit={async e=>{
            e.preventDefault();
            try{
              await send('/assets/'+id,{name:editName,stage_key:editStage},'PATCH');
              setIsEditing(false);
              reload();
              history.reload();
            }catch(e){
              setMessage((e as Error).message);
            }
          }}>
            <div className="two-columns">
              <label>{text.name}
                <input value={editName} onChange={e=>setEditName(e.target.value)}/>
              </label>
              <label>{text.stage}
                <select value={editStage} onChange={e=>setEditStage(e.target.value)}>
                  {Object.entries(text.stages).map(([k,v])=><option key={k} value={k}>{v}</option>)}
                </select>
              </label>
            </div>
            <div style={{marginTop:'1rem',display:'flex',gap:'0.5rem'}}>
              <button className="primary">{text.save}</button>
              <button type="button" onClick={()=>setIsEditing(false)}>{text.cancel}</button>
            </div>
          </form>
        </section>
      )}

      {asset.projects&&asset.projects.length>0&&(
        <section className="panel">
          <h2>Linked Projects</h2>
          <DataTable
            rows={asset.projects}
            columns={[
              [text.code, (r:Row)=><Link to={'/projects/'+r.id}>{r.code}</Link>],
              [text.name, (r:Row)=>r.name],
              [text.stage, (r:Row)=>text.projectStages[r.current_stage_key]||r.current_stage_key],
              [text.relationKind, (r:Row)=>r.relation_kind]
            ]}
          />
        </section>
      )}

      <div className="asset-top">
        <section className="panel">
          <h2>{text.official}</h2>
          {asset.links.filter((r:Row)=>r.is_main).map((row:Row)=>(
            <div key={row.id}>
              <p>{text.keptBy} <strong>{row.system}</strong> · {text.checked} {new Date(row.last_seen_at).toLocaleDateString()}</p>
              <p className="muted">{text.officialNote}</p>
              <JsonView value={row.official_record.details}/>
            </div>
          ))}
          {notes&&<button onClick={()=>{setKind('correction_for_department');document.getElementById('note-box')?.focus()}}>{text.correction}</button>}
          <h3>{text.also}</h3>
          {asset.links.filter((r:Row)=>!r.is_main).map((r:Row)=><p key={r.id}>{r.system} · {r.source_id}</p>)}
        </section>
        <section className="panel small-map">
          <MapCanvas shape={asset.shape}/>
        </section>
      </div>

      <section className="panel">
        <h2>{text.contracts}</h2>
        <DataTable rows={asset.contracts} columns={[[text.number,r=><Link to={'/contracts/'+r.id}>{r.contract_number}</Link>],[text.contractor,r=>r.contractor_name],[text.completion,r=>r.completion_date],[text.end,r=>r.warranty_end_date]]}/>
      </section>

      <section className="panel">
        <h2>{text.problems}</h2>
        <DataTable rows={asset.problems} columns={[[text.description,r=>r.description],[text.urgency,r=>label(text.urgencyChoices,r.urgency)],[text.status,r=>label(text.statuses,r.status)]]}/>
        {edit&&(
          <form className="inline-form" onSubmit={async e=>{e.preventDefault();try{await send('/assets/'+id+'/problems',{description:problem,urgency});setProblem('');reload();history.reload()}catch(e){setMessage((e as Error).message)}}}>
            <label>{text.description}<textarea required value={problem} onChange={e=>setProblem(e.target.value)}/></label>
            <label>{text.urgency}<select value={urgency} onChange={e=>setUrgency(e.target.value)}>{Object.entries(text.urgencyChoices).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
            <button className="primary">{text.report}</button>
          </form>
        )}
      </section>

      <section className="panel">
        <h2>{text.photos}</h2>
        <div className="photo-grid">{asset.photos.map((r:Row)=><Photo key={r.id} row={r}/>)}</div>
        {edit&&<label className="check"><input type="checkbox" checked={includeLocation} onChange={e=>setIncludeLocation(e.target.checked)}/>{text.includeLocation}</label>}
        {edit&&<label className="file-label">{text.addPhoto}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={async e=>{const file=e.target.files?.[0];if(!file)return;try{const form=new FormData();form.append('file',await shrinkPhoto(file),'photo.jpg');if(includeLocation){const position=await new Promise<GeolocationPosition>((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{timeout:10000}));form.append('taken_lat',String(position.coords.latitude));form.append('taken_lon',String(position.coords.longitude));}await send('/assets/'+id+'/photos',form);reload();history.reload()}catch(e){setMessage((e as Error).message)}}}/></label>}
      </section>

      <section className="panel">
        <h2>{text.notes}</h2>
        {asset.notes.map((r:Row)=><blockquote key={r.id}><p>{r.body}</p><small>{r.full_name} · {new Date(r.created_at).toLocaleString()}</small></blockquote>)}
        {notes&&(
          <form onSubmit={async e=>{e.preventDefault();try{await send('/assets/'+id+'/notes',{kind,body:note});setNote('');reload();history.reload()}catch(e){setMessage((e as Error).message)}}}>
            <label>{kind==='note'?text.note:text.correctionKind}<textarea id="note-box" required value={note} onChange={e=>setNote(e.target.value)}/></label>
            <button>{text.addNote}</button>
          </form>
        )}
      </section>

      <section className="panel">
        <h2>{text.history}</h2>
        {history.data?.map((r:Row)=><div className="history-row" key={r.id}><span className="history-dot"/><div><strong>{r.summary}</strong><p>{r.full_name} · {new Date(r.happened_at).toLocaleString()}</p>{r.before_value&&<details><summary>{text.before} / {text.after}</summary><div className="two-columns"><JsonView value={r.before_value}/><JsonView value={r.after_value}/></div></details>}</div></div>)}
        <Pager page={page} setPage={setPage} count={history.data?.length||0}/>
      </section>
    </>
  );
}
