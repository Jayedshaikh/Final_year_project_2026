export const formatValue = value => Array.isArray(value) ? `[${value.join(', ')}]` : String(value)
export const formatRule = rule => `${rule.effect.toUpperCase()} ${rule.action} IF ${rule.conditions.map(c => `${c.attribute} ${c.operator} ${formatValue(c.value)}`).join(' AND ')}`
export const percent = (value, decimals = 1) => value == null ? '—' : `${(value * 100).toFixed(decimals)}%`
export const title = value => String(value || '').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase())
export function buildApprovalRequest(policy_id, reviewer, decisions) {
  return {policy_id, reviewer: reviewer.trim(), decisions: Object.entries(decisions).filter(([,v]) => v?.decision).map(([rule_id, v]) => ({rule_id, decision:v.decision, edited_conditions:v.decision === 'edit' ? v.edited_conditions : null, comment:v.comment?.trim() || null}))}
}
