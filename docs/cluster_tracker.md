# Cluster journey: running tracker (Gavin)

The story of how we got to the cluster options, kept in order so it can be presented. Newest entry goes at the bottom.
Current state and definitions: [`clustering_options.md`](clustering_options.md). The hero picture for a slide is
`outputs/figures/method_comparison/options_overview.png` (regenerate: `python scripts/16_compare_methods_map.py`).

**To add an entry:** copy the template at the bottom, fill in the four lines (tried / saw / learned / decided), link one picture.

---

## 1. Starting point: Nate's schedule clusters (2026-09-28)
- **Tried:** group sections PFBC stocks on the same truck runs (run = date + hatchery + meeting place + time; link when two
  sections share at least half the runs of the less-visited one).
- **Saw:** 351 clusters, 103 sections alone, biggest 18 sections, widest 57 mi.
- **Learned:** it reflects what PFBC did, so it also carries PFBC's hatchery choices, which the model is meant to choose.
- **Decided:** keep as the reference and as the Phase 1 clusters (plan of record, 2026-10-01).
- Picture: `outputs/figures/medoid_clusters/approach_comparison.png` (left column).

## 2. Geography only: real road distances between sections (2026-09-29)
- **Built:** OSRM road miles between all 1,022 x 1,022 stocked sections (script 12), checked: 9 of 9 validation checks pass.
- **Learned:** real road miles are about 1.5x the straight line at short range, not Nate's flat 1.3. This is what makes
  schedule-free clustering possible.

## 3. k-medoids on road miles vs Nate's (2026-09-30)
- **Tried:** k-medoids (centers are real sections) at Nate's count of 351.
- **Saw:** silhouette 0.38 vs 0.12, widest cluster 28 mi vs 57 mi. Nate's biggest cluster (18 sections) splits into 7.
- **Learned:** pure geography gives much tighter groups, but nothing stops a cluster growing large or wide.
- Picture: `outputs/figures/medoid_clusters/approach_comparison.png`, `silhouette.png`.

## 4. How many clusters? Sweep, then limits from real runs (2026-09-30)
- **Tried:** k from 10 to 800; compared against what real truck runs look like (632 multi-section runs).
- **Saw:** silhouette plateaus around 250 to 400 clusters; real runs have a median width of 8.4 mi, a 90th percentile of 19.9 mi
  and a maximum of 47.5 mi, with at most 7 sections (90% have 3 or fewer).
- **Decided (then):** k-medoids plus limits of 20 mi and 4 sections gives 407 clusters (script 13).
- Picture: `outputs/figures/medoid_clusters/approach_comparison.png`.

## 5. Turning point: a cluster is a cost, not a trip (2026-10-01)
- **Objective on record:** a cluster groups sections that cost about the same to reach from every hatchery and supplies one
  representative cost per hatchery. Nothing is routed or assigned to a cluster; the model still decides `x[h, s]`.
- **Learned:** trip-style limits (width, hops, section count) are not the right yardstick. They described a truck run. What
  matters is how close a cluster's average cost is to each member's own cost.
- **Decided:** width, hop and size limits superseded; the geography-only options kept on the table.

## 6. DBSCAN: a useful dead end (2026-10-01)
- **Tried:** DBSCAN at eps 19.9 and 47.5 mi (the real-run width numbers).
- **Saw:** one cluster covering the whole state, at both settings.
- **Learned:** eps is how far a section may sit from its nearest cluster-mate, not a cluster width, so clusters chain along
  streams. DBSCAN only behaves at eps near 6 mi (482 clusters, 271 alone), where it flags remote sections.
- **Decided:** scrapped. Its script and figures were removed on 2026-10-03; they are in git history (commit `38e0b8a`: `scripts/14_dbscan_clusters.py`,
  `outputs/figures/dbscan_clusters/`). The overview still shows the eps 6 mi result (card 6).
- Picture: `outputs/figures/method_comparison/options_overview.png` (card 6).

## 7. Width-limited clustering (2026-10-01)
- **Tried:** hop + size + width limits (405 clusters, the same as script 13), then width only with complete linkage.
- **Saw:** width 19.9 mi gives 234 clusters, silhouette 0.42, but averaging error 2.8% (vs 1.7% for script 13). Width 47.5 mi gives
  74 clusters and doubles the error to 5.7%.
- **Learned:** the hop limit changed nothing (sections link into 3 groups at 17.7 mi); size cap matters only for trucks, not cost.
- **Decided (then):** keep 19.9 mi as a sensitivity candidate; 47.5 mi is an upper bound only. (Superseded: entries 10 to 12.)
- Picture: `outputs/figures/hierarchical_clusters/metrics.png`.

## 8. Plan of record (2026-10-01)
- **Phase 1:** Nate's clusters. **Sensitivity:** Gavin's, once settled. Clusters are interchangeable labelings; the math applied
  to them afterwards is a separate step.
