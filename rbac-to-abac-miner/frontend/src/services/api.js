import * as mock from './mockApi'
const mocks = import.meta.env.VITE_USE_MOCKS !== 'false'
const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
async function request(path, options = {}) {
  let response
  try { response = await fetch(`${base}${path}`, options) } catch { throw new Error('Cannot reach the API. Check the backend connection and try again.') }
  const data = await response.json().catch(() => null)
  if (!response.ok || data?.status === 'error') throw new Error(data?.message || `Request failed (${response.status})`)
  return data
}
const json = (body) => ({ method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) })
export const isMockMode = mocks
export const uploadDataset = (form) => mocks ? mock.uploadDataset(form) : request('/datasets/upload', {method:'POST',body:form})
export const getAuthorisation = (id) => mocks ? mock.getAuthorisation(id) : request(`/datasets/${encodeURIComponent(id)}/authorisation`)
export const runTraining = (config) => mocks ? mock.runTraining(config) : request('/training/run',json(config))
export const getComparison = (id) => mocks ? mock.getComparison(id) : request(`/training/${encodeURIComponent(id)}/comparison`)
export const getRules = (id) => mocks ? mock.getRules(id) : request(`/training/${encodeURIComponent(id)}/rules`)
export const optimisePolicy = (id) => mocks ? mock.optimisePolicy(id) : request(`/policies/optimise/${encodeURIComponent(id)}`, {method:'POST'})
export const getValidation = (id) => mocks ? mock.getValidation(id) : request(`/policies/${encodeURIComponent(id)}/validation`)
export const submitReview = (body) => mocks ? mock.submitReview(body) : request(`/policies/${encodeURIComponent(body.policy_id)}/review`,json(body))
export const exportPolicy = (body) => mocks ? mock.exportPolicy(body) : request(`/policies/${encodeURIComponent(body.policy_id)}/export`,json(body))
