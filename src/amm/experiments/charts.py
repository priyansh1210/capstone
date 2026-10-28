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


# ---------------------------------------------------------------- multi-city
# Entity colours for the multi-city figures. Only three categorical hues pass the
# all-pairs CVD check, so the proposed method (probe) takes slot 1 blue, the schedule
# family orange, static aqua; the ADWIN-style adaptive baselines are a de-emphasised
# dark grey told apart by marker shape + direct labels; the oracle reference is black.
MC = {"probe": "#2a78d6", "periodic": "#eb6834", "static": "#1baf7a", "adaptive": "#52514e", "oracle": "#0b0b0b"}
ADAPT_MARK = {"adaptive": "o", "adaptive-ph": "s", "adaptive-kswin": "^", "adaptive-bias": "D"}


def family(label: str) -> str:
    for f in ("probe", "periodic", "static", "oracle"):
        if label.startswith(f):
            return f
    return "adaptive"


ADAPT_NAME = {"adaptive": "ADWIN", "adaptive-ph": "Page-Hinkley", "adaptive-kswin": "KSWIN", "adaptive-bias": "ADWIN+bias"}
SCENARIO_NAME = {
    "city_chicago_unmodified": "Chicago 2019-24", "city_chicago_abrupt": "Chicago 2019-24 + injected abrupt",
    "city_nyc_unmodified": "New York 2019-24", "city_nyc_abrupt": "New York 2019-24 + injected abrupt",
    "city_sf_unmodified": "SF Bay Area 2020-24", "city_sf_abrupt": "SF Bay Area 2020-24 + injected abrupt",
    "city_dc_unmodified": "DC 2025 (Jan-Aug)", "bike_unmodified": "DC 2018-24 (exploratory)",
    "bike_abrupt": "DC 2018-24 + injected abrupt (exploratory)", "bike_gradual": "DC 2018-24 + injected gradual (exploratory)",
}
# label offsets tried in order (points): right, below, above, left, then the diagonals
_SPOTS = ((7, 0, "left", "center"), (0, -8, "center", "top"), (0, 8, "center", "bottom"), (-7, 0, "right", "center"),
          (7, -8, "left", "top"), (7, 8, "left", "bottom"), (-7, -8, "right", "top"), (-7, 8, "right", "bottom"))


def _mark_box(ax, x, y, r=6.0):
    from matplotlib.transforms import Bbox
    px, py = ax.transData.transform((x, y))
    return Bbox.from_bounds(px - r, py - r, 2 * r, 2 * r)


def _label(ax, x, y, text, taken, **kw):
    """Annotate (x, y) at the first offset whose text box overlaps no earlier label or mark
    and stays inside the axes; falls back to the first offset."""
    rend = ax.figure.canvas.get_renderer()
    for dx, dy, ha, va in _SPOTS:
        t = ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, **kw)
        bb = t.get_window_extent(rend)
        inside = bb.x0 >= ax.bbox.x0 and bb.x1 <= ax.bbox.x1 and bb.y0 >= ax.bbox.y0 and bb.y1 <= ax.bbox.y1
        if inside and not any(bb.overlaps(o) for o in taken):
            taken.append(bb)
            return t
        t.remove()
    dx, dy, ha, va = _SPOTS[0]
    t = ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, **kw)
    taken.append(t.get_window_extent(rend))
    return t


