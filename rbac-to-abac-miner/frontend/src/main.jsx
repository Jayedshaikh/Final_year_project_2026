import React,{Suspense,lazy} from 'react'
import {createRoot} from 'react-dom/client'
import {BrowserRouter,Routes,Route,Navigate} from 'react-router-dom'
import {WorkflowProvider} from './context/WorkflowContext'
import AppLayout from './layouts/AppLayout'
import {Loading} from './components/UI'
import './index.css'
const UploadPage=lazy(()=>import('./pages/UploadPage'))
const DatasetPage=lazy(()=>import('./pages/DatasetPage'))
const TrainingPage=lazy(()=>import('./pages/TrainingPage'))
const ModelsPage=lazy(()=>import('./pages/ModelsPage'))
const RulesPage=lazy(()=>import('./pages/RulesPage'))
const MetricsPage=lazy(()=>import('./pages/MetricsPage'))
const ReviewPage=lazy(()=>import('./pages/ReviewPage'))
const ExportPage=lazy(()=>import('./pages/ExportPage'))
createRoot(document.getElementById('root')).render(<React.StrictMode><WorkflowProvider><BrowserRouter><Suspense fallback={<Loading/>}><Routes><Route element={<AppLayout/>}><Route path="/" element={<Navigate to="/upload" replace/>}/><Route path="/upload" element={<UploadPage/>}/><Route path="/dataset" element={<DatasetPage/>}/><Route path="/training" element={<TrainingPage/>}/><Route path="/models" element={<ModelsPage/>}/><Route path="/rules" element={<RulesPage/>}/><Route path="/metrics" element={<MetricsPage/>}/><Route path="/review" element={<ReviewPage/>}/><Route path="/export" element={<ExportPage/>}/><Route path="*" element={<Navigate to="/upload" replace/>}/></Route></Routes></Suspense></BrowserRouter></WorkflowProvider></React.StrictMode>)
