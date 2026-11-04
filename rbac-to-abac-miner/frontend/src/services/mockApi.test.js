import {describe,it,expect} from 'vitest'
import {uploadDataset,submitReview,exportPolicy} from './mockApi'
describe('mock contract safeguards',()=>{
  it('returns a fresh contract fixture and supports invalid upload preview',async()=>{const form=new FormData();form.append('mock_invalid','true');const invalid=await uploadDataset(form);expect(invalid.status).toBe('invalid');expect(invalid.issues[0].severity).toBe('error')})
  it('refuses review choices not represented by the fixed approval fixture',async()=>{await expect(submitReview({decisions:[{rule_id:'R001',decision:'approve'}]})).rejects.toThrow('fixed demo response')})
  it('blocks unsafe candidate export in upstream fixture',async()=>{await expect(exportPolicy({format:'json',policy_id:'pol_001'})).rejects.toThrow('candidate rule')})
  it('does not fabricate an XACML fixture',async()=>{await expect(exportPolicy({format:'xacml',policy_id:'pol_001'})).rejects.toThrow('XACML mock')})
})
