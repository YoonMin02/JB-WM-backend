"""SQLModel 테이블 등록 (metadata.create_all 용)."""
from app.models.agent import (
    ActionExecution,
    ActionProposal,
    AgentEvent,
    AgentSession,
    ApprovalDecision,
    Signal,
)
from app.models.customer import Customer
from app.models.finance import Holding, LoanAccount, PortfolioAccount
from app.models.health import HealthEvent, HealthRecord
from app.models.insurance import CoverageItem, InsurancePolicy
from app.models.memory import CustomerMemory

__all__ = [
    "Customer",
    "HealthRecord",
    "HealthEvent",
    "InsurancePolicy",
    "CoverageItem",
    "PortfolioAccount",
    "Holding",
    "LoanAccount",
    "CustomerMemory",
    "AgentSession",
    "Signal",
    "ActionProposal",
    "ApprovalDecision",
    "ActionExecution",
    "AgentEvent",
]
