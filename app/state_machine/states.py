"""FSM 상태 정의 + 전이 규칙. (docs/03_STATE_MACHINE.md)"""
from __future__ import annotations

from enum import StrEnum


class State(StrEnum):
    MONITORING = "Monitoring"
    SIGNAL_DETECTED = "SignalDetected"
    INTENT_UNKNOWN = "IntentUnknown"
    CLARIFY_USER = "ClarifyUser"
    HEALTHCARE_INTENT = "HealthCareIntent"
    INSURANCE_INTENT = "InsuranceIntent"
    ASSET_DEFENSE_INTENT = "AssetDefenseIntent"
    INVESTMENT_ADJUST_INTENT = "InvestmentAdjustIntent"
    LIFE_PLAN_INTENT = "LifePlanIntent"
    GENERATE_PLAN = "GeneratePlan"
    RISK_CHECK = "RiskCheck"
    AUTO_EXECUTABLE = "AutoExecutable"
    NEED_APPROVAL = "NeedApproval"
    USER_APPROVAL = "UserApproval"
    REVISE_PLAN = "RevisePlan"
    EXECUTE_ACTION = "ExecuteAction"
    VERIFY_RESULT = "VerifyResult"
    PREFERENCE_UPDATE = "PreferenceUpdate"
    UPDATE_MEMORY = "UpdateMemory"
    NO_ACTION = "NoAction"
    FAILED = "Failed"


INTENT_STATES = {
    State.HEALTHCARE_INTENT,
    State.INSURANCE_INTENT,
    State.ASSET_DEFENSE_INTENT,
    State.INVESTMENT_ADJUST_INTENT,
    State.LIFE_PLAN_INTENT,
}

# 허용 전이: from -> {to, ...}
TRANSITIONS: dict[State, set[State]] = {
    State.MONITORING: {State.SIGNAL_DETECTED},
    State.SIGNAL_DETECTED: {State.INTENT_UNKNOWN, *INTENT_STATES},
    State.INTENT_UNKNOWN: {State.CLARIFY_USER},
    State.CLARIFY_USER: {*INTENT_STATES, State.PREFERENCE_UPDATE, State.NO_ACTION},
    State.HEALTHCARE_INTENT: {State.GENERATE_PLAN},
    State.INSURANCE_INTENT: {State.GENERATE_PLAN},
    State.ASSET_DEFENSE_INTENT: {State.GENERATE_PLAN},
    State.INVESTMENT_ADJUST_INTENT: {State.GENERATE_PLAN},
    State.LIFE_PLAN_INTENT: {State.GENERATE_PLAN},
    State.GENERATE_PLAN: {State.RISK_CHECK},
    State.RISK_CHECK: {State.AUTO_EXECUTABLE, State.NEED_APPROVAL},
    State.AUTO_EXECUTABLE: {State.EXECUTE_ACTION},
    State.NEED_APPROVAL: {State.USER_APPROVAL},
    State.USER_APPROVAL: {State.EXECUTE_ACTION, State.REVISE_PLAN, State.NO_ACTION},
    State.REVISE_PLAN: {State.GENERATE_PLAN},
    State.EXECUTE_ACTION: {State.VERIFY_RESULT, State.FAILED},
    State.VERIFY_RESULT: {State.UPDATE_MEMORY},
    State.PREFERENCE_UPDATE: {State.UPDATE_MEMORY},
    State.NO_ACTION: {State.UPDATE_MEMORY},
    State.FAILED: {State.UPDATE_MEMORY},
    State.UPDATE_MEMORY: {State.MONITORING},
}

# 고객이 취할 수 있는 행동 (API allowed_actions)
USER_ACTIONS: dict[State, list[str]] = {
    State.USER_APPROVAL: ["approve", "reject", "revise"],
    State.CLARIFY_USER: ["answer"],
}


def allowed_actions(state: State) -> list[str]:
    return USER_ACTIONS.get(state, [])
