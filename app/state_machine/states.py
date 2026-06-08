"""FSM 상태 정의 + 전이 규칙. (docs/03_STATE_MACHINE.md)"""
from __future__ import annotations

from enum import StrEnum


class State(StrEnum):
    MONITORING = "Monitoring"
    SIGNAL_DETECTED = "SignalDetected"
    ASSESS_NEED = "AssessNeed"
    CLARIFY_USER = "ClarifyUser"
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


# 허용 전이: from -> {to, ...}
TRANSITIONS: dict[State, set[State]] = {
    State.MONITORING: {State.SIGNAL_DETECTED},
    State.SIGNAL_DETECTED: {State.ASSESS_NEED, State.FAILED},
    State.ASSESS_NEED: {State.CLARIFY_USER, State.PREFERENCE_UPDATE, State.NO_ACTION, State.GENERATE_PLAN, State.FAILED},
    State.CLARIFY_USER: {State.ASSESS_NEED, State.PREFERENCE_UPDATE, State.NO_ACTION, State.FAILED},
    State.GENERATE_PLAN: {State.RISK_CHECK, State.FAILED},
    State.RISK_CHECK: {State.AUTO_EXECUTABLE, State.NEED_APPROVAL, State.FAILED},
    State.AUTO_EXECUTABLE: {State.EXECUTE_ACTION},
    State.NEED_APPROVAL: {State.USER_APPROVAL},
    State.USER_APPROVAL: {State.EXECUTE_ACTION, State.REVISE_PLAN, State.NO_ACTION},
    State.REVISE_PLAN: {State.GENERATE_PLAN},
    State.EXECUTE_ACTION: {State.VERIFY_RESULT, State.FAILED},
    State.VERIFY_RESULT: {State.UPDATE_MEMORY, State.NEED_APPROVAL},
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
