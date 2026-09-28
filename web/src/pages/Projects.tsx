import {useState} from 'react';
import {Link} from 'react-router-dom';
import {send} from '../api';
import {text} from '../text';
import {useData,usePerson,Heading,Notice,DataTable,Select,Row} from '../common';

export default function Projects(){
  const person=usePerson();
  const canCreate=['editor','admin'].includes(person.role);
  const [q,setQ]=useState('');
  const [stageKey,setStageKey]=useState('');
  const [status,setStatus]=useState('');
  const [creating,setCreating]=useState(false);
  const [failure,setFailure]=useState('');

  const areas=useData('/areas').data||[];
  const departments=useData('/department-systems').data||[];

  const query=new URLSearchParams({
    q,
    ...(stageKey?{stage_key:stageKey}:{}),
    ...(status?{status}:{})
  }).toString();

  const {data:projects,error,reload}=useData('/projects?'+query);

  const [form,setForm]=useState({
    name:'',
    project_type:'Road Improvement',
    area_id:areas[0]?.id||1,
    department_system_id:departments[0]?.id||null,
    current_stage_key:'need_identified',
    approved_budget:'0',
    description:''
  });

  return (
    <>
      <Heading title={text.projectTitle} subtitle={text.projectHelp}/>
      <Notice error={error||failure}/>

      <section className="panel">
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:'1rem',marginBottom:'1rem'}}>
          <div className="filters" style={{margin:0}}>
            <label>{text.search}
              <input value={q} placeholder="Search project name, code, type..." onChange={e=>setQ(e.target.value)}/>
            </label>
            <Select
              label={text.stage}
              value={stageKey}
              onChange={setStageKey}
              items={[['',text.all],...Object.entries(text.projectStages)]}
            />
            <Select
              label={text.status}
              value={status}
              onChange={setStatus}
              items={[['',text.all],['active','Active'],['on_hold','On hold'],['completed','Completed'],['cancelled','Cancelled']]}
            />
          </div>

          {canCreate&&(
            <button className="primary" onClick={()=>setCreating(!creating)}>
              {creating?text.cancel:`+ ${text.newProject}`}
            </button>
          )}
        </div>

        {creating&&(
          <form className="panel" style={{background:'var(--surface-sunken)',marginBottom:'1.5rem'}} onSubmit={async e=>{
            e.preventDefault();
            try{
              await send('/projects',{
                ...form,
                area_id:Number(form.area_id),
                department_system_id:form.department_system_id?Number(form.department_system_id):null,
                approved_budget:Number(form.approved_budget)
              });
              setCreating(false);
              reload();
              setFailure('');
            }catch(err){
              setFailure((err as Error).message);
            }
          }}>
            <h3>{text.newProject}</h3>
            <div className="two-columns">
              <label>{text.name}
                <input required value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/>
              </label>
              <label>{text.type}
                <input required value={form.project_type} placeholder="e.g. Highway upgrade, Water main" onChange={e=>setForm({...form,project_type:e.target.value})}/>
              </label>
              <label>{text.area}
                <select value={form.area_id} onChange={e=>setForm({...form,area_id:Number(e.target.value)})}>
                  {areas.map((a:Row)=><option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </label>
              <label>{text.department}
                <select value={form.department_system_id||''} onChange={e=>setForm({...form,department_system_id:e.target.value?Number(e.target.value):null})}>
                  <option value="">None / Direct</option>
                  {departments.map((d:Row)=><option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </label>
              <label>{text.stage}
                <select value={form.current_stage_key} onChange={e=>setForm({...form,current_stage_key:e.target.value})}>
                  {Object.entries(text.projectStages).map(([k,v])=><option key={k} value={k}>{v}</option>)}
                </select>
              </label>
              <label>{text.budget} (₹)
                <input type="number" min="0" value={form.approved_budget} onChange={e=>setForm({...form,approved_budget:e.target.value})}/>
              </label>
            </div>
            <label style={{marginTop:'0.5rem'}}>{text.description}
              <textarea value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/>
            </label>
            <div style={{marginTop:'1rem',display:'flex',gap:'0.5rem'}}>
              <button className="primary">{text.save}</button>
              <button type="button" onClick={()=>setCreating(false)}>{text.cancel}</button>
            </div>
          </form>
        )}

        <DataTable
          rows={projects||[]}
          columns={[
            [text.code, (r:Row)=><Link to={`/projects/${r.id}`}>{r.code}</Link>],
            [text.name, (r:Row)=><strong>{r.name}</strong>],
            [text.type, (r:Row)=>r.project_type],
            [text.area, (r:Row)=>r.area_name],
            [text.stage, (r:Row)=><span className="badge">{text.projectStages[r.current_stage_key]||r.current_stage_key}</span>],
            [text.budget, (r:Row)=>r.approved_budget?`₹${Number(r.approved_budget).toLocaleString()}`:'—'],
            [text.linkedAssets, (r:Row)=>r.linked_asset_count||0],
            ['', (r:Row)=><Link className="button quiet" to={`/projects/${r.id}`}>{text.open}</Link>]
          ]}
        />
      </section>
    </>
  );
}
