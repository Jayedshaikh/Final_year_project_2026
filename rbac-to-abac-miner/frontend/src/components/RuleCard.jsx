import {percent,title} from '../utils/formatRule'
import {Status} from './UI'

const STATUS_TONE_MAP = {
  candidate: 'grey',
  optimised: 'blue',
  approved: 'green',
  rejected: 'red',
  edited: 'amber'
}

export default function RuleCard({rule,footer}) {
  const tone = STATUS_TONE_MAP[rule.status] || 'neutral'
  return <article className="rule-card"><div className="rule-top"><div className="rule-identity"><span className="rule-id">{rule.rule_id}</span><Status tone={tone}>{title(rule.status)}</Status></div><span className="rule-source">{title(rule.source)}</span></div><div className="rule-statement"><span className="permit-word">PERMIT</span> <strong>{rule.action}</strong> <span className="muted">IF</span></div><div className="conditions">{rule.conditions.map((c,i)=><div className="condition" key={i}><span>{c.attribute}</span><b>{c.operator}</b><strong>{Array.isArray(c.value)?`[${c.value.join(', ')}]`:String(c.value)}</strong></div>)}</div><div className="rule-foot"><div><small>SUPPORT</small><strong>{percent(rule.support)}</strong></div><div><small>CONFIDENCE</small><strong>{percent(rule.confidence)}</strong></div><div><small>COVERAGE</small><strong>{rule.n_covered_positive} positive · {rule.n_covered_negative} negative</strong></div></div>{footer&&<div className="rule-actions">{footer}</div>}</article>}
