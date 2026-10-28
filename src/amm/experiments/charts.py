"""Static report charts (matplotlib, light surface) generated from executed runs.

Colour follows the entity (policy), fixed everywhere in the project:
adaptive = slot 1 blue, periodic = slot 2 orange, static = slot 3 aqua
(validated categorical palette; aqua is < 3:1 on the light surface, so
every chart carries direct labels and the numbers are also in tables).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

POLICY_COLORS = {"adaptive": "#2a78d6", "periodic": "#eb6834", "static": "#1baf7a"}
POLICY_COLORS_DARK = {"adaptive": "#3987e5", "periodic": "#d95926", "static": "#199e70"}
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT2 = "#52514e"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
ORDER = ["adaptive", "periodic", "static", "adaptive+ (post-hoc)"]
# The post-hoc variant is the same entity family as adaptive: same hue, different mark
# (hollow diamond / dashed line) - a 4th hue would fail the all-pairs CVD check in scatters.
POLICY_COLORS["adaptive+ (post-hoc)"] = POLICY_COLORS["adaptive"]
LINESTYLE = {"adaptive+ (post-hoc)": (0, (5, 2))}


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(AXIS)
        ax.spines[s].set_linewidth(1)
    ax.grid(axis="y", color=GRID, linewidth=1, linestyle="-")
    ax.set_axisbelow(True)
    ax.tick_params(colors=TEXT2, labelsize=9)
    ax.yaxis.label.set_color(TEXT2)
    ax.xaxis.label.set_color(TEXT2)


def rolling_error(daily: dict[str, pd.DataFrame], title: str, out: Path, change: dict | None = None, window: int = 28, events=None):
    """daily: policy -> daily frame (day, mae). Rolling mean of daily MAE."""
    fig, ax = plt.subplots(figsize=(10, 4.2), facecolor=SURFACE)
    _style(ax)
    ends = []
    for pol in ORDER:
        if pol not in daily:
            continue
        d = daily[pol].sort_values("day")
        r = d["mae"].rolling(window, min_periods=window // 2).mean()
        ax.plot(d["day"], r, color=POLICY_COLORS[pol], linewidth=2, solid_capstyle="round", label=pol, linestyle=LINESTYLE.get(pol, "-"))
        ends.append((pol, d["day"].iloc[-1], r.iloc[-1]))
    lo_day = min(d["day"].min() for d in daily.values())
    hi_day = max(d["day"].max() for d in daily.values())
    ymin, ymax = ax.get_ylim()
    if change:
        start = pd.Timestamp(change["start"])
        ax.axvline(start, color=TEXT2, linewidth=1)
        txt = "injected change" + (" (ramp shaded)" if change.get("end") else "")
        ax.text(start, ymin + 0.02 * (ymax - ymin), f" {txt}", color=TEXT2, fontsize=8, va="bottom")
        if change.get("end"):
            ax.axvspan(start, pd.Timestamp(change["end"]), color=GRID, alpha=0.6, linewidth=0)
    for name, ts in events or []:
        t = pd.Timestamp(ts)
        if lo_day <= t <= hi_day:
            ax.axvline(t, color=AXIS, linewidth=1)
            ax.text(t, ymax, f" {name}", color=TEXT2, fontsize=8, va="top")
    ax.set_xlim(lo_day, hi_day + (hi_day - lo_day) * 0.06)
    # direct end labels only where they do not collide (otherwise the legend carries identity)
    ends.sort(key=lambda e: e[2] if e[2] == e[2] else 0)
    span = ymax - ymin
    for i, (pol, x, y) in enumerate(ends):
        near = [abs(y - o[2]) < 0.06 * span for j, o in enumerate(ends) if j != i]
        if not any(near):
            ax.annotate(f" {pol}", (x, y), color=TEXT, fontsize=8, va="center")
    ax.set_ylabel(f"MAE, trips/hour ({window}-day rolling)")
    ax.set_title(title, color=TEXT, fontsize=11, loc="left")
    ax.legend(frameon=False, fontsize=9, loc="upper left", ncol=3, labelcolor=TEXT)
    fig.tight_layout()
    fig.savefig(out, dpi=130, facecolor=SURFACE)
    plt.close(fig)


def tradeoff(table: pd.DataFrame, out: Path):
    """Quality vs effort: one small panel per scenario, x = training wall time, y = MAE."""
    scen = list(table["scenario"].unique())
    n = len(scen)
    cols = min(3, n)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(4.2 * cols, 3.4 * rows), facecolor=SURFACE, squeeze=False)
    for i, sc in enumerate(scen):
        ax = axes[i // cols][i % cols]
        _style(ax)
        ax.grid(axis="x", color=GRID, linewidth=1)
        t = table[table["scenario"] == sc]
        xmax_ = max(1.0, float(t["train_seconds"].max()))
        yspan = max(float(t["mae"].max() - t["mae"].min()), 0.06 * float(t["mae"].mean()))
        groups: list = []  # points closer than ~4 % of the axis spans share one label
        for _, r in t.iterrows():
            pol = r["policy"]
            if pol == "adaptive+ (post-hoc)":
                ax.scatter(r["train_seconds"], r["mae"], s=70, marker="D", facecolor=SURFACE, edgecolor=POLICY_COLORS[pol], linewidth=2, zorder=4)
            else:
                ax.scatter(r["train_seconds"], r["mae"], s=64, color=POLICY_COLORS[pol], edgecolor=SURFACE, linewidth=2, zorder=3)
            cyc = r["cycles"]
            label = f"{pol} ({cyc:.0f} cycles)" if abs(cyc - round(cyc)) < 0.05 else f"{pol} ({cyc:.1f} cycles)"
            for g in groups:
                if abs(g[0] - r["train_seconds"]) < 0.04 * xmax_ and abs(g[1] - r["mae"]) < 0.04 * yspan:
                    g[2].append(label)
                    break
            else:
                groups.append([r["train_seconds"], r["mae"], [label]])
        for x, y, names in groups:
            # a label running right would cross a neighbour at similar height -> put it above the point
            blocked = any(0 < gx - x < 0.5 * xmax_ * 1.9 and abs(gy - y) < 0.08 * yspan for gx, gy, _ in groups)
            if blocked:
                ax.annotate("\n".join(names), (x, y), xytext=(0, 9), textcoords="offset points", fontsize=8, color=TEXT, ha="center", va="bottom")
            else:
                ax.annotate("  " + "\n  ".join(names), (x, y), fontsize=8, color=TEXT, va="center")
        ax.set_title(sc, color=TEXT, fontsize=10, loc="left")
        ax.set_xlabel("training wall time (s)")
        ax.set_ylabel("stream MAE")
        xmax = max(1.0, float(t["train_seconds"].max()))
        ax.set_xlim(-0.04 * xmax, xmax * 1.9)
        mid, half = float(t["mae"].mean()), max(float(t["mae"].max() - t["mae"].min()) * 0.75, 0.03 * float(t["mae"].mean()))
        ax.set_ylim(mid - half, mid + half)
    for j in range(n, rows * cols):
        axes[j // cols][j % cols].axis("off")
    present = [p for p in ORDER if p in set(table["policy"])]
    handles = [
        plt.Line2D([], [], marker="D", linestyle="", markerfacecolor=SURFACE, markeredgecolor=POLICY_COLORS[p], markeredgewidth=2, label=p, markersize=7)
        if p == "adaptive+ (post-hoc)" else plt.Line2D([], [], marker="o", linestyle="", color=POLICY_COLORS[p], label=p, markersize=8)
        for p in present
    ]
    fig.legend(handles=handles, frameon=False, loc="upper right", ncol=len(handles), fontsize=9, labelcolor=TEXT)
    fig.suptitle("Prediction quality vs training effort (mean over seeds)", color=TEXT, fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out, dpi=130, facecolor=SURFACE)
    plt.close(fig)


def yearly(mae_by_year: dict[str, dict], out: Path, title: str):
    """Grouped columns: MAE per year per policy."""
    df = pd.DataFrame(mae_by_year)  # index year, columns policy
    years = list(df.index)
    pols = [p for p in ORDER if p in df.columns]
    fig, ax = plt.subplots(figsize=(10, 3.8), facecolor=SURFACE)
    _style(ax)
    w = 0.26
    for k, pol in enumerate(pols):
        xs = [i + (k - (len(pols) - 1) / 2) * (w + 0.02) for i in range(len(years))]
        ax.bar(xs, df[pol].values, width=w, color=POLICY_COLORS[pol], label=pol, linewidth=0)
    ax.set_xticks(range(len(years)), years)
    ax.set_ylabel("MAE, trips/hour")
    ax.set_title(title, color=TEXT, fontsize=11, loc="left")
    ax.legend(frameon=False, fontsize=9, ncol=3, loc="upper left", labelcolor=TEXT)
    fig.tight_layout()
    fig.savefig(out, dpi=130, facecolor=SURFACE)
    plt.close(fig)
