import {useState} from 'react';
import {useParams,Link} from 'react-router-dom';
import {send} from '../api';
import {text} from '../text';
import {useData,usePerson,Heading,Notice,DataTable,Row} from '../common';

const STAGE_ORDER = [
  'need_identified',
  'feasibility',
  'planning_design',
  'approvals',
  'procurement',
  'construction',
  'testing_handover',
  'operation_maintenance',
  'renewal_disposal'
];

export default function ProjectDetail(){
  const {id}=useParams();
  const person=usePerson();
  const {data:project,error,reload}=useData('/projects/'+id);
  const assets=useData('/assets').data||[];
  const [transitioning,setTransitioning]=useState(false);
  const [nextStage,setNextStage]=useState('feasibility');
  const [decision,setDecision]=useState('advanced');
  const [comments,setComments]=useState('');
  const [evidenceUrl,setEvidenceUrl]=useState('');
  const [linkingAsset,setLinkingAsset]=useState(false);
  const [selectedAssetId,setSelectedAssetId]=useState('');
  const [relationKind,setRelationKind]=useState('creates');
  const [addingItem,setAddingItem]=useState(false);
  const [itemType,setItemType]=useState('risk');
  const [itemTitle,setItemTitle]=useState('');
  const [itemSeverity,setItemSeverity]=useState('medium');
  const [failure,setFailure]=useState('');

  if(!project) return <><Notice error={error}/><p>{text.loading}</p></>;

  const currentIdx = STAGE_ORDER.indexOf(project.current_stage_key);
  const canAdvance = ['reviewer','admin'].includes(person.role);
  const canEdit = ['editor','admin'].includes(person.role);

  return (
    <>
      <Heading
        title={project.name}
        subtitle={`${project.code} · ${project.project_type} · ${project.area_name} ${project.department_name ? '· ' + project.department_name : ''}`}
      >
        <span className="badge">{text.projectStages[project.current_stage_key]||project.current_stage_key}</span>
      </Heading>
      <Notice error={failure}/>

      {/* 9-Stage Visual Lifecycle Progress Tracker */}
      <section className="panel">
        <h2>{text.stage} Progression (v2 Full Lifecycle)</h2>
        <div style={{display:'flex',overflowX:'auto',padding:'1rem 0',gap:'0.5rem',alignItems:'center'}}>
          {STAGE_ORDER.map((stageKey,idx)=>{
            const isCurrent = stageKey === project.current_stage_key;
            const isPast = idx < currentIdx;
            const bg = isCurrent ? 'var(--primary, #197967)' : isPast ? '#258665' : 'var(--surface-sunken, #e5e7eb)';
            const color = isCurrent || isPast ? '#fff' : 'inherit';
            return (
              <div
                key={stageKey}
                style={{
                  display:'flex',
                  alignItems:'center',
                  background:bg,
                  color,
                  padding:'0.5rem 0.8rem',
                  borderRadius:'4px',
                  fontSize:'0.82rem',
                  fontWeight:isCurrent?'bold':'normal',
                  whiteSpace:'nowrap'
                }}
              >
                <span>{idx + 1}. {text.projectStages[stageKey]||stageKey}</span>
              </div>
            );
          })}
        </div>

        {canAdvance&&(
          <div style={{marginTop:'1rem'}}>
            <button className="primary" onClick={()=>{
              const next = STAGE_ORDER[Math.min(currentIdx + 1, STAGE_ORDER.length - 1)];
              setNextStage(next);
              setTransitioning(!transitioning);
            }}>
              {transitioning ? text.cancel : `⚡ ${text.advanceStage}`}
            </button>
          </div>
        )}

        {transitioning&&canAdvance&&(
          <form style={{marginTop:'1rem',padding:'1rem',background:'var(--surface-sunken)',borderRadius:'4px'}} onSubmit={async e=>{
            e.preventDefault();
            try{
              await send(`/projects/${id}/stages`,{
                to_stage:nextStage,
                decision,
                comments,
                evidence_url:evidenceUrl
              });
              setTransitioning(false);
              setComments('');
              reload();
              setFailure('');
            }catch(err){
              setFailure((err as Error).message);
            }
          }}>
            <h3>Advance Project Stage (Governance Gate)</h3>
            <div className="two-columns">
              <label>Target Stage
                <select value={nextStage} onChange={e=>setNextStage(e.target.value)}>
                  {STAGE_ORDER.map(k=><option key={k} value={k}>{text.projectStages[k]}</option>)}
                </select>
              </label>
              <label>{text.decision}
                <select value={decision} onChange={e=>setDecision(e.target.value)}>
                  <option value="advanced">Advanced / Approved</option>
                  <option value="held">Held for Conditions</option>
                  <option value="rejected">Rejected / Reverted</option>
                </select>
              </label>
              <label>{text.decisionComments}
                <input required placeholder="Rationale for stage gate progression" value={comments} onChange={e=>setComments(e.target.value)}/>
              </label>
              <label>{text.evidenceUrl}
                <input placeholder="Link to minutes, approval signoff, or doc" value={evidenceUrl} onChange={e=>setEvidenceUrl(e.target.value)}/>
              </label>
            </div>
            <div style={{marginTop:'0.8rem',display:'flex',gap:'0.5rem'}}>
              <button className="primary">{text.save}</button>
              <button type="button" onClick={()=>setTransitioning(false)}>{text.cancel}</button>
            </div>
          </form>
        )}
      </section>

      {/* Budget & Cost Control */}
      <section className="panel">
        <h2>{text.budget} & Cost Control (Req #7)</h2>
        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(200px, 1fr))',gap:'1rem'}}>
          <div className="card">
            <small>{text.budget}</small>
            <h3>₹{Number(project.approved_budget||0).toLocaleString()}</h3>
          </div>
          <div className="card">
            <small>{text.forecast}</small>
            <h3>₹{Number(project.forecast_cost||0).toLocaleString()}</h3>
          </div>
          <div className="card">
            <small>{text.actual}</small>
            <h3>₹{Number(project.actual_cost||0).toLocaleString()}</h3>
          </div>
          <div className="card">
            <small>Variance</small>
            <h3 style={{color: Number(project.forecast_cost) > Number(project.approved_budget) ? 'var(--danger,#e11d48)' : 'inherit'}}>
              ₹{(Number(project.forecast_cost||0) - Number(project.approved_budget||0)).toLocaleString()}
            </h3>
          </div>
        </div>
      </section>

      {/* Linked Assets */}
      <section className="panel">
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'1rem'}}>
          <h2>{text.linkedAssets} (Req #1, #13, #22)</h2>
          {canEdit&&(
            <button onClick={()=>setLinkingAsset(!linkingAsset)}>
              {linkingAsset ? text.cancel : `+ ${text.linkAsset}`}
            </button>
          )}
        </div>

        {linkingAsset&&canEdit&&(
          <form style={{background:'var(--surface-sunken)',padding:'1rem',borderRadius:'4px',marginBottom:'1rem'}} onSubmit={async e=>{
            e.preventDefault();
            if(!selectedAssetId) return;
            try{
              await send(`/projects/${id}/assets`,{asset_id:selectedAssetId,relation_kind:relationKind});
              setLinkingAsset(false);
              reload();
              setFailure('');
            }catch(err){
              setFailure((err as Error).message);
            }
          }}>
            <div className="two-columns">
              <label>Select Asset
                <select value={selectedAssetId} onChange={e=>setSelectedAssetId(e.target.value)}>
                  <option value="">Choose asset...</option>
                  {assets.map((a:Row)=><option key={a.id} value={a.id}>{a.register_code} · {a.name||text.noName}</option>)}
                </select>
              </label>
              <label>{text.relationKind}
                <select value={relationKind} onChange={e=>setRelationKind(e.target.value)}>
                  <option value="creates">Creates (Capital Delivery)</option>
                  <option value="modifies">Modifies / Upgrades</option>
                  <option value="retires">Retires / Replaces</option>
                </select>
              </label>
            </div>
            <div style={{marginTop:'0.8rem',display:'flex',gap:'0.5rem'}}>
              <button className="primary">{text.save}</button>
              <button type="button" onClick={()=>setLinkingAsset(false)}>{text.cancel}</button>
            </div>
          </form>
        )}

        <DataTable
          rows={project.assets||[]}
          columns={[
            [text.code, (r:Row)=><Link to={`/assets/${r.id}`}>{r.register_code}</Link>],
            [text.name, (r:Row)=>r.name||text.noName],
            [text.type, (r:Row)=>r.type_name],
            [text.stage, (r:Row)=>text.stages[r.stage_key]||r.stage_key],
            [text.relationKind, (r:Row)=>r.relation_kind],
            ['', (r:Row)=><Link className="button quiet" to={`/assets/${r.id}`}>{text.open}</Link>]
          ]}
        />
      </section>

      {/* Items, Risks & Approvals */}
      <section className="panel">
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'1rem'}}>
          <h2>{text.projectItems} (Req #3, #4, #6, #10, #18)</h2>
          {canEdit&&(
            <button onClick={()=>setAddingItem(!addingItem)}>
              {addingItem ? text.cancel : `+ ${text.addItem}`}
            </button>
          )}
        </div>

        {addingItem&&canEdit&&(
          <form style={{background:'var(--surface-sunken)',padding:'1rem',borderRadius:'4px',marginBottom:'1rem'}} onSubmit={async e=>{
            e.preventDefault();
            try{
              await send(`/projects/${id}/items`,{
                item_type:itemType,
                title:itemTitle,
                severity:itemSeverity
              });
              setAddingItem(false);
              setItemTitle('');
              reload();
              setFailure('');
            }catch(err){
              setFailure((err as Error).message);
            }
          }}>
            <div className="two-columns">
              <label>{text.itemType}
                <select value={itemType} onChange={e=>setItemType(e.target.value)}>
                  <option value="need">Need / Option Appraisal</option>
                  <option value="feasibility">Feasibility Check</option>
                  <option value="permit">Statutory Permit / Clearance</option>
                  <option value="milestone">Milestone / Work Package</option>
                  <option value="risk">Risk / Issue</option>
                  <option value="quality">Quality / Defect Check</option>
                  <option value="safety">Safety / Environmental Log</option>
                </select>
              </label>
              <label>{text.name} / Title
                <input required value={itemTitle} placeholder="Item title or description" onChange={e=>setItemTitle(e.target.value)}/>
              </label>
              <label>{text.severity}
                <select value={itemSeverity} onChange={e=>setItemSeverity(e.target.value)}>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </label>
            </div>
            <div style={{marginTop:'0.8rem',display:'flex',gap:'0.5rem'}}>
              <button className="primary">{text.save}</button>
              <button type="button" onClick={()=>setAddingItem(false)}>{text.cancel}</button>
            </div>
          </form>
        )}

        <DataTable
          rows={project.items||[]}
          columns={[
            [text.itemType, (r:Row)=><span className="badge">{r.item_type}</span>],
            [text.name, (r:Row)=><strong>{r.title}</strong>],
            [text.status, (r:Row)=>r.status],
            [text.severity, (r:Row)=>r.severity||'—'],
            ['Owner', (r:Row)=>r.owner_name||'—']
          ]}
        />
      </section>

      {/* Stage History */}
      <section className="panel">
        <h2>{text.stageHistory} (Req #2, #11)</h2>
        <DataTable
          rows={project.history||[]}
          columns={[
            ['Transition', (r:Row)=>`${text.projectStages[r.from_stage]||r.from_stage||'Start'} ➔ ${text.projectStages[r.to_stage]||r.to_stage}`],
            [text.decision, (r:Row)=>r.decision],
            ['Moved By', (r:Row)=>r.who_name],
            ['Reviewer', (r:Row)=>r.reviewer_name||'—'],
            ['Comments', (r:Row)=>r.comments||'—'],
            ['Date', (r:Row)=>new Date(r.happened_at).toLocaleString()]
          ]}
        />
      </section>
    </>
  );
}
