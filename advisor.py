#!/usr/bin/env python3
"""
Personal financial advisor powered by Claude.

Replaces the 1% AUM advisor with a $20/month tool that does:
  1. Portfolio allocation
  2. Portfolio health check
  3. Company deep dive
  4. Sector comparison
  5. Tax optimization audit
  6. Retirement income modeling

Usage:
  export ANTHROPIC_API_KEY=sk-ant-...
  python advisor.py
"""

from __future__ import annotations

import os
import sys
import textwrap

import anthropic

MODEL = "claude-opus-4-7"

SYSTEM_PROMPT = """You are a rigorous, fee-only financial advisor. You answer the
user's questions the way a CFP/CFA fiduciary would: cite specific reasoning, show
your work, flag what would cost them money, and never recommend products you
have a financial incentive to push (you have none).

Ground rules for every response:
- Show the math step by step when numbers are involved.
- Be specific: name actual ETFs, tickers, account types, and percentages.
- Call out conflicts of interest a commission-based advisor would have.
- Compare your recommendation to the standard 60/40 model and explain deltas.
- Flag tax inefficiencies and concentration risk explicitly.
- End with a prioritized action list ("do this first, then this").
- This is educational analysis, not personalized investment advice. The user is
  responsible for their own decisions and should verify tax specifics with a CPA.
"""

PROMPTS: dict[str, dict[str, object]] = {
    "1": {
        "title": "Portfolio allocation",
        "fields": [
            ("age", "Age"),
            ("horizon", "Investment horizon (years until you need this money)"),
            ("risk", "Risk tolerance (conservative / moderate / aggressive)"),
            ("savings", "Current savings to invest ($)"),
            ("monthly", "Monthly contribution ($)"),
            ("holdings", "Existing holdings (list what you currently own)"),
            ("goals", "Goals (retirement / house / passive income / wealth building)"),
        ],
        "template": """I want you to build a complete portfolio allocation for me.

My profile:
- Age: {age}
- Investment horizon: {horizon}
- Risk tolerance: {risk}
- Current savings to invest: ${savings}
- Monthly contribution: ${monthly}
- Existing holdings: {holdings}
- Goals: {goals}

Build me:
1. An allocation model with exact percentages across asset classes (equities, bonds, real estate, commodities, crypto if relevant).
2. Specific instruments for each allocation (ETFs, index funds, asset types) with tickers and expense ratios.
3. Rebalancing schedule and triggers.
4. What to prioritize buying first given my current holdings.
5. The logic behind every decision.

Then flag: what would a traditional 60/40 advisor put me in vs what you recommend, and why.""",
    },
    "2": {
        "title": "Portfolio health check",
        "fields": [
            ("portfolio", "Your current holdings with amounts (paste them)"),
            ("scenario", "Stress scenario (e.g. 'tech crashes 40%' / 'rates rise 2%' / 'dollar weakens 15%')"),
        ],
        "template": """Here are my current holdings with amounts:
{portfolio}

Run a full health check:
- Where am I overconcentrated?
- What sectors am I missing?
- What is my real exposure vs what I think it is?
- What would I lose if {scenario}?
- What should I sell, hold, and buy more of?

Give me specific actions, not general advice.""",
    },
    "3": {
        "title": "Company deep dive",
        "fields": [
            ("ticker", "Company name or ticker"),
        ],
        "template": """I want a full due diligence report on {ticker}.

Cover:
1. Business model: how does it actually make money?
2. Revenue quality: recurring vs one-time, concentration risk.
3. Financials: revenue growth (3yr), margins trend, debt/equity, free cash flow.
4. Competitive moat: what stops competitors from taking market share?
5. Key risks: what are the 3 most realistic ways this investment loses money?
6. Valuation: P/E, P/S, EV/EBITDA vs sector average. Cheap or expensive?
7. Insider activity: any recent significant buys or sells by executives?
8. Verdict: would you buy, hold, or avoid this at current price and why?

Compare it to its 2 main competitors using the same framework.""",
    },
    "4": {
        "title": "Sector comparison",
        "fields": [
            ("sector_a", "Sector A"),
            ("sector_b", "Sector B"),
            ("years", "Time horizon (years, e.g. 3-5)"),
        ],
        "template": """I'm choosing between investing in {sector_a} vs {sector_b} for the next {years} years.

Compare them across:
- Macro tailwinds and headwinds for each.
- Historical returns in rising vs falling rate environments.
- Valuation multiples now vs 10-year averages.
- Best ETF or index fund for each with expense ratios.
- What scenario makes each the better bet?

Give me a recommendation with logic, not a "it depends.""",
    },
    "5": {
        "title": "Tax optimization audit",
        "fields": [
            ("income", "Annual income ($)"),
            ("bracket", "Federal tax bracket (%)"),
            ("state", "State"),
            ("portfolio_size", "Portfolio size ($)"),
            ("accounts", "Account types you hold (taxable brokerage / 401k / IRA / Roth IRA)"),
            ("gains", "Estimated capital gains this year ($) — break out short-term vs long-term"),
            ("losses", "Any positions currently at a loss (list them)"),
        ],
        "template": """I need a full tax optimization audit for my investment portfolio.

My situation:
- Annual income: ${income}
- Tax bracket: {bracket}% federal
- State: {state}
- Portfolio size: ${portfolio_size}
- Account types I hold: {accounts}
- Estimated capital gains this year: {gains}
- Any positions currently at a loss: {losses}

Tell me:
1. Which accounts should hold which assets for maximum tax efficiency?
2. Are there any positions I should sell before year-end to harvest losses?
3. Should I convert any traditional IRA to Roth this year given my bracket?
4. What is my optimal contribution strategy across account types?
5. What am I likely leaving on the table that most people in my situation miss?""",
    },
    "6": {
        "title": "Retirement income modeling",
        "fields": [
            ("years_to_retirement", "Years from retirement"),
            ("portfolio", "Current portfolio ($)"),
            ("monthly", "Monthly contribution ($)"),
            ("social_security", "Expected Social Security ($/month)"),
            ("target_income", "Target monthly income in retirement ($)"),
            ("seq_risk", "Sequence-of-returns risk tolerance (low / medium)"),
        ],
        "template": """I'm {years_to_retirement} years from retirement. I want to model my income.

My situation:
- Current portfolio: ${portfolio}
- Monthly contribution: ${monthly}
- Expected Social Security: ${social_security}/month
- Target monthly income in retirement: ${target_income}
- Risk I'm willing to take on sequence-of-returns: {seq_risk}

Build me:
1. Projected portfolio value at retirement under conservative (5%), moderate (7%), and optimistic (9%) scenarios.
2. Safe withdrawal rate for each scenario.
3. What gap exists between my projected income and my target.
4. What I need to change NOW to close that gap.
5. A Roth conversion strategy if it applies.

Show the math step by step.""",
    },
}


