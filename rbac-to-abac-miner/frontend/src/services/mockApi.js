import ok from './mocks/dataset_validation_ok.json'
import invalid from './mocks/dataset_validation_invalid.json'
import auth from './mocks/rbac_authorisation.json'
import training from './mocks/training_response.json'
import comparison from './mocks/model_comparison.json'
import rules from './mocks/extracted_rules.json'
import optimised from './mocks/optimised_policy.json'
import validation from './mocks/policy_validation.json'
import approval from './mocks/approval_response.json'
import exported from './mocks/export_response.json'
import errorFixture from './mocks/error_response.json'
const delay = (data) => new Promise((resolve,reject) => {
  const ms = 300 + Math.random() * 300 // 300-600ms random delay as per spec
  setTimeout(() => {
    if (typeof window !== 'undefined' && new URLSearchParams(window.location.search).has('mock_error')) reject(new Error(errorFixture.message))
    else resolve(structuredClone(data))
  }, ms)
})
export const uploadDataset = (form) => delay(form.get('mock_invalid') === 'true' ? invalid : ok)
export const getAuthorisation = () => delay(auth)
export const runTraining = () => delay(training)
export const getComparison = () => delay(comparison)
export const getRules = () => delay(rules)
export const optimisePolicy = () => delay(optimised)
export const getValidation = () => delay(validation)
export const submitReview = (request) => {
  const a = request.decisions.find(d => d.rule_id === 'R001')
  const b = request.decisions.find(d => d.rule_id === 'R002')
  if (request.decisions.length !== 2 || a?.decision !== 'approve' || b?.decision !== 'reject') return Promise.reject(new Error('This fixed demo response covers R001 approved and R002 rejected only. Connect the backend for other review decisions.'))
  return delay(approval)
}
// The shipped JSON sample is for JSON only. Never fabricate an XACML document in the browser.
export const exportPolicy = (request) => {
  if (request.format !== 'json') return Promise.reject(new Error('The XACML mock is not available. Connect the backend to generate XACML.'))
  // The upstream JSON sample says n_rules_exported=1, but its rule has status=candidate.
  // Refuse this unsafe sample instead of presenting an unapproved rule as an export.
  const rules = JSON.parse(exported.content).rules || []
  if (rules.some(rule => rule.status !== 'approved')) return Promise.reject(new Error('The repository export sample contains a candidate rule, not an approved rule. Export is blocked in demo mode; ask the policy/backend owners for a corrected sample or connect the live API.'))
  return delay(exported)
}
