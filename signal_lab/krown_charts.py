"""Render a completed Krown study without rerunning extraction or a backtest.

Matplotlib is optional and imported only by ``render_study_charts``. Inputs are
the runner's JSON-compatible study and frozen source manifest. Returned names
are relative to the requested output directory; each chart has PNG and SVG
versions. The renderer neither reads captions nor downloads or calculates prices.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta, timezone
import math
from pathlib import Path
import textwrap
from typing import Any

from .models import utc


INITIAL_EQUITY = 10_000.0
INK = "#20334A"
MUTED = "#637287"
GRID = "#E3E9EF"
BACKGROUND = "#FBFCFE"
BLUE = "#2869A9"
TEAL = "#07878D"
ORANGE = "#C37532"
GRAY = "#A7B1BE"
SPLIT_COLORS = {"development": TEAL, "holdout": BLUE}
EXTRACTOR_NAMES = {"lexical": "Keyword counts", "context_strict": "Strict context",
                   "context_standard": "Standard context", "context_broad": "Broad context"}
STYLE = {"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
         "axes.labelcolor": INK, "axes.edgecolor": GRID, "axes.titlecolor": INK,
         "axes.spines.top": False, "axes.spines.right": False, "axes.facecolor": "white",
         "figure.facecolor": BACKGROUND, "xtick.color": MUTED, "ytick.color": MUTED,
         "grid.color": GRID, "grid.linewidth": 0.7, "legend.frameon": False,
         "svg.fonttype": "none", "svg.hashsalt": "krown-study-v1", "timezone": "UTC"}


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _label(row: dict) -> str:
    if row.get("label"):
        return str(row["label"])
    name = EXTRACTOR_NAMES.get(str(row.get("extractor", "")), str(row.get("extractor", row["variant"])).replace("_", " "))
    holding = row.get("holding_hours")
    label = f"{name}, {holding}-hour hold" if holding is not None else name
    return label + (", breakout confirmation" if row.get("confirmation") == "breakout" else "")


def _strategy_rows(study: dict, split: str, cost: str = "base") -> list[dict]:
    rows = [row for row in study.get("rows", []) if row.get("split") == split and row.get("cost") == cost]
    if len({row["variant"] for row in rows}) != len(rows):
        raise ValueError(f"Duplicate strategy rows for {split}/{cost}")
    return rows


def _run(study: dict, row: dict) -> dict:
    try:
        return study["runs"][row["run_id"]]
    except KeyError as exc:
        raise ValueError(f"Missing backtest result for {row.get('run_id')}") from exc


def _summary(result: dict) -> dict:
    summary = result["summary"]
    initial = _number(summary["initial_equity"], "initial_equity")
    if not math.isclose(initial, INITIAL_EQUITY, rel_tol=0, abs_tol=0.000001):
        raise ValueError("Krown charts require the frozen 10,000 USDT initial equity")
    return summary


def _curve(result: dict) -> tuple[list, list[float]]:
    _summary(result)
    points = result.get("equity", [])
    if not points:
        raise ValueError("A charted run has no equity observations")
    dates = [utc(point["time"]) for point in points]
    values = [_number(point["equity"], "equity") for point in points]
    if any(a > b for a, b in zip(dates, dates[1:])):
        raise ValueError("Equity observations must be in chronological order")
    return dates, values


def _controls(study: dict, rows: list[dict]) -> dict[str, dict]:
    """Deduplicate controls by rule, not by their source strategy's name."""
    controls: dict[str, dict] = {}
    for row in rows:
        result = _run(study, row)
        benchmarks = result.get("benchmarks", {})
        holding = int(row.get("holding_hours", result.get("config", {}).get("holding_hours", 24)))
        for key, label in (("buy_and_hold", "Buy and hold"),
                           ("price_only_momentum", f"Price-only momentum, {holding}-hour hold")):
            if key not in benchmarks:
                raise ValueError(f"Missing {key} control for {row['run_id']}")
            control = benchmarks[key]
            if label in controls:
                # The experiment uses identical source clocks. A mismatch must
                # be investigated instead of concealing a distinct control.
                if _curve(controls[label]) != _curve(control):
                    raise ValueError(f"Cannot deduplicate unequal control curves: {label}")
            else:
                controls[label] = control
    return controls


