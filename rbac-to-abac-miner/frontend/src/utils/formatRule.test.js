import {describe,it,expect} from 'vitest'
import {formatRule,percent,buildApprovalRequest} from './formatRule'
describe('formatRule',()=>{
  it('renders contract conditions and array values without changing operators',()=>{expect(formatRule({effect:'permit',action:'read',conditions:[{attribute:'user.department',operator:'==',value:'Finance'},{attribute:'resource.sensitivity',operator:'in',value:['low','medium']}]})).toBe('PERMIT read IF user.department == Finance AND resource.sensitivity in [low, medium]')})
  it('formats null metrics without inventing a number',()=>expect(percent(null)).toBe('—'))
})
describe('buildApprovalRequest',()=>{
  it('includes explicit decisions only and preserves edited conditions',()=>{const edited=[{attribute:'user.seniority',operator:'>=',value:4}];expect(buildApprovalRequest('pol_001',' Alex ',{R001:{decision:'approve'},R002:{decision:'edit',edited_conditions:edited,comment:' Review again '},R003:null})).toEqual({policy_id:'pol_001',reviewer:'Alex',decisions:[{rule_id:'R001',decision:'approve',edited_conditions:null,comment:null},{rule_id:'R002',decision:'edit',edited_conditions:edited,comment:'Review again'}]})})
})
