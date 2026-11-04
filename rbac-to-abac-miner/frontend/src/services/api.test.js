import {describe,it,expect} from 'vitest'
import {isMockMode,getRules} from './api'
describe('API adapter',()=>{
  it('uses unchanged mock contract data by default in the local build',async()=>{
    expect(isMockMode).toBe(true)
    const response=await getRules('run_001')
    expect(response.status).toBe('ok')
    expect(response.rules[0].rule_id).toBe('R001')
  })
})
