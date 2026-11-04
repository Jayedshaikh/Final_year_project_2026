import {createContext,useContext,useState} from 'react'
const Context = createContext(null)
export function WorkflowProvider({children}) {
  const [state,setState] = useState({dataset:null,auth:null,training:null,comparison:null,extracted:null,policy:null,validation:null,approval:null,exported:null})
  const set = (key,value) => setState(previous => ({...previous,[key]:value}))
  const resetFromDataset = dataset => setState({dataset,auth:null,training:null,comparison:null,extracted:null,policy:null,validation:null,approval:null,exported:null})
  const resetFromTraining = training => setState(previous => ({...previous,training,comparison:null,extracted:null,policy:null,validation:null,approval:null,exported:null}))
  return <Context.Provider value={{...state,set,resetFromDataset,resetFromTraining}}>{children}</Context.Provider>
}
export const useWorkflow = () => useContext(Context)
