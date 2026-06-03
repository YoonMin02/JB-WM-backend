"""SQLModel 테이블 등록 (metadata.create_all 용)."""
from app.models.agent import (
    ActionExecution,
    ActionProposal,
    AgentEvent,
    AgentMessage,
    AgentSession,
    ApprovalDecision,
    NeedAssessmentRecord,
    PlanRecord,
    Signal,
)
from app.models.customer import Customer
from app.models.finance import (
    AccountBalance,
    AccountTransaction,
    AssetEvent,
    CardBill,
    Holding,
    LoanAccount,
    LoanSwitchPrecheck,
    PortfolioAccount,
)
from app.models.health import HealthEvent, HealthRecord, MedicalDocument
from app.models.insurance import CoverageItem, InsurancePolicy
from app.models.memory import CustomerMemory
from app.models.privacy import ConsentRecord
from app.models.stats import PopulationStat

__all__ = [
    "Customer",
    "HealthRecord",
    "HealthEvent",
    "MedicalDocument",
    "InsurancePolicy",
    "CoverageItem",
    "PortfolioAccount",
    "Holding",
    "LoanAccount",
    "AccountBalance",
    "AccountTransaction",
    "CardBill",
    "LoanSwitchPrecheck",
    "AssetEvent",
    "CustomerMemory",
    "ConsentRecord",
    "PopulationStat",
    "AgentSession",
    "Signal",
    "ActionProposal",
    "ApprovalDecision",
    "ActionExecution",
    "AgentEvent",
    "AgentMessage",
    "NeedAssessmentRecord",
    "PlanRecord",
]
