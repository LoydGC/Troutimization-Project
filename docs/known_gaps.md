# Known gaps

## Our stocking data vs PFBC's published totals
Source: PFBC 2024 Annual Report, "Trout Stocked by PFBC", fiscal year July 2023–June 2024
(`data/references/2024annualreport.pdf`).

The report's **4,699,507 trout stocked** = 3,143,145 adults + 1,556,362 fingerlings. A further 1,135,658
fingerlings went to co-op nurseries, making 5,835,165 including co-ops.

Our stream layers only cover **adult trout in stream sections**. Stocking year 2024 is 2,599,733 fish,
about 83% of the report's adults:

| Species | Report (FY23–24 adults) | Our 2024 stream sections | Share |
|---|---|---|---|
| Brook | 184,374 | 74,675 | 41% |
| Brown | 894,027 | 664,285 | 74% |
| Rainbow | 2,049,362 | 1,785,740 | 87% |
| Golden rainbow | 15,382 | 11,723 | 76% |
| Brood (listed separately in our layer) | — | 63,310 | |
| **Adults** | **3,143,145** | **2,599,733** | **83%** |

**Why they differ:**
1. **Fingerlings (1.56M) are a different program.** They're small fish, mostly for lakes and larger
   waters, and they aren't in the adult stocking layers (all rows are `SpeciesLifestage = ADULT`).
   They're out of scope; CLAUDE.md treats fingerlings and co-ops as fixed.
2. **Lakes: most of the ~543k adult gap (likely).**
   - About 131 stocked lakes get adult trout, but no PFBC GIS service has lake counts. Checked
     2026-09-26: the 2024, 2025 and 2026 stocked services each hold one stream-section layer, and
     `PFBC_Stocked_Trout_Waters` lakes have no counts.
   - Brook trout have the lowest stream share (41%), which fits heavy lake or other non-stream use.
     *Unverified.*
3. **The years are defined differently.** The report covers fiscal year Jul 2023–Jun 2024 (fall 2023 plus
   spring 2024); the layer covers the 2024 stocking year. Our three years are similar (2.60M, 2.63M,
   2.62M), so this likely matters little.
4. **Brood fish** are a separate field in our layer. The report probably counts them within each
   species. *Unverified.*

**Implications for the model:**
- The decision covers about 83% of PFBC's adult trout: the stream allocation.
- Hatchery supply must be scaled to the **stream** total (baseline stream fish × each hatchery's share),
  not the report's 3.14M. Otherwise the supply constraints are about 20% too loose.
- Lakes stay out of the decision until we find counts. Options:
  - a PFBC records request
  - the stocking schedule pages (event lists)
  - treating lakes as fixed demand that uses up hatchery capacity
