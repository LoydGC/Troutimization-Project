# Dashboard concept (sketch, 2026-10-02)

A first idea of what an interactive scenario dashboard could look like once the model exists. **It is a sketch, expected to change a lot.**
Open [`mockups/dashboard_sketch.html`](mockups/dashboard_sketch.html) in a browser (needs internet for Chart.js). Every number in it is a placeholder
from a toy allocator, not model output.

**Real in the sketch:** the 9 hatchery names and their 2026 stream-fish supply (`hatchery_schedule_supply.csv`), and the averaging-error
percentages for the cluster options (`docs/clustering_options.md`). **Placeholder:** the 240 dots standing in for the 1,022 sections, their demand,
the allocation (a greedy cheapest-route fill instead of the Gurobi solve), and every cost, benefit and impact number.

## What each control would need from the real model

- **Hatcheries in service.** Set a hatchery's supply to 0 and re-solve. Needs the `hatcheries` table (Prompt 7), with the 9 producing flagged.
  The 4 non-producing ones could be switched on (the "more hatcheries" extension).
- **Cost of a truck mile.** `cost_per_truck_mile` in `parameters.csv` with its low and high values (not there yet; Prompt 7 step 2).
- **Sections out at random.** Each section is a random variable that may be dropped from the candidate set, then re-solved many times. Needs
  fast solves or a precomputed batch of draws; the result is a spread, not one plan.
- **Cluster approach.** Swap the section-to-cluster labelling (Nate's `section_schedule.cluster_id`, or Gavin's `section_medoid_clusters` and
  `section_hierarchical_clusters`) with the downstream math held fixed (`docs/clustering_options.md`). The step that turns a labelling into a
  representative cost is not built yet.
- **Transport budget.** The epsilon-constraint on transport cost; sliding it walks along the trade-off curve.
- **Map colour.** Reads the solution `x[h, s]`, `cost[h, s]` and the wild-trout weights in `environment`.
- **Cards and trade-off chart.** The three objectives (angler benefit, transport cost, wild-trout impact), kept separate, as the model design says.
- **Hatchery use.** Fish used divided by `supply_h`.

## Things to remember when reading the sketch

- "Lose Bellefonte" shows total cost falling because fewer fish get delivered while benefit drops. A real version should also show cost per
  fish delivered so that does not read as a saving.
- Cluster error is applied as noise on the costs the allocator sees; the reported cost uses the exact costs. That is the idea, not the real method.

## Open questions for a real version

- Live (re-solve in the browser or a small server) or precomputed (the model writes a results file for a grid of scenarios and the page only
  reads it)? Precomputed is much simpler for a class presentation.
- Which scenarios matter most for the report? The sketch has hatchery outage, fuel cost, random section loss, cluster choice and budget.
- A results file would need, per scenario: the settings, the objective values, and the solution `x[h, s]` as a long table.
- Where it lives (static page in the repo, an artifact, a notebook) and who builds it.
