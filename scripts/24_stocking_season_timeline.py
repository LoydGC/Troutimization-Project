"""Slide visual: PFBC's 2026 stream stocking schedule over the year, pre-season stockings versus in-season ("maintenance") stockings.

Season codes from the schedule (docs/data_dictionary.md, stocking_events.season): P pre-season, I in-season, F fall (W winter has lake events only).
One bar per week = the stream stockings scheduled that week, stacked by season. Counts are schedule facts. Trout per season are an estimate:
each section's 2026 count is split equally over its scheduled events (scripts/09_stocking_schedule.py `alloc_fish`). 73 stockings are listed by
week only (no day); they are placed at the start of that week. Stream events only (lakes have no fish counts). Title: Open Sans 40, the deck's
dark red berry, like the other slides.

Inputs : data/processed/stocking_events.parquet, data/processed/sections.parquet
Outputs: outputs/figures/allocation_problem/stocking_season_timeline.png   (16:9, 300 dpi)
         logs/24_stocking_season_timeline.log

    python scripts/24_stocking_season_timeline.py
"""
# %% Setup
from __future__ import annotations

import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from common import PROCESSED_DIR, ROOT, setup_logging

FIG_DIR = ROOT / "outputs" / "figures" / "allocation_problem"
SURFACE, INK, INK2, GRID = "#ffffff", "#0b0b0b", "#52514e", "#e6e5e0"
BLUE, AMBER, SLATE = "#2a78d6", "#f5ae00", "#8c8b85"
AMBER_TEXT = "#8a5d00"
TITLE = "#a6192e"                                                          # the deck's dark red berry
setup_logging("24_stocking_season_timeline")
log = logging.getLogger("24_stocking_season_timeline")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Open Sans (the deck's font; SIL Open Font License), local only: see scripts/20_allocation_map.py. Falls back to DejaVu Sans if absent.
FONT_DIR = ROOT / "data" / "references" / "fonts"
if (FONT_DIR / "OpenSans.ttf").exists():
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    from matplotlib import font_manager
    for style, wght in (("Regular", 400), ("Bold", 700)):
        cut = FONT_DIR / f"OpenSans-{style}.ttf"
        if not cut.exists():
            instancer.instantiateVariableFont(TTFont(FONT_DIR / "OpenSans.ttf"), {"wght": wght, "wdth": 100}, updateFontNames=True).save(cut)
        font_manager.fontManager.addfont(str(cut))
else:
    log.warning("data/references/fonts/OpenSans.ttf not found: falling back to DejaVu Sans")

# %% Load and summarise
ev = pd.read_parquet(PROCESSED_DIR / "stocking_events.parquet")
st = ev[ev.water_type == "stream"].copy()
st["when"] = st.date.fillna(st.week_of)                                    # week-only listings sit at the start of their week
assert st["when"].notna().all()
log.info("%d stream stockings; %d listed by week only", len(st), st.date.isna().sum())
assert set(st.season.unique()) <= {"P", "I", "F"}, "stream stockings should be pre-season, in-season or fall only"
st["week"] = st["when"].dt.to_period("W-SUN").dt.start_time
weekly = st.groupby(["week", "season"]).size().unstack(fill_value=0).reindex(columns=["P", "I", "F"], fill_value=0)
by = st.groupby("season").agg(n=("season", "size"), fish=("alloc_fish", "sum"), first=("when", "min"), last=("when", "max"))
tot_n, tot_fish = len(st), st.alloc_fish.sum()
n_no_fish = int(st.alloc_fish.isna().sum())                                # 13 on 8 sections with no 2026 count + 6 matched to no section
assert n_no_fish == 19 and int(st.date.isna().sum()) == 73
assert abs(tot_fish - 2606468) < 5, "stream fish on the schedule should be the 2.61M of the 2026 stocked-sections layer"
for s_, r_ in by.iterrows():
    log.info("%s: %d stockings (%.0f%%), %.0f trout (%.0f%%), %s to %s", s_, r_.n, 100 * r_.n / tot_n, r_.fish, 100 * r_.fish / tot_fish,
             r_["first"].date(), r_["last"].date())
n_late = int(((st.season == "I") & (st["when"] > pd.Timestamp("2026-05-22"))).sum())     # in-season stockings after late May
log.info("in-season stockings after May 22: %d of %d", n_late, int((st.season == "I").sum()))
peak = weekly.sum(axis=1).idxmax()
log.info("peak week %s: %d stockings", peak.date(), weekly.sum(axis=1).max())

tab = pd.read_parquet(PROCESSED_DIR / "sections.parquet", columns=["section_id", "total_2026"])
stocked = set(tab.loc[tab.total_2026.fillna(0) > 0, "section_id"])
per = st[st.section_id.isin(stocked)].groupby("section_id").season.agg(pre=lambda s: int((s == "P").sum()), inn=lambda s: int((s == "I").sum()))
assert len(per) == 1022
n_pre_only = int(((per.pre > 0) & (per.inn == 0)).sum())
n_pre_in = int(((per.pre > 0) & (per.inn > 0)).sum())
n_in_only = int(((per.pre == 0) & (per.inn > 0)).sum())
log.info("of 1,022 sections: pre-season + in-season %d, pre-season only %d, in-season only %d; most common %d with 1 pre + 1 in",
         n_pre_in, n_pre_only, n_in_only, int(((per.pre == 1) & (per.inn == 1)).sum()))

# %% Draw
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})
fig = plt.figure(figsize=(13.333, 7.5))
fig.suptitle("Pre-Season vs. In-Season Stocking, 2026", x=0.03, y=0.975, ha="left", fontsize=40, color=TITLE)
ax = fig.add_axes([0.07, 0.13, 0.58, 0.70])
x = weekly.index + pd.Timedelta(days=3.5)
bottom = pd.Series(0, index=weekly.index)
for code, color in (("P", BLUE), ("I", AMBER), ("F", SLATE)):
    ax.bar(x, weekly[code], bottom=bottom, width=6.2, color=color, edgecolor="white", linewidth=0.6, zorder=3)
    bottom = bottom + weekly[code]
