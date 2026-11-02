"""Truck routes from the smallest hatchery (by 2026 stream supply): PFBC's 2026 plan vs the model's plan, one map plus a road-miles strip.

Smallest hatchery = the scheduled hatchery with the least supply in data/processed/hatcheries.parquet (Tionesta, 15,257 fish).
Routes are drawn per k-medoids cluster (the unit the model prices haul cost on): one curved line from the hatchery to the fish-weighted
centre of the cluster's destination sections, width by fish. The lines are schematic (no road geometry: the OSRM route service is not
reachable from every machine); every mile shown is the cluster's average OSRM road miles (cost_matrix.cluster_road_mi, Gavin's script 18).
PFBC 2026 = run "baseline" (schedule credits: each section's 2026 count split equally over its scheduled events); model plan =
"none|dominance" (more angler benefit at no more than PFBC's 2026 cost and impact), the same default as scripts/figures/34-36.

Inputs : data/processed/hatcheries.parquet, cost_matrix.parquet, sections.parquet, pa_trout.gpkg (sections),
         outputs/tables/optimization/flows.parquet, data/raw/pa_boundary.gpkg
Outputs: outputs/figures/smallest_hatchery/<hatchery>_truck_routes.png   logs/44_smallest_hatchery_routes.log

    python scripts/figures/44_smallest_hatchery_routes.py [run_id]      (default none|dominance)
"""
# %% Setup
from __future__ import annotations

import logging
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scripts/, where common.py lives
from common import PROCESSED_DIR, RAW_DIR, ROOT, setup_logging, register_open_sans

