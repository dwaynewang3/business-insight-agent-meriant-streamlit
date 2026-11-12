"""Who sees what: every role except the fraud team lead uses a warehouse copy without
personal data.

The rule is enforced by which file a session connects to, not by checking queries: data that
isn't in the file can't leak, even if a query gets past every other check. The app sets the
role when it starts the warehouse server, so the model can't change it.
"""

from pathlib import Path

ROLES = {
    "head_of_claims": "Head of Claims. Sees all data except personal data.",
    "claims_ops_manager": "Claims operations manager. Sees all data except personal data.",
    "actuarial_analyst": "Actuarial analyst. Sees all data except personal data.",
    "fraud_team_lead": "Fraud team lead. Sees all data, including personal data.",
}
PERSONAL_DATA_ROLES = frozenset({"fraud_team_lead"})


def restricted_path(full_path: str | Path) -> Path:
    """The copy without personal data, written next to the full warehouse by `make data`."""
    full_path = Path(full_path)
    return full_path.with_name(f"{full_path.stem}_restricted{full_path.suffix}")


def warehouse_for(role: str, full_path: str | Path) -> Path:
    if role not in ROLES:
        raise ValueError(f"Unknown role {role!r}. Roles: {', '.join(ROLES)}.")
    return Path(full_path) if role in PERSONAL_DATA_ROLES else restricted_path(full_path)


def sees_personal_data(role: str) -> bool:
    return role in PERSONAL_DATA_ROLES