def _heading(fig: Any, title: str, subtitle: str) -> None:
    fig.text(0.055, 0.965, title, fontsize=20, fontweight="bold", va="top")
    fig.text(0.055, 0.923, subtitle, fontsize=10.5, color=MUTED, va="top")


def _footer(fig: Any, lines: list[str], *, bottom: float = 0.025) -> None:
    fig.text(0.055, bottom, "\n".join(lines), fontsize=8.5, color=MUTED, va="bottom", linespacing=1.5)


def _date_axis(ax: Any, dates: Any) -> None:
    locator = dates.AutoDateLocator(minticks=4, maxticks=7, interval_multiples=False, tz=timezone.utc)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(dates.DateFormatter("%d %b", tz=timezone.utc))
    ax.grid(axis="both", alpha=0.65)
    ax.set_axisbelow(True)


def _timeline(plt: Any, dates: Any, sources: dict) -> Any:
    entries = [row for row in sources.get("entries", []) if row.get("split") in SPLIT_COLORS]
    if not entries:
        raise ValueError("The frozen source manifest has no development or holdout entries")
    if len({row["source_id"] for row in entries}) != len(entries):
        raise ValueError("Duplicate source IDs in the frozen manifest")
    fig, ax = plt.subplots(figsize=(14, 5.8))
    fig.subplots_adjust(left=0.17, right=0.96, top=0.76, bottom=0.22)
    times = [utc(row["published_at"]) for row in entries]
    years = str(min(times).year) if min(times).year == max(times).year else f"{min(times).year}–{max(times).year}"
    _heading(fig, "The frozen source cohort", f"{len(entries)} original-channel sources · {years} publication dates in UTC")
    content_types = [("normal_video", "Normal analysis", 1, "o"),
                     ("completed_livestream", "Completed stream", 0, "D")]
    for split, color in SPLIT_COLORS.items():
        cohort = [row for row in entries if row["split"] == split]
        if not cohort:
            continue
        span = [utc(row["published_at"]) for row in cohort]
        start, end = min(span), max(span)
        ax.axvspan(start - timedelta(hours=8), end + timedelta(hours=8), color=color, alpha=0.065)
        ax.text(start + (end - start) / 2, 1.53, f"{split.title()} · {len(cohort)} sources",
                ha="center", fontsize=11, color=color, fontweight="bold")
        for kind, _, y, marker in content_types:
            selected = [utc(row["published_at"]) for row in cohort if row["content_type"] == kind]
            ax.scatter(selected, [y] * len(selected), marker=marker, s=64, color=color,
                       edgecolor="white", linewidth=0.8, zorder=3)
    counts = Counter(row["content_type"] for row in entries)
    ax.set_yticks([item[2] for item in content_types],
                 [f"{item[1]}\n{counts[item[0]]} sources" for item in content_types])
    ax.set_ylim(-0.65, 1.85)
    ax.set_xlim(min(times) - timedelta(days=2), max(times) + timedelta(days=3))
    ax.tick_params(axis="y", length=0, pad=12)
    _date_axis(ax, dates)
    ax.set_xlabel("Source publication date (UTC)", labelpad=10)
    _footer(fig, ["Source IDs and periods were frozen before holdout evaluation; the plot shows the selected sample, not every channel upload.",
                  "Publication is distinct from reconstructed research availability and from the actual caption retrieval time."])
    return fig


