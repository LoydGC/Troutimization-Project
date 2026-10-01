# Clustering options for the cost model (status 2026-10-01)

## Objective (on record, Gavin, 2026-10-01)

A cluster is a group of sections that **cost about the same to reach from every hatchery**. It exists to hand the model one
representative cost per hatchery for the whole group. It is **not a trip**: nothing is routed or assigned to a cluster. The model
still decides `x[h, s]`, fish from hatchery h into section s, so different sections of one cluster can be supplied by different
hatcheries. A cluster only says "getting fish to this section costs about the same as getting them to that one", not that a
truck must visit every section.

- **Cost vector.** Each section s has `cost[h, s]` for every hatchery h (`2 × road miles × $ per truck-mile ÷ fish per load`).
  A cluster's representative cost from h is the mean of its members' `cost[h, s]`.
- **Hatchery-agnostic.** No hatchery is attached to a cluster, and PFBC's schedule is not used (except for #1, the reference).
- **Does not matter:** trip width, hop distance, sections per cluster, fish counts, truckloads.
- **Does matter:** how close the cluster's average cost is to each member's own cost, across hatcheries. Judged by mean and
  90th-percentile error, whether the cheapest hatchery for a section is preserved, and the extra cost (regret) if the model used
  the cluster average to pick. The number of clusters follows from an error tolerance, not a trip rule.

**Consequence for the options below.** #3 to #5 were built around trip-style limits (width, section count) and group by road
distance between sections, which is only a proxy for similar cost vectors. Their width, hop and size rules are superseded. The
next step is to cluster the cost vectors directly (#7, not built yet). Nothing below is deleted: they stay as proxy baselines.

**Where this lives.** This is Gavin's working document and is deliberately separate from `docs/model_design.md`, which still
carries Nate's cluster plan (run clusters, § Open questions: detour charge) unchanged. When this approach is settled, merge it
into `model_design.md` § Open questions as a third version next to Nate's two (geographic nearest-neighbour; schedule run
clusters), and update `CLAUDE.md` (Agreed simplifications) only after Nate agrees.

## Formal statement

- Each section s has a cost vector `c_s = (cost[h, s] for every hatchery h)`, with
  `cost[h, s] = 2 × road_mi[h, s] × cost_per_truck_mile / fish_per_load` (the existing `model_design.md` § Transport cost formula).
- A clustering assigns each section to a cluster k. The representative cost from h is `cbar[h, k]` = mean of `cost[h, s]` over
  the members of k, used in place of `cost[h, s]` for any s in k. The decision variables stay `x[h, s]`.
- Grade a clustering by (a) mean and 90th-percentile absolute error of `cbar[h, k]` against `cost[h, s]` over all hatchery and
  section pairs, (b) the share of sections whose cheapest hatchery is unchanged under `cbar`, (c) the regret: extra cost if the
  model picked the hatchery by `cbar`. Set the number of clusters from an error tolerance.
- Sections far apart on the map may share a cluster if their cost vectors match; geographic coherence is a readability
  preference, not a requirement.
- Status: options #2 to #6 below cluster by road distance between sections (a proxy for similar cost vectors) under trip-style
  limits that this objective supersedes. Clustering the cost vectors directly is the next step (#7, not built).

![The six options](../outputs/figures/method_comparison/options_overview.png)

Regenerate: `python scripts/16_compare_methods_map.py` (needs scripts 12, 13, 15 run first).

## The two families that matter

| | |
|---|---|
| **Schedule links** (#1) | PFBC's own runs define the clusters. Faithful, but frozen to PFBC's hatchery choices. Reference only. |
| **Geography only** (#2–#6) | Road miles between sections decide. The model stays free to choose hatcheries. |

Inside geography-only there are three algorithm families:

- **K-medoids** (#2, #3): you choose how many clusters; centers are real sections. Script 13.
- **Hierarchical, complete linkage** (#4, #5): you choose a maximum width; the number of clusters follows. Script 15.
- **DBSCAN** (#6): you choose a neighbour reach; clusters chain and loners become noise. Script 14 (scrapped, code kept).

## Where each option stands

1. **Nate's schedule clusters** (351). *Reference.* `section_schedule.cluster_id`.
2. **k-medoids, no limits** (351). *Baseline.* Built only in script 13 for comparison; not saved as a table.
3. **Script 13: k-medoids + limits** (407). *Candidate: most accurate cost estimate* (hatchery-distance error 1.7%). Limits: 20 mi wide, 4 sections. `section_medoid_clusters`.
4. **Width-limited 19.9 mi** (234). *Candidate: most faithful to real runs and tightest groups* (silhouette 0.42; hatchery-distance error 2.8%). `section_run_limited_clusters.tight_cluster_id`.
5. **Width-limited 47.5 mi** (74). *Upper bound.* The widest real run; hatchery-distance error doubles to 5.7%. `loose_cluster_id`.
6. **DBSCAN, eps 6 mi** (482, 271 alone). *Scrapped.* Useful only for flagging remote sections.

## The decision that was left (before the objective above)

**#3 vs #4**: accurate cost against faithfulness to real runs. #3 gives the smallest averaging error (1.7% vs 2.8%) but
keeps only 42% of real truck runs whole (65% for #4). #4 also needs fewer clusters (234 vs 407).

## Ideas we tried and retired

- **Hop limit** (longest jump between two sections in a run). Dropped: a truck's fuel is spent whether on one leg or many;
  only total reach (width) matters. It also changed almost nothing (sections link into 3 groups at 17.7 mi).
- **Section-count cap**. Dropped for cost purposes: a cluster only supplies an average cost, so size doesn't enter the
  cost. Width keeps the average accurate. (Script 13 still uses a 4-section cap.)
- **DBSCAN at 19.9 / 47.5 mi**. `eps` is a neighbour reach, not a width, so clusters chain and the whole state becomes one
  cluster. At 6 mi it behaves, but is the weakest option for cost.
- **k-medoids then split for the width rule**. Worse than complete linkage at the same width (270 vs 234 clusters,
  silhouette 0.34 vs 0.42).
- **Fish counts / truckload in clusters**. Deliberately ignored; see `scenarios_and_extensions.md`.

## Where the numbers come from

Tight and loose widths are the real-run width percentiles on the road-mile matrix: 90th = 19.9 mi, maximum = 47.5 mi
(`parameters.csv`, `run_width_max_mi`). Real runs: 632 multi-section runs; longest single hop 46.5 mi (Codorus State Park).
