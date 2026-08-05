# Options Volume, Open Interest, and Directional Sentiment Data

> Purpose: serves as the options-data interpretation boundary and implementation basis for the `stock-analysis-debate` Skill. This document summarizes the OIC, OCC, and Cboe primary sources; it does not replace the originals and does not constitute investment advice.
> Verified against sources: 2026-08-06

## 1. Summary of conclusions

1. **Volume measures trading activity that occurs over a period of time; Open Interest (OI) measures the outstanding stock of contracts still open after clearing. The two are not the same dimension.**
2. **Volume, OI, or volume/OI alone cannot establish opening, closing, trade-aggressor direction, strategy, or investor identity.** How OI changes depends on the open/close designations of both the buyer and the seller.
3. **Every open contract simultaneously has a long and a short side.** A high or low call/put OI by itself implies neither bullish nor bearish.
4. **Directional flow requires additional trade-level execution data and filtering rules.** Cboe's directional product classifies executions by their position relative to the midpoint/bid/ask and excludes complex, late, and tied trades; its fields go far beyond a plain option-chain snapshot.
5. **The OI in OCC Series Search is the result of the previous trading day's settlement matching, not an intraday real-time measure of openings.** Therefore the ratio of same-day volume to that OI can only be described as "elevated same-day activity relative to prior-settlement OI".
6. **The current Skill's IV comparison is an approximate ±5% spot-moneyness proxy.** It can describe the relative IV between two selected strikes, but it cannot masquerade as Cboe's fixed-tenor, fixed-delta normalized skew.

## 2. OIC General Information FAQ