def _coverage(plt: Any, study: dict) -> Any:
    lookup = {(row["split"], row["extractor"]): row for row in study.get("coverage", [])}
    strategies = _strategy_rows(study, "holdout") or _strategy_rows(study, "development")
    if not strategies:
        raise ValueError("The study has no base-cost strategy rows")
    labels = [textwrap.fill(_label(row), 34) for row in strategies]
    fig, axes = plt.subplots(1, 2, figsize=(15, max(6.9, 2.5 + 0.65 * len(labels))), sharey=True)
    fig.subplots_adjust(left=0.24, right=0.96, top=0.79, bottom=0.23, wspace=0.13)
    _heading(fig, "Extracted direction and abstention", "Video-level direction before holding periods or price confirmation are applied")
    for ax, split in zip(axes, ("development", "holdout")):
        for index, strategy in enumerate(strategies):
            record = lookup.get((split, strategy["extractor"]))
            if record is None:
                ax.text(50, index, "Coverage unavailable", ha="center", va="center", color=MUTED)
                continue
            counts = [_number(record[key], key) for key in ("long", "short", "flat")]
            total = _number(record["videos"], "videos")
            if total < 0 or any(count < 0 or count != int(count) for count in counts) or sum(counts) != total:
                raise ValueError("Direction counts must be nonnegative integers that sum to the video count")
            if not total:
                ax.text(50, index, "No video outcomes", ha="center", va="center", color=MUTED)
                continue
            left = 0.0
            for count, color in zip(counts, (BLUE, ORANGE, GRAY)):
                width = count / total * 100
                ax.barh(index, width, left=left, height=0.62, color=color, edgecolor="white", linewidth=0.8)
                if width >= 7:
                    ax.text(left + width / 2, index, str(int(count)), ha="center", va="center",
                            color="white" if color != GRAY else INK, fontsize=9, fontweight="bold")
                left += width
            ax.text(102, index, f"n={int(total)}", va="center", color=MUTED, fontsize=8.5)
        ax.set_title(split.title(), loc="left", fontsize=12, fontweight="bold", pad=15)
        ax.set_xlim(0, 116)
        ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
        ax.set_yticks(range(len(labels)), labels)
        ax.set_xlabel("Share of source videos", labelpad=8)
        ax.grid(axis="x", alpha=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0, pad=9)
    axes[0].invert_yaxis()
    handles = [plt.Rectangle((0, 0), 1, 1, color=color) for color in (BLUE, ORANGE, GRAY)]
    fig.legend(handles, ["Long", "Short", "Flat / abstain"], loc="lower center",
               bbox_to_anchor=(0.58, 0.12), ncol=3, columnspacing=2.5)
    _footer(fig, ["Numbers inside bars count source videos, not trades. A directional label can still fail an execution filter.",
                  "Strategies sharing an extractor repeat the same counts; holding periods and confirmation change execution, not extraction."])
    return fig


def _cost_note(result: dict, name: str) -> str:
    config = result.get("config", {})
    if "fee_bps" not in config or "slippage_bps" not in config:
        return f"{name} costs include the run's executed fees and adverse slippage."
    fee = _number(config["fee_bps"], "fee_bps")
    slippage = _number(config["slippage_bps"], "slippage_bps")
    return f"{name} costs: {fee:g} basis points in fees + {slippage:g} in adverse slippage per executed leg."


def _diagnostic_notes(study: dict) -> list[str]:
    note = study.get("metadata", {}).get("post_outcome_diagnostics", {}).get("chart_note")
    return [str(note)] if note else []


def _period(result: dict) -> str:
    times, _ = _curve(result)
    return f"{times[0]:%d %b %Y}–{times[-1]:%d %b %Y}"


