import { AgentDecision } from "../api/client";

export function decisionGuardWarnings(decision: AgentDecision): string[] {
  const warnings = decision.agent_response_json.response_guard_warnings;
  if (!Array.isArray(warnings)) return [];
  return warnings.filter((warning): warning is string => typeof warning === "string" && warning.trim().length > 0);
}

export function decisionBlockReason(decision: AgentDecision): string {
  const guardWarnings = decisionGuardWarnings(decision);
  if (guardWarnings.length) return `응답 가드 차단: ${guardWarnings[0]}`;
  return decision.rejection_reason ?? "";
}
