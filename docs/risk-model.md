# Risk Model

Every Chronos proposal receives a risk class.

| Level | Meaning | Default Policy |
|---|---|---|
| L0 | Read-only summary | May run automatically |
| L1 | Draft or recommendation only | Scheduled output requires review |
| L2 | Internal write action | Activation requires approval |
| L3 | External communication | Every external action requires approval |
| L4 | Financial, legal, healthcare, employment, or regulated action | Human-in-the-loop always |
| L5 | Destructive, irreversible, or permission-expanding action | Forbidden by default |

## Rule of Thumb

If a proposal can affect another person, money, legal position, clinical care, employment, security, permissions, or irreversible state, it must not be treated as autonomous.

## Review-Day Boundary

`review-day` only proposes. It never acts. Even L0 proposals are emitted as a plan rather than installed.

## Agent Compatibility

A proposal cannot be matched to an agent whose `max_risk_class` is below the proposal risk class. If the agent otherwise fits, Chronos may report a partial match and explain the risk mismatch.