RUN = sys.argv[1] if len(sys.argv) > 1 else "none|dominance"
SURFACE, INK, INK2, FAINT = "#ffffff", "#0b0b0b", "#52514e", "#e2e1dc"
OLD, NEW, AMBER, AMBER_EDGE, BERRY = "#a6192e", "#2a78d6", "#f5ae00", "#2b2100", "#a6192e"
FIG_DIR = ROOT / "outputs" / "figures" / "smallest_hatchery"
FIG_DIR.mkdir(parents=True, exist_ok=True)
setup_logging("44_smallest_hatchery_routes")
log = logging.getLogger("44_smallest_hatchery_routes")
register_open_sans()
plt.rcParams.update({"font.family": ["Open Sans", "DejaVu Sans"], "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK})
halo = [pe.withStroke(linewidth=3.5, foreground="white")]

# %% Smallest hatchery and its two plans
hat = pd.read_parquet(PROCESSED_DIR / "hatcheries.parquet")
hat = hat[hat.in_2026_schedule & (hat.supply > 0)].sort_values("supply")
h = hat.iloc[0]
NAME = h.hatchery
log.info("supply by hatchery: %s -> smallest %s (%.0f fish)", hat.set_index("hatchery").supply.to_dict(), NAME, h.supply)

flows = pd.read_parquet(ROOT / "outputs" / "tables" / "optimization" / "flows.parquet")
assert RUN in set(flows.run_id), f"unknown run {RUN}"
cm = pd.read_parquet(PROCESSED_DIR / "cost_matrix.parquet")
cm = cm[cm.hatchery == NAME].set_index("section_id")
sec = pd.read_parquet(PROCESSED_DIR / "sections.parquet").set_index("section_id")


def plan(run: str) -> pd.DataFrame:
    s = flows[(flows.run_id == run) & (flows.hatchery == NAME) & (flows.x > 0.5)].groupby("section_id").x.sum().rename("fish").reset_index()
    s["cluster"] = s.section_id.map(cm.cluster_id)
    s["mi"] = s.section_id.map(cm.cluster_road_mi)
    s["water"] = s.section_id.map(sec.water_name)
    s["county"] = s.section_id.map(sec.county)
    s["lon"], s["lat"] = s.section_id.map(sec.mid_lon), s.section_id.map(sec.mid_lat)
    assert s[["cluster", "mi", "lon", "lat"]].notna().all().all(), "every destination has a cluster, road miles and a midpoint"
    return s


def by_cluster(s: pd.DataFrame) -> pd.DataFrame:
    g = s.assign(wlon=s.lon * s.fish, wlat=s.lat * s.fish).groupby("cluster").agg(
        fish=("fish", "sum"), mi=("mi", "first"), wlon=("wlon", "sum"), wlat=("wlat", "sum"), n=("section_id", "size"),
        waters=("water", lambda w: list(dict.fromkeys(w))), county=("county", "first"))
    g["lon"], g["lat"] = g.wlon / g.fish, g.wlat / g.fish
    return g.drop(columns=["wlon", "wlat"]).sort_values("mi")


old, new = plan("baseline"), plan(RUN)
oc, nc = by_cluster(old), by_cluster(new)
avg = lambda s: float((s.fish * s.mi).sum() / s.fish.sum())
near = lambda s, m=25: float(s.loc[s.mi <= m, "fish"].sum() / s.fish.sum())
stats = {k: dict(sections=len(s), clusters=s.cluster.nunique(), fish=s.fish.sum(), avg_mi=avg(s), max_mi=s.mi.max(), within25=near(s))
         for k, s in (("PFBC 2026", old), ("model", new))}
for k, v in stats.items():
    log.info("%s: %d sections in %d clusters, %.0f fish, fish-weighted %.1f road mi, farthest %.0f mi, %.0f%% of fish within 25 mi",
             k, v["sections"], v["clusters"], v["fish"], v["avg_mi"], v["max_mi"], 100 * v["within25"])
for k, g in (("PFBC 2026", oc), ("model", nc)):
    log.info("%s clusters:\n%s", k, g[["fish", "mi", "n", "county", "waters"]].to_string())
kept = set(old.section_id) & set(new.section_id)
log.info("sections in both plans: %d", len(kept))
# Who supplies the sections Tionesta no longer serves, in the model plan (context for the caption)
run = flows[(flows.run_id == RUN) & (flows.x > 0.5)]
dropped = old[~old.section_id.isin(new.section_id)]
who = run[run.section_id.isin(dropped.section_id)].groupby(["section_id", "hatchery"]).x.sum().reset_index()
log.info("dropped Tionesta sections and their model supplier:\n%s", dropped[["section_id", "water", "county", "fish", "mi"]]
         .merge(who, on="section_id", how="left").to_string())

# %% Draw
fig = plt.figure(figsize=(13.333, 7.5))
fig.text(0.025, 0.935, f"{NAME}: The Smallest Hatchery's Truck Routes", fontsize=30, color=BERRY, ha="left", va="center")
fig.text(0.025, 0.872, f"{NAME} ships {h.supply:,.0f} stream trout in 2026, the fewest of PFBC's nine hatcheries. "
         f"Model plan: more angler benefit at PFBC's 2026 cost and wild-trout impact.", fontsize=11.5, color=INK2, ha="left", va="center")

ax = fig.add_axes([0.01, 0.06, 0.58, 0.78])
pa = gpd.read_file(RAW_DIR / "pa_boundary.gpkg").to_crs(4326)
lines = gpd.read_file(PROCESSED_DIR / "pa_trout.gpkg", layer="sections")[["section_id", "geometry"]]
stocked = lines[lines.section_id.isin(set(flows.loc[flows.run_id == "baseline", "section_id"]))]
hx, hy = h.lon, h.lat
fmax = max(oc.fish.max(), nc.fish.max())
LOCAL_MI = 25                                   # clusters this close are labelled in the zoom inset, the rest on the main map


def short(w: list[str]) -> str:
    return w[0] if len(w) == 1 else f"{w[0]} +{len(w) - 1}"


def draw(a, lw_scale: float, sec_lw: float, label_ids: set, off: dict, fs: float) -> None:
    pa.plot(ax=a, facecolor="#ffffff", edgecolor=INK2, lw=1.1, zorder=0)
    stocked.plot(ax=a, color=FAINT, lw=0.8, zorder=1)
    lines[lines.section_id.isin(old.section_id)].plot(ax=a, color=OLD, lw=sec_lw, zorder=4)
    lines[lines.section_id.isin(new.section_id)].plot(ax=a, color=NEW, lw=sec_lw, zorder=5)
    for g, color, bend, ls in ((oc, OLD, 0.18, (0, (2.2, 1.4))), (nc, NEW, -0.18, "-")):
        for cid, r in g.iterrows():
            dx, dy = r.lon - hx, r.lat - hy                 # quadratic curve hatchery -> cluster centre; PFBC bows left, model right
            cx, cy = (hx + r.lon) / 2 - bend * dy, (hy + r.lat) / 2 + bend * dx
            t = np.linspace(0, 1, 60)[:, None]
            q = (1 - t) ** 2 * np.array([hx, hy]) + 2 * (1 - t) * t * np.array([cx, cy]) + t ** 2 * np.array([r.lon, r.lat])
            a.plot(q[:, 0], q[:, 1], color=color, lw=lw_scale * (1.2 + 7 * np.sqrt(r.fish / fmax)), ls=ls, solid_capstyle="round",
                   dash_capstyle="round", alpha=0.9, zorder=3)
            if cid in label_ids:
                ox, oy, ha = off.get(cid, (10, 0, "left"))
                a.annotate(f"{short(r.waters)}\n{r.mi:.0f} mi · {r.fish:,.0f} fish", (r.lon, r.lat), xytext=(ox, oy), textcoords="offset points",
                           ha=ha, va="center", fontsize=fs, color=color, fontweight="bold", path_effects=halo, zorder=8, linespacing=1.15)
    a.scatter([hx], [hy], s=520 * lw_scale, c=AMBER, edgecolors=AMBER_EDGE, linewidths=1.6, zorder=7)
    a.set_axis_off()


far = set(oc.index[oc.mi > LOCAL_MI]) | set(nc.index[nc.mi > LOCAL_MI])
local = (set(oc.index) | set(nc.index)) - far
# label offsets in points, chosen per cluster so labels clear the lines (fallback: right of the anchor)
OFF = {"B052": (10, -4, "left"), "B174": (-10, -12, "right"), "B005": (0, 14, "center"), "B033": (-10, 0, "right"),
       "B002": (-10, 0, "right"), "B031": (8, 10, "left"), "B011": (-12, -4, "right")}
draw(ax, 1.0, 3.2, far, OFF, 8.6)
ax.annotate(NAME, (hx, hy), xytext=(-14, 14), textcoords="offset points", ha="right", va="bottom", fontsize=14, fontweight="bold",
            path_effects=halo, zorder=8)
xs = np.r_[old.lon, new.lon, hx]
ys = np.r_[old.lat, new.lat, hy]
x0, x1, y0, y1 = xs.min() - 0.55, xs.max() + 0.55, ys.min() - 0.25, ys.max() + 0.30
ax.set_xlim(x0, x1)
ax.set_ylim(y0, y1)
ax.set_aspect(1 / np.cos(np.radians((y0 + y1) / 2)))

# zoom inset: every cluster within LOCAL_MI road miles, on its real stream lines
loc_secs = pd.concat([old[old.cluster.isin(local)], new[new.cluster.isin(local)]]).section_id
bx0, by0, bx1, by1 = lines[lines.section_id.isin(loc_secs)].total_bounds
bx0, bx1 = min(bx0, hx) - 0.06, max(bx1, hx) + 0.06
by0, by1 = min(by0, hy) - 0.05, max(by1, hy) + 0.05
ax.add_patch(plt.Rectangle((bx0, by0), bx1 - bx0, by1 - by0, fill=False, ec=INK2, lw=1, ls="-", zorder=6))
ins = fig.add_axes([0.345, 0.30, 0.24, 0.36])
INS_OFF = {"B153": (0, 16, "center"), "B264": (0, -26, "center"), "B212": (-10, -6, "right"), "B158": (-4, -24, "center")}
draw(ins, 0.7, 4.0, local, INS_OFF, 8.4)
ins.annotate(NAME, (hx, hy), xytext=(-10, 12), textcoords="offset points", ha="right", va="bottom", fontsize=11, fontweight="bold",
             path_effects=halo, zorder=8)
ins.set_xlim(bx0, bx1)
ins.set_ylim(by0, by1)
ins.set_aspect(1 / np.cos(np.radians((by0 + by1) / 2)))
ins.set_axis_on()
ins.set_xticks([])
ins.set_yticks([])
ins.set_xlabel("")
ins.set_ylabel("")
for sp in ins.spines.values():
    sp.set_color(INK2)
ins.set_title(f"Within {LOCAL_MI} road miles", fontsize=9.5, color=INK2, loc="left", pad=4)

ax.legend(handles=[Line2D([], [], color=OLD, lw=3, ls=(0, (2.2, 1.4)), label="PFBC 2026"),
                   Line2D([], [], color=NEW, lw=3, label="Model plan"),
                   Line2D([], [], color=FAINT, lw=2, label="Other stocked sections")],
          loc="lower right", frameon=False, fontsize=10, handlelength=2.6, borderaxespad=0.2)

# %% Right side: the headline and a road-miles strip (one bubble per cluster, area by fish)
o, n = stats["PFBC 2026"], stats["model"]
fig.text(0.62, 0.765, f"{o['avg_mi']:.0f}", fontsize=46, fontweight="bold", color=OLD, ha="left", va="center")
fig.text(0.715, 0.765, "→", fontsize=34, color=INK2, ha="center", va="center")
fig.text(0.745, 0.765, f"{n['avg_mi']:.0f}", fontsize=46, fontweight="bold", color=NEW, ha="left", va="center")
fig.text(0.62, 0.685, "average road miles each fish rides from the hatchery\n(cluster-average OSRM road miles, weighted by fish)",
         fontsize=11, color=INK2, ha="left", va="center", linespacing=1.3)

sx = fig.add_axes([0.685, 0.30, 0.29, 0.28])
xmax = 10 * np.ceil(max(o["max_mi"], n["max_mi"]) / 10) + 10
for yv, g, color in ((1, oc, OLD), (0, nc, NEW)):
    sx.axhline(yv, color=FAINT, lw=1, zorder=0)
    sx.scatter(g.mi, np.full(len(g), yv), s=1400 * g.fish / fmax, color=color, alpha=0.75, edgecolors="white", linewidths=1.2, zorder=3)
    w = avg(old if yv else new)
    sx.plot([w, w], [yv - 0.28, yv + 0.28], color=color, lw=2, zorder=4)
    sx.text(w, yv + 0.33, f"avg {w:.0f}", color=color, fontsize=8.5, ha="center", va="bottom", fontweight="bold")
sx.set_yticks([1, 0], ["PFBC 2026", "Model plan"], fontsize=11)
for t, c in zip(sx.get_yticklabels(), (OLD, NEW)):
    t.set_color(c)
    t.set_fontweight("bold")
sx.set_ylim(-0.6, 1.75)
sx.set_xlim(0, xmax)
sx.set_xlabel("Road miles from the hatchery (one bubble per cluster, area = fish)", fontsize=9.5, color=INK2)
sx.tick_params(axis="x", labelsize=9, colors=INK2)
sx.tick_params(axis="y", length=0)
for sp in ("top", "right", "left"):
    sx.spines[sp].set_visible(False)
sx.spines["bottom"].set_color(INK2)

fig.text(0.62, 0.19, f"PFBC 2026: {o['sections']} sections in {o['clusters']} clusters, farthest {o['max_mi']:.0f} mi, "
         f"{100 * o['within25']:.0f}% of fish within 25 mi.\n"
         f"Model plan: {n['sections']} sections in {n['clusters']} clusters, farthest {n['max_mi']:.0f} mi, "
         f"{100 * n['within25']:.0f}% of fish within 25 mi.\n"
         f"Sections in both plans: {len(kept)}. In the model plan, Tionesta's 2026 sections\ncome from "
         f"{', '.join(f'{k} ({v})' for k, v in who.groupby('section_id').x.idxmax().map(who.hatchery).value_counts().items())}.",
         fontsize=9.5, color=INK, ha="left", va="top", linespacing=1.45)
fig.text(0.025, 0.012, "Lines are schematic, one per k-medoids cluster (the unit the model prices haul cost on), drawn to the fish-weighted centre of its sections; "
         "width = fish. Miles are the cluster's average OSRM road miles.\nPFBC 2026 credits each section's 2026 count equally to its scheduled hatcheries. "
         "Model plan = run none|dominance (scripts/optimization.py).",
         fontsize=7.8, color=INK2, ha="left")

out = FIG_DIR / f"{NAME.lower().replace(' ', '_')}_truck_routes.png"
fig.savefig(out, dpi=300, facecolor=SURFACE)
log.info("wrote %s", out)