Source: [OIC General Information FAQ](https://www.optionseducation.org/referencelibrary/faq/general-information)

### 2.1 OI increasing does not mean bullish or bearish

The FAQ explains that OI is the number of long or short contracts that have not yet been closed out. The same contract corresponds to both a buyer and a seller, so the observed OI provides no net direction: a call buyer may be bullish, while the call seller on the same contract may hold the opposite view.

Constraints for the Skill:

- Must not present high call OI as "net bullish positioning".
- Must not present high put OI as "net bearish positioning".
- The put/call OI ratio can only describe the call/put composition of outstanding contracts.

### 2.2 How OI changes depends on the open/close combination of both sides

The clearing relationship given by the FAQ can be summarized as:

| Buyer designation | Seller designation | OI change after clearing |
|---|---|---|
| Buy to open | Sell to open | Increase |
| Buy to open | Sell to close | Unchanged |
| Buy to close | Sell to open | Unchanged |
| Buy to close | Sell to close | Decrease |

This shows that the same same-day volume can map to entirely different OI outcomes. New OI is only available after exchange reports are matched and cleared by the OCC at end of day.

### 2.3 Volume/OI alone cannot prove liquidity either

The FAQ links liquidity to the ease of entering or exiting a position at a fair price; more direct observations include bid/ask width and the quoted size on both sides. A higher volume/OI may accompany more market participation, but it cannot guarantee that a given contract currently has sufficient liquidity.

Constraints for the Skill:

- Most-active or high OI may describe where historical/same-day activity concentrates.
- Must not claim "sufficient liquidity" or "institutions can trade large size" solely from volume/OI.

### 2.4 Meaning of open and close

- Opening purchase: establishes or increases an options long.
- Opening sale: establishes or increases an options short.
- Closing purchase: reduces or eliminates an options short.
- Closing sale: reduces or eliminates an options long.

A plain aggregate option chain does not provide these order intents, so they cannot be inferred backwards from volume/OI.

## 3. OIC "Open Interest: Why It Matters"

Source: [Open Interest: Why It Matters](https://www.optionseducation.org/news/open-interest-why-it-matters)

### 3.1 Volume and OI are produced by different processes

The article defines volume as activity within a trading session and OI as the cumulative contracts still open. The OCC consolidates the opening and closing trade reports provided by the exchanges and also accounts for the elimination of contracts through exercise and assignment, ultimately producing the settled OI.

### 3.2 All four trade intents are required

Direction and OI change require distinguishing:

- buy to open;
- buy to close;
- sell to open;
- sell to close.

If both sides open, OI increases; if both sides close, OI decreases; if one opens and the other closes, it is only a transfer of position and OI is unchanged. It follows that `volume > 2 × OI` does not equate to "massive new opening".

### 3.3 Reasonable uses of OI

The article holds that OI can be used to observe market depth and participation, and to look for clues in day-over-day OI changes. The keyword here is "clues", not proof of direction, strategy, or participant identity.

Constraints for the Skill:

- May describe OI level, contract distribution, and cross-day changes.
- If next-settlement-day OI becomes available in the future, the net change may be described, but the open/close breakdown of both sides still cannot be determined from the net change alone.
- Without cross-day OI, must not claim an OI trend.

## 4. Cboe Option Sentiment Specification

Source: [Cboe Option Sentiment Specification v1.4](https://datashop.cboe.com/Documents/Cboe_OptionSentiment_Specs.pdf)

### 4.1 Why professional directional data needs more fields

The Cboe document contains not only call/put volume and OI, but also:

- call/put trade counts and average trade size;
- call/put premium;
- offer-side `calls_bought`, `puts_bought`;
- bid-side `calls_sold`, `puts_sold`;
- `call_premium_bought/sold`, `put_premium_bought/sold`;
- `net_option_delta` and `directional_pct` for directional trades;
- customer, firm, and market maker volume;
- trade-size buckets, DTE buckets, moneyness buckets, and per-exchange volume.

This shows that aggregate call/put volume is only one of the basic fields for directional analysis and cannot substitute for directional fields.

### 4.2 How Cboe defines direction

Cboe classifies trades by the position of the execution price relative to the midpoint: executions above the midpoint are treated as buys, executions below the midpoint as sells. It also excludes spread, late, and tied trades, and backs cancelled executions out of the totals.

Constraints for the Skill:

- The current yfinance snapshot has only aggregate volume, OI, last price, and a quote snapshot — no full trade-by-trade tape or the filtering flags above.
- The current Skill must not fabricate substitutes such as `calls_bought`, `puts_bought`, net delta flow, or buyer-initiated premium.
- The position of a single last price relative to the current bid/ask cannot represent the direction of the day's cumulative volume.

### 4.3 Cboe's skew convention

Cboe provides `norm_25d_skew_30`, a normalized 30-day, 25-delta put-call skew. It holds tenor and delta fixed, making cross-underlying and cross-date comparisons more consistent.

The current Skill selects, within the same expiry, the put/call strikes closest to spot ±5%, which can only be labeled as:

```text
Approximate ±5% spot-moneyness IV difference
```

It may describe "the selected put-side IV is higher/lower than the call-side IV", but it is prohibited from being called a 25-delta skew, a normalized risk reversal, or a flow direction.

### 4.4 File timing

The Cboe specification distinguishes a preliminary file delivered the same evening from a complete file delivered the next morning. This further shows that rigorous trade-direction aggregation requires end-of-day processing and data cleansing, rather than relying only on an option-chain snapshot at a single point in time.

## 5. OCC Series Search

Source: [OCC Series Search (AAPL example)](https://www.theocc.com/market-data/market-data-reports/series-and-trading-data/series-search?symbol=AAPL&symbolType=U)

### 5.1 What the page provides

Series Search displays OI by underlying, contract date, strike, and call/put, and lists the relevant exchanges. AAPL is only a query example; it does not mean the conclusions here apply only to AAPL.

### 5.2 Time basis

The page states that OI comes from the previous trading day's settlement. For example, what you see on Friday morning is the OI after Thursday's trades were matched and settled. Therefore:

- intraday volume is the cumulative activity of the current day;
- the OI on the same screen is typically prior-settlement OI;
- `volume / OI` is an activity ratio across different time bases, not a "same-day newly-opened ratio".

Constraint for the Skill: output must use `prior OI` or `prior-settlement OI`; terms such as `fresh OI` or `new positions` are not allowed.

## 6. Allowed and prohibited statements for the current Skill

| Data | Allowed statements | Prohibited statements |
|---|---|---|
| Call/put volume | composition of same-day activity, where volume concentrates | net bullish/bearish capital inflows, buyer-initiated direction |
| Call/put OI | composition of prior-settlement open contracts | net long, net short, institutional positioning |
| Volume > 2× prior OI | activity elevated relative to existing OI | freshly opened, new money, direction of opening |
| Most-active strike | volume concentrated at a specific expiry/strike | speculation, hedging, institutional or retail identity |
| Approx. ±5% moneyness IV difference | relative IV pricing of the selected puts/calls | normalized 25-delta skew, definitive flow direction |
| Single yfinance snapshot | cross-sectional observation | historical trend, day-over-day OI change |

The final status of options analysis uses:

```text
OPTIONS EVIDENCE: Available / Limited / Not Rated
```

It only indicates whether the data is sufficient to describe activity and implied pricing. It does not represent a Bullish/Bearish direction and does not directly authorize a stock rating, target price, position size, or risk limit.

## 7. Minimum data requirements before restoring directional flow

Directional output should only be re-evaluated if a future data source provides at least the following capabilities:

1. Trade-by-trade execution prices with the contemporaneous bid/ask or midpoint;
2. Open/close designations, or verifiable cleared open/close data;
3. Filters for complex, spread, late, tied, and cancelled trades;
4. Coverage of directional executions;
5. Next-settlement-day OI with an explicit timestamp;
6. To judge participant type, account-class data such as customer/firm/market-maker is also required.

Even when these conditions are met, direction must be labeled with its methodology, coverage, and confidence, and execution direction must not be automatically equated with a final stock view.

## 8. Supplements and refinements (added after re-verification against sources on 2026-08-06)

The items below change none of the conclusions above; they add details confirmed while re-checking the primary sources, so that future Skill extensions avoid misuse.

### 8.1 Mixed time bases within the snapshot

On the yfinance chain, bid/ask/lastPrice are near real-time, while openInterest is prior-settlement. Within the same row the two columns sit on different time bases, so `volume / OI` is a cross-time-base activity ratio (see §5.2). yfinance OI may be 0 or stale when fetched after hours or over a weekend; `options_flow.py` already downgrades "whole-chain OI missing" to Not Rated. When interpreting, must not conclude "no positions in this contract" just because OI=0 — it may be missing data in the snapshot.

### 8.2 Cboe directional fields cover only the directional subset

In the Cboe spec, `net_option_delta`, `calls_bought/sold`, and `puts_bought/sold` count only directional trades (Note 3 excludes spread/late/tied trades). The spec's `directional_pct` field reads "percent of option volume that is directional (noncomplex, not late)", formatted like 98.011 instead of 0.98011. When this data becomes available, directional totals must be divided by that coverage ratio; the spec's claimed initiating-side identification scale of roughly 5 million executions per day does not mean every market execution carries a direction. This is the exact semantics of §7 item 4, "coverage of directional executions".

### 8.3 Delta drift of the ±5% moneyness proxy — not comparable across underlyings

The 25-delta anchor point drifts with the IV environment: at low-IV underlyings (~15% vol), ±5% moneyness maps to roughly 15-20 delta; at high-IV underlyings (~50% vol) it may map to 30-35 delta. The approximation therefore mixes moneyness and IV-environment changes and may only describe relative IV within the same underlying and the same expiry (see §6). Direct cross-underlying or cross-tenor comparison is prohibited, and it must not be treated as a 25-delta risk reversal.

### 8.4 OI concentration should be analyzed in two dimensions (expiry × moneyness)

The Cboe spec provides `otm_call_oi`/`otm_put_oi` and itm/atm/otm volume buckets, and states that OI supports "concentration analysis". High OI does not imply direction, but where OI concentrates at an "expiry × strike" combination is usable for concentration observation. The current Skill only takes the two nearest expiries; interpretation should break down by expiry rather than reporting only the aggregate put/call OI ratio.

### 8.5 Baseline averages are key to anomaly detection

The spec's `avg_call_volume`/`avg_put_volume`/`avg_total_volume` are 20-day moving averages, used as "baseline averages for contextualization of activity". The current Skill has no history and can only make single-point observations; if historical data is integrated later, using same-day volume relative to the 20-day average as a multiple or deviation is a more robust "unusual activity" test than a single-point `vol/OI`.

### 8.6 Volume counting convention

Exchanges/OPRA report volume as the number of contracts traded; a single buyer-plus-seller execution counts once, not once per side. When interpreting §3.2, do not multiply volume by 2 before comparing it with OI changes.

### 8.7 Exercise/assignment reduces OI near expiration

The OIC article is explicit: contracts that are exercised and result in assignment are eliminated from OI. A large OI decline around expiration is therefore not necessarily a "closing wave" — it may be exercise settlement. This further supports §5.2: without cross-day OI data, must not claim an OI trend.

### 8.8 Premium vs. delta weighting

Cboe provides both dollar premium (`call_premium`/`put_premium`) and `net_option_delta`. Premium mixes OTM/ITM and cannot be used directly as directional strength; directional exposure should use the delta-weighted value. When measuring directional strength in the future, use `net_option_delta`, not premium.

### 8.9 Traditional use of the put/call ratio

The classic put/call ratio (especially the OI version) is often treated as a contrarian/sentiment indicator, but its effectiveness is contested, and index-option volume is dominated by institutional hedging. §6's stance of prohibiting the ratio from being used directly as direction is correct; even if the ratio is computed in the future, it must not be used to separate hedging flow from speculative flow.

### 8.10 Verified versions and sources

- Cboe Option Sentiment Spec v1.4 (0525) re-verified (fetched 2026-07-23): field 51 `norm_25d_skew_30` definition, Note 3 (midpoint direction; excludes spread/late/tied), and Note 4 (cancelled trades backed out) all match the above.
- OIC "Open Interest: Why It Matters" published 2025-10-03.
- OCC Series Search page text: "Open interest figures are derived from the previous day's settlement. ... on a Friday morning represent open interest [from the prior day's settlement]".
