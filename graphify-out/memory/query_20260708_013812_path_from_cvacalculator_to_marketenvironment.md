---
type: "path_query"
date: "2026-07-08T01:38:12.990944+00:00"
question: "Path from CVACalculator to MarketEnvironment"
contributor: "graphify"
source_nodes: ["CVACalculator", "NettingSet", "MarketEnvironment"]
---

# Q: Path from CVACalculator to MarketEnvironment

## Answer

CVACalculator references NettingSet, which references MarketEnvironment (2 hops). NettingSet is the bridge: CVA operates on a netting set (trades under one ISDA/CSA), which must be revalued per time-step against a bumped MarketEnvironment under Hull-White to simulate EPE/ENE. Alternative longer path routes through Swap -> Instrument::pv() -> MarketEnvironment, the polymorphic valuation flow P5 fixed.

## Source Nodes

- CVACalculator
- NettingSet
- MarketEnvironment