def _equity(plt: Any, dates: Any, ticker: Any, study: dict) -> Any:
    rows = _strategy_rows(study, "holdout")
    if not rows:
        raise ValueError("The study has no base-cost holdout results")
    controls = _controls(study, rows)
    nrows = math.ceil((len(rows) + 1) / 2)
    fig, axes = plt.subplots(nrows, 2, figsize=(15, 3.05 * nrows + 2.35), squeeze=False, sharex=True, sharey=True)
    fig.subplots_adjust(left=0.075, right=0.965, top=0.87, bottom=0.13, hspace=0.51, wspace=0.18)
    _heading(fig, "Holdout equity after trading costs",
             f"{_period(_run(study, rows[0]))} · 10,000 USDT initial equity · base costs · hourly closes in UTC")
    flat_axes = list(axes.flat)
    all_values = [INITIAL_EQUITY]
    all_times = []
    for row, ax in zip(rows, flat_axes):
        result = _run(study, row)
        holding = int(row.get("holding_hours", result.get("config", {}).get("holding_hours", 24)))
        lines = [(result, BLUE, "-", "Transcript heuristic"),
                 (controls["Buy and hold"], GRAY, "--", "Buy and hold"),
                 (controls[f"Price-only momentum, {holding}-hour hold"], ORANGE, ":", f"Price only · {holding}-hour hold")]
        for run, color, style, label in lines:
            times, values = _curve(run)
            ax.plot(times, values, color=color, linestyle=style, linewidth=1.6 if style == "-" else 1.25, label=label)
            all_values.extend(values)
            all_times.extend(times)
        ax.set_title(textwrap.fill(_label(row), 51), loc="left", fontsize=11, fontweight="bold", pad=10)
        ax.legend(loc="upper left", fontsize=7.7, ncol=1, handlelength=2.5, labelspacing=0.28)
    control_ax = flat_axes[len(rows)]
    control_colors = [GRAY, TEAL, ORANGE, BLUE]
    for index, (label, result) in enumerate(controls.items()):
        times, values = _curve(result)
        control_ax.plot(times, values, label=label, color=control_colors[index % len(control_colors)],
                        linestyle="--" if label == "Buy and hold" else "-", linewidth=1.6)
    control_ax.set_title("Controls, once per holding period", loc="left", fontsize=11, fontweight="bold", pad=10)
    control_ax.legend(loc="upper left", fontsize=7.5)
    span = max(all_values) - min(all_values)
    padding = max(160.0, span * 0.18)
    for index, ax in enumerate(flat_axes):
        if index > len(rows):
            ax.axis("off")
            ax.text(0, 0.9, "How to read the controls", transform=ax.transAxes, fontsize=11, fontweight="bold")
            ax.text(0, 0.74, "Buy and hold stays invested throughout the sample.\n\n"
                    "Price-only momentum uses the previous 24 completed\n"
                    "hours at the same video clocks, including abstentions.\n\n"
                    "Its 24- and 48-hour holds are distinct controls.\n"
                    "It has no breakout confirmation gate.", transform=ax.transAxes,
                    fontsize=9, color=MUTED, va="top", linespacing=1.5)
            continue
        ax.axhline(INITIAL_EQUITY, color=INK, alpha=0.38, linewidth=0.8)
        ax.set_ylim(min(all_values) - padding, max(all_values) + padding * 1.6)
        ax.set_xlim(min(all_times), max(all_times))
        ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("{x:,.0f}"))
        _date_axis(ax, dates)
        if index % 2 == 0:
            ax.set_ylabel("Equity (USDT)")
        ax.tick_params(axis="x", labelbottom=True, labelsize=8)
    _footer(fig, [_cost_note(_run(study, rows[0]), "Base"),
                  "All panels use the same scale. Price-only controls are deduplicated by holding period and never use breakout confirmation.",
                  "Returns include hourly marks on open positions; unincurred exit costs are excluded. Short positions are synthetic; borrow and funding are omitted."]
            + _diagnostic_notes(study))
    return fig


