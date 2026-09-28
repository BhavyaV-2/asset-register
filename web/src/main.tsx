import {useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {BrowserRouter,Routes,Route,NavLink,Navigate,Outlet,useLocation} from 'react-router-dom';
import {text,canVisit,Role} from './text';
import {base,token} from './api';
import {useData,Person,Notice} from './common';
import SignIn from './pages/SignIn';
import AssetList from './pages/AssetList';
import AssetPage from './pages/AssetPage';
import MapPage from './pages/MapPage';
import BringInData from './pages/BringInData';
import ReviewQueue from './pages/ReviewQueue';
import ReviewItem from './pages/ReviewItem';
import Contracts from './pages/Contracts';
import Problems from './pages/Problems';
import Reports from './pages/Reports';
import Admin from './pages/Admin';
import HowItWorks from './pages/HowItWorks';
import './styles.css';
function Layout(){const {data:user,error}=useData('/me');const location=useLocation();if(!token())return <Navigate to="/sign-in"/>;if(!user)return <main><Notice error={error}/><p>{text.loading}</p></main>;if(!canVisit(user.role,location.pathname))return <Navigate to="/assets"/>;return <Person.Provider value={user}><div className="app-shell"><aside className="sidebar"><NavLink className="brand" to="/map"><span className="brand-mark">AR</span><span>{text.app}<small>{text.internal}</small></span></NavLink><nav>{text.menu.filter(([path])=>canVisit(user.role,path)).map(([path,name],index)=><NavLink key={path} to={path}><span className="nav-number">{String(index+1).padStart(2,'0')}</span>{name}</NavLink>)}</nav><div className="sidebar-bottom"><span className="sample-pill">{text.sample}</span><p>{text.event}</p></div></aside><div className="workspace"><header className="topbar"><div><span className="status-dot"/>{text.access}: <strong>{user.area_name||text.allAreas}</strong></div><div className="account"><span>{user.full_name}<small>{text.roles[user.role as Role]}</small></span><button onClick={()=>{sessionStorage.removeItem('asset-token');locationAssign()}}>{text.signOut}</button></div></header><main className="page"><Outlet/></main></div></div></Person.Provider>}
function locationAssign(){window.location.assign('/sign-in')}
function Wake(){const [slow,setSlow]=useState(false);useEffect(()=>{const timer=setTimeout(()=>setSlow(true),3000);fetch(base+'/health').catch(()=>undefined).finally(()=>{clearTimeout(timer);setSlow(false)});return()=>clearTimeout(timer)},[]);return slow?<div className="wake" role="status">{text.waking}</div>:null}
export function App(){return <BrowserRouter><Wake/><Routes><Route path="/sign-in" element={<SignIn/>}/><Route element={<Layout/>}><Route path="/" element={<Navigate to="/map"/>}/><Route path="/map" element={<MapPage/>}/><Route path="/assets" element={<AssetList/>}/><Route path="/assets/:id" element={<AssetPage/>}/><Route path="/imports" element={<BringInData/>}/><Route path="/review" element={<ReviewQueue/>}/><Route path="/review/:id" element={<ReviewItem/>}/><Route path="/contracts" element={<Contracts/>}/><Route path="/contracts/:id" element={<Contracts/>}/><Route path="/problems" element={<Problems/>}/><Route path="/reports" element={<Reports/>}/><Route path="/admin" element={<Admin/>}/><Route path="/how-it-works" element={<HowItWorks/>}/></Route><Route path="*" element={<Navigate to="/assets"/>}/></Routes></BrowserRouter>}
createRoot(document.getElementById('root')!).render(<App/>);