ax.set_xlim(pd.Timestamp("2026-02-09"), pd.Timestamp("2026-10-31"))
ax.set_ylim(0, 260)
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
ax.set_yticks([0, 50, 100, 150, 200, 250])
ax.grid(axis="y", color=GRID, lw=1, zorder=0)
ax.tick_params(axis="both", labelsize=12, colors=INK2, length=0)
ax.tick_params(axis="x", pad=8)
for s_ in ("top", "right", "left"):
    ax.spines[s_].set_visible(False)
ax.spines["bottom"].set_color(INK2)
ax.set_ylabel("Stockings scheduled per week", fontsize=12, color=INK2, labelpad=10)
ax.text(pd.Timestamp("2026-03-08"), 236, "Pre-season", fontsize=17, fontweight="bold", color=BLUE, ha="center")
ax.text(pd.Timestamp("2026-05-02"), 246, "In-season", fontsize=17, fontweight="bold", color=AMBER_TEXT, ha="center")
ax.text(pd.Timestamp("2026-10-13"), 52, "Fall", fontsize=17, fontweight="bold", color=INK2, ha="center")

# %% Right panel: the three seasons in numbers
pan = fig.add_axes([0.69, 0.13, 0.29, 0.70])
pan.set_axis_off()
pan.set_xlim(0, 1)
pan.set_ylim(0, 1)
rows = (("P", "Pre-season", BLUE, BLUE), ("I", "In-season", AMBER, AMBER_TEXT), ("F", "Fall", SLATE, INK2))
for i, (code, name, bar, text) in enumerate(rows):
    y = 0.97 - i * 0.235
    r_ = by.loc[code]
    pan.add_patch(plt.Rectangle((0, y - 0.19), 0.018, 0.2, color=bar, transform=pan.transAxes, clip_on=False))
    pan.text(0.06, y, name, fontsize=15, fontweight="bold", color=text, va="top")
    pan.text(0.06, y - 0.055, f"{r_.fish / 1e6:.2f}M trout ({100 * r_.fish / tot_fish:.0f}%)", fontsize=15, va="top")
    pan.text(0.06, y - 0.105, f"{r_.n:,} stockings, {r_['first']:%b} {r_['first'].day} to {r_['last']:%b} {r_['last'].day}", fontsize=11.5, color=INK2, va="top")
fig.text(0.07, 0.068, f"Stream stockings only ({tot_n:,}; {n_no_fish} of them have no fish count). 73 are listed by week only and placed at the start of that week.",
         fontsize=9, color=INK2, ha="left")
fig.text(0.07, 0.045, "Trout are estimated by splitting each section's 2026 count across its scheduled stockings (by species, where the schedule marks one).",
         fontsize=9, color=INK2, ha="left")
fig.text(0.07, 0.022, "Source: PFBC 2026 trout stocking schedule (planned, subject to change) and 2026 stocked-sections layer.", fontsize=9, color=INK2, ha="left")

out = FIG_DIR / "stocking_season_timeline.png"
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)
