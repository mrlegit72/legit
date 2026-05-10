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
  python advisor.py --service 3            # skip menu
  python advisor.py --no-save              # don't write transcript
  python advisor.py --no-thinking          # hide summarized reasoning
  python advisor.py --save-dir ~/advice    # custom transcript dir
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import anthropic

MODEL = "claude-opus-4-7"
DEFAULT_SAVE_DIR = Path.home() / "claude-advisor"

DISCLAIMER = """\
This is educational analysis, not personalized investment advice. Numbers and
ETF/ticker recommendations are reasoning, not orders. Verify tax specifics with
a CPA and confirm holdings before trading. You are responsible for your decisions.
"""

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


@dataclass(frozen=True)
class Service:
    title: str
    fields: list[tuple[str, str]]
    template: str


SERVICES: dict[str, Service] = {
    "1": Service(
        title="Portfolio allocation",
        fields=[
            ("age", "Age"),
            ("horizon", "Investment horizon (years until you need this money)"),
            ("risk", "Risk tolerance (conservative / moderate / aggressive)"),
            ("savings", "Current savings to invest ($)"),
            ("monthly", "Monthly contribution ($)"),
            ("holdings", "Existing holdings (list what you currently own)"),
            ("goals", "Goals (retirement / house / passive income / wealth building)"),
        ],
        template="""I want you to build a complete portfolio allocation for me.

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
    ),
    "2": Service(
        title="Portfolio health check",
        fields=[
            ("portfolio", "Your current holdings with amounts (paste them)"),
            ("scenario", "Stress scenario (e.g. 'tech crashes 40%' / 'rates rise 2%' / 'dollar weakens 15%')"),
        ],
        template="""Here are my current holdings with amounts:
{portfolio}

Run a full health check:
- Where am I overconcentrated?
- What sectors am I missing?
- What is my real exposure vs what I think it is?
- What would I lose if {scenario}?
- What should I sell, hold, and buy more of?

Give me specific actions, not general advice.""",
    ),
    "3": Service(
        title="Company deep dive",
        fields=[
            ("ticker", "Company name or ticker"),
        ],
        template="""I want a full due diligence report on {ticker}.

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
    ),
    "4": Service(
        title="Sector comparison",
        fields=[
            ("sector_a", "Sector A"),
            ("sector_b", "Sector B"),
            ("years", "Time horizon (years, e.g. 3-5)"),
        ],
        template="""I'm choosing between investing in {sector_a} vs {sector_b} for the next {years} years.

Compare them across:
- Macro tailwinds and headwinds for each.
- Historical returns in rising vs falling rate environments.
- Valuation multiples now vs 10-year averages.
- Best ETF or index fund for each with expense ratios.
- What scenario makes each the better bet?

Give me a recommendation with logic, not an "it depends".""",
    ),
    "5": Service(
        title="Tax optimization audit",
        fields=[
            ("income", "Annual income ($)"),
            ("bracket", "Federal tax bracket (%)"),
            ("state", "State"),
            ("portfolio_size", "Portfolio size ($)"),
            ("accounts", "Account types you hold (taxable brokerage / 401k / IRA / Roth IRA)"),
            ("st_gains", "Estimated SHORT-term capital gains this year ($)"),
            ("lt_gains", "Estimated LONG-term capital gains this year ($)"),
            ("losses", "Any positions currently at a loss (list them)"),
        ],
        template="""I need a full tax optimization audit for my investment portfolio.

My situation:
- Annual income: ${income}
- Tax bracket: {bracket}% federal
- State: {state}
- Portfolio size: ${portfolio_size}
- Account types I hold: {accounts}
- Estimated capital gains this year: short-term ${st_gains}, long-term ${lt_gains}
- Any positions currently at a loss: {losses}

Tell me:
1. Which accounts should hold which assets for maximum tax efficiency?
2. Are there any positions I should sell before year-end to harvest losses?
3. Should I convert any traditional IRA to Roth this year given my bracket?
4. What is my optimal contribution strategy across account types?
5. What am I likely leaving on the table that most people in my situation miss?""",
    ),
    "6": Service(
        title="Retirement income modeling",
        fields=[
            ("years_to_retirement", "Years from retirement"),
            ("portfolio", "Current portfolio ($)"),
            ("monthly", "Monthly contribution ($)"),
            ("social_security", "Expected Social Security ($/month)"),
            ("target_income", "Target monthly income in retirement ($)"),
            ("seq_risk", "Sequence-of-returns risk tolerance (low / medium)"),
        ],
        template="""I'm {years_to_retirement} years from retirement. I want to model my income.

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

Show the math step by step.""",
    ),
}


def banner() -> None:
    print("\n" + "=" * 64)
    print("  CLAUDE FINANCIAL ADVISOR")
    print("  Replaces the 1% AUM advisor for $20/month")
    print("=" * 64)
    print()
    for line in DISCLAIMER.splitlines():
        print(f"  {line}")
    print()


def menu() -> str | None:
    print("-" * 64)
    for key, svc in SERVICES.items():
        print(f"  {key}. {svc.title}")
    print("  q. Quit")
    while True:
        choice = input("\nPick a service: ").strip().lower()
        if choice == "q":
            return None
        if choice in SERVICES:
            return choice
        print(f"Invalid choice. Pick 1-{len(SERVICES)} or q.")