def _results(plt: Any, study: dict) -> Any:
    base = _strategy_rows(study, "holdout")
    stress = _strategy_rows(study, "holdout", "stress")
    stress_by_variant = {row["variant"]: row for row in stress}
    base_controls = _controls(study, base)
    stress_controls = _controls(study, stress) if stress else {}
    comparisons: list[dict[str, Any]] = [{"label": _label(row), "base": _run(study, row),
                    "stress": _run(study, stress_by_variant[row["variant"]]) if row["variant"] in stress_by_variant else None,
                    "control": False} for row in base]
    comparisons += [{"label": label, "base": result, "stress": stress_controls.get(label), "control": True}
                    for label, result in base_controls.items()]
    fig, axes = plt.subplots(1, 2, figsize=(15, max(7.6, 3 + 0.55 * len(comparisons))), sharey=True)
    fig.subplots_adjust(left=0.25, right=0.96, top=0.80, bottom=0.24, wspace=0.24)
    _heading(fig, "Holdout returns and drawdowns",
             f"{_period(_run(study, base[0]))} · base versus stress costs · 10,000 USDT initial equity")
    labels = [textwrap.fill(item["label"], 35) for item in comparisons]
    for ax, metric, title in zip(axes, ("return_pct", "max_drawdown_pct"),
                                 ("Return after fees and slippage", "Maximum peak-to-trough drawdown")):
        values = [0.0]
        plotted = []
        for index, item in enumerate(comparisons):
            if index % 2 == 0:
                ax.axhspan(index - 0.48, index + 0.48, color=BACKGROUND, zorder=0)
            for cost, shift, color in (("base", -0.15, BLUE), ("stress", 0.15, ORANGE)):
                run = item[cost]
                if run is None:
                    continue
                value = _number(_summary(run)[metric], metric)
                if metric == "max_drawdown_pct" and value < 0:
                    raise ValueError("Maximum drawdown must be a nonnegative loss magnitude")
                values.append(value)
                plotted.append((index + shift, value, color))
                ax.barh(index + shift, value, height=0.26, color=color, alpha=0.9, zorder=3)
        width = max(1.0, max(values) - min(values))
        low = min(values) - width * 0.20 if metric == "return_pct" else 0.0
        high = max(values) + width * 0.24
        ax.set_xlim(low, high)
        for y, value, color in plotted:
            sign = 1 if value >= 0 else -1
            text = f"{value:+.2f}%" if metric == "return_pct" else f"{value:.2f}%"
            ax.text(value + sign * width * 0.018, y, text, ha="left" if sign > 0 else "right",
                    va="center", fontsize=7.5, color=color)
        ax.axvline(0, color=INK, linewidth=0.8)
        if base and len(comparisons) > len(base):
            ax.axhline(len(base) - 0.5, color=MUTED, linewidth=0.8, alpha=0.65)
        ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold", pad=14)
        ax.set_yticks(range(len(labels)), labels)
        ax.tick_params(axis="y", length=0, pad=9)
        ax.set_xlabel("Percent", labelpad=8)
        ax.grid(axis="x", alpha=0.65)
        ax.set_axisbelow(True)
    axes[0].invert_yaxis()
    handles = [plt.Rectangle((0, 0), 1, 1, color=color) for color in (BLUE, ORANGE)]
    fig.legend(handles, ["Base costs", "Stress costs"], ncol=2, loc="lower center", bbox_to_anchor=(0.60, 0.135))
    missing = any(item["stress"] is None for item in comparisons)
    notes = [_cost_note(_run(study, base[0]), "Base")]
    notes.append(_cost_note(_run(study, stress[0]), "Stress") if stress else "Stress-cost results were not supplied.")
    notes.append("Controls appear below the divider. Price-only momentum has no breakout confirmation; identical holds are shown once.")
    notes.append("Drawdown uses hourly marked equity. Open positions exclude unincurred exit costs; short borrow and funding are omitted."
                 + (" Some stress results are unavailable." if missing and stress else ""))
    _footer(fig, notes + _diagnostic_notes(study))
    return fig


def render_study_charts(study: dict, sources: dict, out: Path) -> list[str]:
    """Write four PNG/SVG chart pairs and return their names relative to ``out``.

    ``study`` contains ``coverage``, flat summary ``rows`` and complete ``runs``
    keyed by ``run_id``. Rows identify ``split``, ``variant``, ``label``,
    ``extractor``, ``cost`` (``base``/``stress``) and ``holding_hours``. Results
    use the schema returned by ``run_research_backtest``. ``sources['entries']``
    supplies the frozen IDs, splits, content types and publication timestamps.
    No result is ranked, selected or recalculated by this function.
    """
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.dates as dates
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker
    except ImportError as exc:
        raise RuntimeError("Chart rendering requires Matplotlib; use a Python runtime with Matplotlib available") from exc
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    names = []
    style = dict(STYLE, **{"svg.hashsalt": str(study.get("study_id", "krown-study"))})
    with plt.rc_context(style):
        renderers = [("cohort-timeline", lambda: _timeline(plt, dates, sources)),
                     ("coverage", lambda: _coverage(plt, study)),
                     ("holdout-equity", lambda: _equity(plt, dates, ticker, study)),
                     ("holdout-results", lambda: _results(plt, study))]
        for name, render in renderers:
            fig = render()
            try:
                for extension in ("png", "svg"):
                    filename = f"{name}.{extension}"
                    metadata: dict[str, Any] = {"Title": name.replace("-", " ").title(),
                                "Description": f"{study.get('study_id', 'Krown study')}; retrospective research; UTC"}
                    if extension == "svg":
                        metadata["Date"] = None
                    fig.savefig(out / filename, dpi=180, bbox_inches="tight", pad_inches=0.18,
                                facecolor=BACKGROUND, metadata=metadata)
                    names.append(filename)
            finally:
                plt.close(fig)
    return names