def menu() -> str:
    print("\n" + "=" * 60)
    print("  CLAUDE FINANCIAL ADVISOR")
    print("  Replaces the 1% AUM advisor for $20/month")
    print("=" * 60)
    for key, p in PROMPTS.items():
        print(f"  {key}. {p['title']}")
    print("  q. Quit")
    while True:
        choice = input("\nPick a service: ").strip().lower()
        if choice == "q":
            sys.exit(0)
        if choice in PROMPTS:
            return choice
        print(f"Invalid choice. Pick 1-{len(PROMPTS)} or q.")


def collect_inputs(fields: list[tuple[str, str]]) -> dict[str, str]:
    print()
    answers: dict[str, str] = {}
    for key, label in fields:
        value = input(f"{label}: ").strip()
        answers[key] = value or "(not provided)"
    return answers


def run(prompt: str) -> None:
    client = anthropic.Anthropic()
    print("\n" + "-" * 60)
    print("  Claude is thinking and responding...")
    print("-" * 60 + "\n")

    with client.messages.stream(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for event in stream:
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                print(event.delta.text, end="", flush=True)

        final = stream.get_final_message()

    usage = final.usage
    print("\n\n" + "-" * 60)
    print(
        f"  Tokens — input: {usage.input_tokens}  output: {usage.output_tokens}"
        f"  cache_read: {getattr(usage, 'cache_read_input_tokens', 0)}"
    )
    print("-" * 60)


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("error: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        print("  export ANTHROPIC_API_KEY=sk-ant-...", file=sys.stderr)
        sys.exit(1)

    while True:
        choice = menu()
        spec = PROMPTS[choice]
        print(f"\n>>> {spec['title']}")
        print(textwrap.fill(
            "Answer the prompts below. Press Enter to skip a field "
            "(Claude will note it as not provided).",
            width=60,
        ))
        answers = collect_inputs(spec["fields"])  # type: ignore[arg-type]
        prompt = spec["template"].format(**answers)  # type: ignore[union-attr]
        try:
            run(prompt)
        except anthropic.APIStatusError as e:
            print(f"\nAPI error ({e.status_code}): {e.message}", file=sys.stderr)
        except KeyboardInterrupt:
            print("\n\n[interrupted]")


if __name__ == "__main__":
    main()