def collect_inputs(fields: list[tuple[str, str]]) -> dict[str, str]:
    print()
    answers: dict[str, str] = {}
    for key, label in fields:
        value = input(f"  {label}: ").strip()
        answers[key] = value or "(not provided)"
    return answers


def stream_turn(
    client: anthropic.Anthropic,
    messages: list[dict[str, str]],
    show_thinking: bool,
) -> tuple[str, anthropic.types.Usage]:
    """Stream one turn. Print as it arrives. Return (assistant_text, usage)."""
    thinking_param: dict[str, str] = {"type": "adaptive"}
    if show_thinking:
        thinking_param["display"] = "summarized"

    in_thinking = False
    in_text = False

    with client.messages.stream(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        thinking=thinking_param,
        output_config={"effort": "high"},
        messages=messages,
    ) as stream:
        for event in stream:
            if event.type == "content_block_start":
                block_type = event.content_block.type
                if block_type == "thinking" and show_thinking:
                    print("\n[thinking]\n", end="", flush=True)
                    in_thinking = True
                elif block_type == "text":
                    if in_thinking:
                        print("\n", end="", flush=True)
                        in_thinking = False
                    print("[answer]\n" if show_thinking else "", end="", flush=True)
                    in_text = True
            elif event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "thinking_delta" and show_thinking:
                    print(delta.thinking, end="", flush=True)
                elif delta.type == "text_delta":
                    print(delta.text, end="", flush=True)
            elif event.type == "content_block_stop" and in_text:
                in_text = False

        final = stream.get_final_message()

    answer = "".join(b.text for b in final.content if b.type == "text")
    return answer, final.usage


def save_transcript(save_dir: Path, service_title: str, messages: list[dict[str, str]]) -> Path:
    save_dir.mkdir(parents=True, exist_ok=True)
    slug = service_title.lower().replace(" ", "-")
    path = save_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{slug}.md"
    with path.open("w") as f:
        f.write(f"# {service_title}\n\n")
        f.write(f"_Generated {datetime.now():%Y-%m-%d %H:%M}_\n\n")
        for msg in messages:
            role = "You" if msg["role"] == "user" else "Claude"
            f.write(f"## {role}\n\n{msg['content']}\n\n")
    return path


def conversation(
    client: anthropic.Anthropic,
    service: Service,
    initial_prompt: str,
    save_dir: Path | None,
    show_thinking: bool,
) -> None:
    messages: list[dict[str, str]] = [{"role": "user", "content": initial_prompt}]
    print("\n" + "-" * 64)
    print(f"  Running: {service.title}")
    print("-" * 64)

    while True:
        try:
            answer, usage = stream_turn(client, messages, show_thinking)
        except anthropic.APIConnectionError:
            print("\nNetwork error. Check your connection and try again.", file=sys.stderr)
            return
        except anthropic.AuthenticationError:
            print("\nInvalid ANTHROPIC_API_KEY.", file=sys.stderr)
            sys.exit(1)
        except anthropic.RateLimitError:
            print("\nRate limited. Wait a minute and retry.", file=sys.stderr)
            return
        except anthropic.APIStatusError as e:
            print(f"\nAPI error ({e.status_code}): {e.message}", file=sys.stderr)
            return

        messages.append({"role": "assistant", "content": answer})

        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        print(
            f"\n\n  [tokens] in={usage.input_tokens} out={usage.output_tokens}"
            f" cache_read={cache_read}"
        )

        if save_dir is not None:
            path = save_transcript(save_dir, service.title, messages)
            print(f"  [saved] {path}")

        print("\n" + "-" * 64)
        followup = input("Follow-up question (Enter to finish): ").strip()
        if not followup:
            return
        messages.append({"role": "user", "content": followup})


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Claude financial advisor.")
    p.add_argument(
        "--service", "-s",
        choices=list(SERVICES.keys()),
        help="Skip the menu and run this service directly.",
    )
    p.add_argument(
        "--save-dir",
        type=Path,
        default=DEFAULT_SAVE_DIR,
        help=f"Where to save transcripts (default: {DEFAULT_SAVE_DIR}).",
    )
    p.add_argument(
        "--no-save",
        action="store_true",
        help="Don't write transcripts to disk.",
    )
    p.add_argument(
        "--no-thinking",
        action="store_true",
        help="Don't show Claude's summarized reasoning.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("error: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        print("  export ANTHROPIC_API_KEY=sk-ant-...", file=sys.stderr)
        return 1

    save_dir = None if args.no_save else args.save_dir
    show_thinking = not args.no_thinking

    banner()
    client = anthropic.Anthropic()

    try:
        while True:
            choice = args.service or menu()
            if choice is None:
                return 0
            service = SERVICES[choice]
            print(f"\n>>> {service.title}")
            print("    Answer the prompts below. Press Enter to skip a field.")
            answers = collect_inputs(service.fields)
            prompt = service.template.format(**answers)
            conversation(client, service, prompt, save_dir, show_thinking)
            if args.service:
                return 0  # one-shot mode: exit after a single service
    except (KeyboardInterrupt, EOFError):
        print("\n\n[exited]")
        return 0


if __name__ == "__main__":
    sys.exit(main())