- **Considered and dropped:** clustering the cost vectors directly (an option #7). Not built; the six options stand.
- Picture: `outputs/figures/method_comparison/options_overview.png`, `single_section_trips.png`.

## 9. Plain k-medoids with the count set by silhouette (2026-10-01)
- **Tried:** drop the "match Nate's 351" count. Run k-medoids for every k from 20 to 700 and keep the one with the best silhouette.
- **Saw:** best at k = 310 (silhouette 0.39, 54 sections alone, widest 32 mi, averaging error 2.2%). The curve is a plateau: every k from
  240 to 330 is within 0.01 of the best, and two runs at the same k differ by about 0.007.
- **Learned:** "best silhouette" does not pick a sharp winner; any count in that range is equally good by this measure.
- **Decided:** option 2 is now this version. The 351-cluster one is retired.
- Picture: `outputs/figures/medoid_clusters/silhouette.png` (green dot), `outputs/figures/method_comparison/options_overview.png`.

## 10. Hierarchical with the count set by silhouette replaces the 47.5 mi version (2026-10-01)
- **Tried:** cut the same complete-linkage dendrogram at every k from 20 to 700 and keep the best silhouette, with no width or size limit.
- **Saw:** best at k = 309 (silhouette 0.44, 31 alone, widest 15.6 mi, averaging error 2.2%). A plateau again: every k from 269 to 392 is
  within 0.01.
- **Learned:** with no limits, silhouette alone picks a cut tighter than the 19.9 mi limit (widest 15.6 mi) and scores better than any
  limit-based version.
- **Decided:** it replaces the width 47.5 mi example in the comparison. The 47.5 mi result (74 clusters, silhouette 0.34, averaging error
  5.7%, "too wide") stays on record in entry 7 and in `clustering_options.md`.
- Picture: `outputs/figures/hierarchical_clusters/metrics.png`, `outputs/figures/method_comparison/options_overview.png`.

## 11. Same limits for k-medoids and hierarchical (2026-10-01)
- **Tried:** give the hierarchical method the same limits as k-medoids (20 mi wide, 4 sections), so the two are compared like for like.
  The tree is walked from the top and split at the first merge that breaks either limit.
- **Saw:** hierarchical + limits gives 375 clusters (k-medoids: 407), 40 sections alone (95), silhouette 0.38 (0.35), averaging error
  1.9% (1.7%). Widest cluster 20 mi, biggest 4 sections, as set.
- **Learned:** under identical limits the two methods are close; hierarchical needs about 8% fewer clusters and leaves far fewer
  sections alone, while k-medoids has a slightly smaller averaging error.
- **Decided:** option 5 is now hierarchical + limits (options are ordered baseline then limited for each method: k-medoids #2, #3; hierarchical #4, #5). The width-only versions (19.9 mi: 234 clusters; 47.5 mi: 74 clusters) stay on
  record in entries 7 and 10, in `clustering_options.md` and as reference rows in `comparison.csv`.
- Picture: `outputs/figures/method_comparison/options_overview.png`, `outputs/figures/hierarchical_clusters/metrics.png`.

## 12. Housekeeping: limits become a reference; renames; hatchery list from the data (2026-10-01)
- **Decided:** width, hop and size do not matter for the objective. The 20 mi / 4-section limits (options #3 and #5) stay as a tertiary
  reference to show we considered them. The candidates are the no-limits best-silhouette versions (#2 k-medoids, #4 hierarchical).
- **Hatchery check:** averaging error is graded over the hatcheries that produce fish in the 2026 schedule: 9 of the 13 (Linesville and
  Pleasant Mount have 0 stream fish). Read from `hatchery_schedule_supply.csv` (`stream_fish_2026 > 0`), not hard-coded. The numbers did not change.
- **Renamed:** script 15, its outputs and its table said "run_limited", which no longer describes it. Now
  `scripts/15_hierarchical_clusters.py`, `data/processed/section_hierarchical_clusters`, `outputs/{figures,tables}/hierarchical_clusters/`.
  Table columns: `silhouette_best_cluster_id`, `limits_cluster_id`, and the reference-only `width_only_19_9_cluster_id`,
  `width_only_47_5_cluster_id` (formerly `tight_`/`loose_cluster_id`).
- Picture: `outputs/figures/method_comparison/options_overview.png`.

## 13. Cleanup pass (2026-10-01)
- **Fixed:** "trip" wording in the figures and scripts (a cluster is not a trip), the algorithm-family descriptions, a seed claim in
  script 13 that had not been verified, and the `cluster_start_k` note. Script 14 is marked scrapped.
- **Documented:** the new cluster tables and both road-distance tables in `data_dictionary.md`; OSRM in `source_inventory.md`,
  `data_methods.md` and `known_gaps.md` (including the CLAUDE.md rule 3 waiver); tests in `tests/test_clusters.py`.

## 14. Pruning pass (2026-10-03)
- **Removed:** the scrapped DBSCAN script, figures, tables and log; the older two-panel `medoid_clusters/maps.png` and three-panel
  `hierarchical_clusters/maps.png`, which the overview and the same-18-sections comparison now cover. All are in git history (commit `38e0b8a`).
- **Kept as the presentation set:** `options_overview.png`, `approach_comparison.png`, `single_section_trips.png`, `silhouette.png` and the scores
  chart `hierarchical_clusters/metrics.png`.

---

## Slide storyline (draft)
1. **The question:** the model needs one cost per group of similar sections. Which sections go together? *(overview figure)*
2. **What PFBC does:** Nate's schedule clusters. Faithful, but frozen to PFBC's hatchery choices. *(entry 1)*
3. **What geography says:** same sections, real road miles. Tighter, and free of the schedule. *(entry 3)*
4. **What we tried that did not work:** DBSCAN chains the whole state into one blob. *(entry 6)*
5. **What the cluster is really for:** a cost, not a trip; the yardstick changes. *(entry 5)*
6. **Where we landed:** Nate's for Phase 1, ours as a sensitivity. *(entry 8, overview figure)*

Good pictures to reuse: `options_overview.png` (hero), `single_section_trips.png` (who gets left alone), the zoom panels in
`outputs/figures/medoid_clusters/approach_comparison.png` (Nate's biggest cluster splitting), the DBSCAN card on the overview (the one-blob dead end is in git history).

## Entry template
```
## N. Title (date)
- Tried:
- Saw:
- Learned:
- Decided:
- Picture: <path>
```