def pareto(summ: pd.DataFrame, scenarios: list[str], out: Path, title: str) -> None:
    """Error vs compute per scenario. Detector baselines are told apart by marker shape (legend),
    so only probe, static and the schedule intervals carry direct labels; a reference point far
    above the cluster (static, oracle) is pinned to the top edge and labelled with its value."""
    n = len(scenarios)
    cols = min(3, n)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(4.6 * cols, 3.8 * rows), facecolor=SURFACE, squeeze=False)
    tables = {}
    for i, sc in enumerate(scenarios):
        ax = axes[i // cols][i % cols]
        _style(ax)
        ax.grid(axis="x", color=GRID, linewidth=1)
        t = summ[(summ["scenario"] == sc) & ~summ["label"].str.contains("-no-")].copy()
        t["fam"] = t["label"].map(family)
        core = t[~t["fam"].isin(["static", "oracle"])]
        lo, hi = float(core["mae"].min()), float(core["mae"].max())
        pad = max(hi - lo, 0.02 * hi)
        top = hi + 0.18 * pad
        for _, r in t[t["fam"].isin(["static", "oracle"])].iterrows():
            if r["mae"] <= hi + 0.6 * pad:
                top = max(top, r["mae"] + 0.12 * pad)
        ax.set_ylim(lo - 0.18 * pad, top)
        xmax = max(1.0, float(t["compute_seconds"].max()))
        ax.set_xlim(-0.04 * xmax, xmax * 1.18)
        ax.set_title(SCENARIO_NAME.get(sc, sc), color=TEXT, fontsize=10, loc="left")
        ax.set_xlabel("compute: training + probes (s)")
        ax.set_ylabel("stream MAE (trips/h)")
        tables[i] = t
    for j in range(n, rows * cols):
        axes[j // cols][j % cols].axis("off")
    handles = [
        plt.Line2D([], [], marker="*", linestyle="", color=MC["probe"], markersize=12, label="probe (ours)"),
        plt.Line2D([], [], marker="o", color=MC["periodic"], linewidth=2, markersize=6, label="periodic 14/28/56/91 d"),
        plt.Line2D([], [], marker="o", linestyle="", color=MC["static"], markersize=7, label="static"),
    ] + [plt.Line2D([], [], marker=ADAPT_MARK[k], linestyle="", markerfacecolor=SURFACE, markeredgecolor=MC["adaptive"], markeredgewidth=1.6,
                    markersize=7, label=v) for k, v in ADAPT_NAME.items()]
    if any((t["fam"] == "oracle").any() for t in tables.values()):
        handles.append(plt.Line2D([], [], marker="x", linestyle="", color=MC["oracle"], markersize=7, markeredgewidth=2, label="oracle"))
    fig.suptitle(title, color=TEXT, fontsize=11, x=0.01, y=0.995, ha="left", va="top")
    fig.legend(handles=handles, frameon=False, loc="upper left", bbox_to_anchor=(0.005, 0.955), ncol=len(handles), fontsize=8, labelcolor=TEXT)
    fig.tight_layout(rect=(0, 0, 1, 0.86 if rows == 1 else 0.91))
    fig.canvas.draw()
    for i, t in tables.items():
        ax = axes[i // cols][i % cols]
        ytop = ax.get_ylim()[1]
        per = t[t["fam"] == "periodic"].copy()
        per["iv"] = per["label"].str.split("-").str[1].astype(int)
        per = per.sort_values("iv")
        ax.plot(per["compute_seconds"], per["mae"], color=MC["periodic"], linewidth=2, marker="o", markersize=6, zorder=3)
        taken = []
        pts = []
        for _, r in t.iterrows():
            x, y = float(r["compute_seconds"]), float(r["mae"])
            off = y > ytop
            y = min(y, ytop)
            pts.append((r, x, y, off))
            taken.append(_mark_box(ax, x, y, 8 if r["fam"] == "probe" else 5))
        for r, x, y, off in pts:
            fam, lab = r["fam"], r["label"]
            if fam == "probe":
                ax.scatter(x, y, s=280, marker="*", color=MC["probe"], edgecolor=SURFACE, linewidth=1.2, zorder=6)
            elif fam == "static":
                ax.scatter(x, y, s=60, marker="^" if off else "o", color=MC["static"], edgecolor=SURFACE, linewidth=1.5, zorder=4, clip_on=False)
            elif fam == "oracle":
                ax.scatter(x, y, s=60, marker="x", color=MC["oracle"], linewidth=2, zorder=4, clip_on=False)
            elif fam == "adaptive":
                ax.scatter(x, y, s=48, marker=ADAPT_MARK.get(lab, "o"), facecolor=SURFACE, edgecolor=MC["adaptive"], linewidth=1.6, zorder=5)
        # labels: probe first (most important), then the schedule intervals, then off-scale references
        for r, x, y, off in sorted(pts, key=lambda p: {"probe": 0, "periodic": 1}.get(p[0]["fam"], 2)):
            fam = r["fam"]
            if fam == "probe":
                _label(ax, x, y, "probe", taken, fontsize=8.5, color=TEXT, fontweight="bold")
            elif fam == "periodic":
                _label(ax, x, y, f"{r['label'].split('-')[1]} d", taken, fontsize=7.5, color=TEXT2)
            elif fam in ("static", "oracle"):
                _label(ax, x, y, f"{fam} {r['mae']:.0f}" + (" (off scale)" if off else ""), taken, fontsize=7.5, color=TEXT2)
    fig.savefig(out, dpi=130, facecolor=SURFACE)
    plt.close(fig)


def forest(sig: pd.DataFrame, out: Path, title: str) -> None:
    """Paired daily-MAE differences with block-bootstrap 95 % CIs, as % of the comparator's MAE.
    Left: probe and ADWIN+bias vs the calibrated 28-day schedule; right: probe vs the 14-day one."""
    panels = [("periodic-28", [("probe", "probe (ours)", "o", MC["probe"]), ("adaptive-bias", "ADWIN+bias", "D", MC["adaptive"])]),
              ("periodic-14", [("probe", "probe (ours)", "o", MC["probe"])])]
    scen = [s for s in SCENARIO_NAME if s in set(sig["scenario"])]
    fig, axes = plt.subplots(1, 2, figsize=(11, 0.46 * len(scen) + 1.9), sharey=True, facecolor=SURFACE)
    lim = 0.0
    for ax, (b, series) in zip(axes, panels):
        _style(ax)
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", color=GRID, linewidth=1)
        ax.axvline(0, color=TEXT2, linewidth=1, zorder=1)
        for k, (a, lab, mk, col) in enumerate(series):
            shift = (k - (len(series) - 1) / 2) * 0.26
            for i, sc in enumerate(scen):
                r = sig[(sig["scenario"] == sc) & (sig["a"] == a) & (sig["b"] == b)]
                if r.empty:
                    continue
                r = r.iloc[0]
                base = float(r["mae_b"])
                lo, mid, hi = 100 * r["ci_lo"] / base, 100 * r["diff"] / base, 100 * r["ci_hi"] / base
                lim = max(lim, abs(lo), abs(hi))
                ax.plot([lo, hi], [i + shift, i + shift], color=col, linewidth=2, solid_capstyle="round", zorder=2)
                ax.scatter(mid, i + shift, marker=mk, s=64, color=col, edgecolor=SURFACE, linewidth=1.5, zorder=3)
        ax.set_title(f"vs {b}", color=TEXT, fontsize=10, loc="left")
    fig.supxlabel("difference in mean daily MAE, % of the comparator's MAE  (negative = lower error)", color=TEXT2, fontsize=9)
    for ax in axes:
        ax.set_xlim(-1.08 * lim, 1.08 * lim)
    axes[0].set_yticks(range(len(scen)))
    axes[0].set_yticklabels([SCENARIO_NAME[s] for s in scen])
    axes[0].invert_yaxis()
    handles = [plt.Line2D([], [], marker="o", color=MC["probe"], linewidth=2, markersize=7, label="probe (ours)"),
               plt.Line2D([], [], marker="D", color=MC["adaptive"], linewidth=2, markersize=6, label="ADWIN+bias")]
    fig.suptitle(title, color=TEXT, fontsize=11, x=0.01, y=0.995, ha="left", va="top")
    fig.legend(handles=handles, frameon=False, loc="upper left", bbox_to_anchor=(0.005, 0.955), ncol=2, fontsize=9, labelcolor=TEXT)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    fig.savefig(out, dpi=130, facecolor=SURFACE)
    plt.close(fig)


def rolling_multi(daily: dict, title: str, out: Path, change: dict | None = None, window: int = 28) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.0), facecolor=SURFACE)
    _style(ax)
    order = ["static", "periodic-28", "adaptive", "probe"]
    for lab in [o for o in order if o in daily]:
        d = daily[lab].sort_values("day")
        fam = family(lab)
        ax.plot(d["day"], d["mae"].rolling(window, min_periods=window // 2).mean(), color=MC[fam], linewidth=2.4 if fam == "probe" else 1.8,
                label={"probe": "probe (ours)", "adaptive": "adaptive (ADWIN)"}.get(lab, lab))
    ymin, ymax = ax.get_ylim()
    if change and change.get("start"):
        st = pd.Timestamp(change["start"])
        ax.axvline(st, color=TEXT2, linewidth=1)
        ax.text(st, ymin + 0.02 * (ymax - ymin), " injected change", color=TEXT2, fontsize=8, va="bottom")
    ax.set_ylabel(f"MAE, trips/hour ({window}-day rolling)")
    ax.set_title(title, color=TEXT, fontsize=11, loc="left")
    ax.legend(frameon=False, fontsize=9, ncol=4, loc="upper left", labelcolor=TEXT)
    fig.tight_layout()
    fig.savefig(out, dpi=130, facecolor=SURFACE)
    plt.close(fig)
