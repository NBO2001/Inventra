# RFC 001 — Receipt-based grocery assistant for Manaus

- **Status:** Draft for discussion
- **Date:** 2026-11-22
- **Initial market:** Manaus, Amazonas, Brazil
- **Product language:** Brazilian Portuguese

## 1. Summary

Build a mobile-friendly website where residents of Manaus import grocery receipts, understand their spending and the *approximate* taxes shown on those receipts, and use their purchase history to plan the next supermarket trip at better observed prices. Cautious replenishment suggestions help assemble the next list. A separate, explicit opt-in lets a person contribute item, price, and store observations to public, search-indexable product and store pages. Personal purchase history remains private.

**Decision:** The core promise combines private spending understanding with a practical recommendation for the next shopping trip. Proceed as a small product experiment, conditional on validating receipt ingestion, usable store coverage, and user demand. Price lookup alone is not a sufficient differentiator in Amazonas.

## 2. Market check

| Product | Relevant current offer | Implication |
| --- | --- | --- |
| [Busca Preço Amazonas](https://buscapreco.sefaz.am.gov.br/sobre), SEFAZ/AM | Free search of prices from NFC-e issued in Amazonas; defaults to receipts from the last 48 hours and supports a period of up to seven days. | Direct, local competitor for public price lookup. Our public pages need a distinct use case, such as interpretable price history or a household shopping list. |
| [Economiza AI](https://economizaai.app/) | Imports NFC-e by QR code, tracks grocery spending, and adds community price comparisons. | Direct overlap with private receipt history and community data. |
| [GoMarket](https://gomarket.app.br/) | Crowdsourced NFC-e prices, nearby store comparison, shopping lists, and rewards. | Further evidence that uploading receipts for price comparison is an existing model. |
| [Maria Econômica](https://mariaeconomica.com.br/) | Receipt scanning, spending control, and local supermarket price comparison. | Validate any claim of novelty before marketing it. |

This is a feature and positioning comparison of public product descriptions, **not** evidence about their usage, data quality, or availability in every Manaus supermarket. The potential opening is a focused Manaus experience that combines a useful private household assistant with transparent, trustworthy public price observations. This remains a hypothesis to test with users.

## 3. Users and jobs

1. **Household shopper:** “Show what I spent, what I may need again, and which supermarket is a better choice for my next trip.”
2. **Price researcher:** “Compare a specific, equivalent product or my shopping list across nearby supermarkets using recent observed prices.”
3. **Contributor:** “Help others compare prices without exposing my identity or full shopping basket.”

## 4. Scope and product rules

### MVP: private experience

1. Create an account and import an Amazonas NFC-e using its QR code or 44-digit access key. Receipt photo import is outside the initial release.
2. Show extracted store, issue date, items, quantity, unit, unit price, discounts, line total, receipt total, and the approximate tax amount **when present**. Let the user review and correct extraction before saving.
3. Reject duplicates using a protected fingerprint of the access key; flag canceled or invalid documents when verification is available. Keep the original and corrected values distinguishable.
4. Show total spending by calendar month across **all** supermarkets used by the shopper, then provide category, store, and product breakdowns within a month. Separate changes in quantity or basket mix from changes in the unit price of the *same comparable product*.
5. Show price history in R$/unit and normalized R$/kg or R$/L where conversion is reliable. Preserve brand, package size, and unit so unlike products are not silently compared.
6. Estimate replenishment with a deterministic algorithm based on repeat purchase intervals and quantities, with no AI or machine learning in the initial version. Label it as “may be running low,” show the last purchase and the rule behind the estimate, and allow dismissing or adjusting it. Require sufficient history; otherwise show no prediction.
7. Read the **approximate tax total printed at the bottom of the NFC-e** and show it for each receipt. The main tax summary sums reported totals by calendar month across **all** supermarkets, with coverage for that month (for example, “8 of 10 receipts reported a value”). A shopper can inspect the underlying receipts, including their supermarkets. If the footer value is absent or cannot be read, mark it unavailable. Do not describe it as exact tax personally remitted, infer a missing amount, or imply a product-level tax breakdown.
8. Let the shopper build the next-trip list from past purchases and replenishment suggestions, with manual add/remove and quantity edits. The shopper chooses the **maximum number of supermarkets** for that trip: 1, 2, 3, …, up to the number of available supermarkets. With 1, estimate the best single supermarket for the complete list; with a larger limit, assign items among up to that many supermarkets to minimize the estimated total cost using recent, comparable observed prices. Show each supermarket's assigned items and subtotal, the estimated trip total, the number of supermarkets used, the comparison with the best single-store estimate, observation dates, and any missing or stale prices. Use fewer supermarkets when adding another does not improve the estimate. Never claim an overall cheapest option when price coverage is insufficient.

### MVP: contribution and public experience

9. Keep contribution **off by default** and ask after each receipt review initially. In settings, let the shopper persist a choice for future receipts: **ask each time**, **share future receipts**, or **do not share future receipts**. Enabling automatic sharing requires a separate, explicit affirmative action that explains the public fields and scope. On each import, show the current sharing choice and allow a one-receipt override before saving. A settings change applies only to future receipts; previously shared observations remain individually withdrawable.
10. Derive public observations containing only normalized product description, brand and package information where known, quantity/unit as needed for comparison, paid item price, store identity/location, and a coarse purchase date. Do not publish receipt image, QR code, access key, consumer name/CPF, payment method, exact time, account ID, or a linkable full basket.
11. Offer public product pages for Manaus with search, comparable variants, supermarket, observed price, normalized price, observation age, and number of observations. Mark all prices as historical observations, subject to change and stock availability. Index pages only when product matching and observation quality pass review criteria; avoid indexing thin or duplicate pages.
12. Support contribution withdrawal by removing that person's public observations and updating affected pages. Explain that search engines may take time to remove cached results.

### Later, after validation

- Travel-distance-aware recommendations, route planning between supermarkets, and more advanced substitutes for missing items.
- Receipt photo import, after testing extraction accuracy, correction effort, and cost.
- Opt-in household collaboration, reminders, and notifications.
- Broader Amazonas coverage, other receipt types, or store integrations.
- Explanations of price trends across the community when there are enough comparable observations.

### Out of scope for MVP

- Claims of live shelf price, stock availability, or guaranteed savings.
- Personalized tax advice or estimating taxes that are absent from a receipt.
- Automatic retrieval of every receipt attached to a CPF.
- Public profiles, full receipt pages, or identifiable purchase timelines.
- Scraping SEFAZ/AM or competing services without confirming access terms and technical permission.

## 5. Main flows

**Import:** Scan QR code or enter key → retrieve/parse receipt → show verification and extraction confidence → user reviews ambiguous lines and the current sharing choice → optionally override sharing for this receipt → save private receipt and, if authorized, contribute item observations.

**Manage:** Open dashboard → inspect monthly spending and approximate tax totals across all supermarkets → drill into category, store, product, and receipt details → inspect a product’s comparable price history → accept or dismiss a replenishment suggestion.

**Plan next trip:** Start with previously purchased items and replenishment suggestions → edit the list and choose a maximum of 1, 2, 3, … supermarkets → compare the best eligible allocation for that limit with a single-store estimate → inspect each store's assigned items, subtotal, item coverage, and price freshness → choose a plan or inspect missing prices.

**Compare:** Search product → choose exact package or normalized unit comparison → see recent observations by supermarket, observation date, and evidence count → open a store or product page.

**Withdraw:** Open contribution settings or a receipt → turn off sharing → remove associated public observations → refresh affected public pages and request search recrawling where supported.

## 6. Data and calculation rules

| Entity | Minimum fields and handling |
| --- | --- |
| Receipt | Owner, protected access-key fingerprint, source, issuer/store, issue date, status, totals, reported approximate taxes, extraction version, verification status. Raw image/QR/key are private and retained only as long as justified by the retention policy. |
| Receipt item | Original label, corrected label, quantity, unit, unit price, discounts, final line total, optional product code/EAN, matching confidence. |
| Canonical product | Brand, product type, variant, net quantity/unit, optional EAN. Match exact EAN where reliable; otherwise use reviewable rules and confidence thresholds. |
| Public observation | Canonical product or clearly labeled raw product, supermarket/branch, observed price and unit, coarse date, source quality, contribution link kept only in private administration for withdrawal. |

- **Unit price:** Use the paid line total after line discounts divided by quantity. Do not hide discounts or compare promotional prices as standard shelf prices.
- **Price change:** Compare the same product and package, or a clearly marked normalized unit price when equivalence is defensible. Show the observation dates and sample size. Avoid an “inflation” claim from a changing basket.
- **Spending:** Use receipt totals for overall spending; use item totals for category breakdown. Show any reconciliation gap caused by receipt-level discounts, freight, rounding, or parsing errors.
- **Taxes:** Use only the approximate tax total reported in each receipt footer. Store the original label and amount for auditability; display a monthly sum across all supermarkets and the number of receipts with an available value. Do not allocate that total to products or calculate a replacement value. See [Law 12.741/2012](https://www2.camara.leg.br/legin/fed/lei/2012/lei-12741-8-dezembro-2012-774745-normaatualizada-pl.html) and the [NFC-e DANFE guidance](https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=DdSDvm4LtCI%3D).
- **Replenishment:** For each comparable product, compute the median interval between purchases. Require at least three purchases spanning two intervals. Suggest replenishment when elapsed time since the last purchase reaches that median interval; adjust for purchased quantity only if there is enough consistent quantity history to do so reliably. Show the last purchase, typical interval, and estimated next purchase date. Allow the shopper to dismiss or adjust the suggestion. Never imply that actual household inventory is measured. This is a fixed, explainable rule, not AI or machine learning.
- **Next-trip comparison:** Treat the shopper's store count as an upper bound, not a target. Assign each listed item to at most one supermarket with a recent, comparable observed price for the requested quantity; minimize the sum of observed item prices subject to the store limit. Prefer fewer stores when estimated totals tie. Show unpriced items separately and do not count them as savings. Prices are past observations, not stock guarantees, and the estimate excludes travel cost. If no plan covers enough of the list with trustworthy prices, show partial comparisons without a “best supermarket” claim.

## 7. Privacy, trust, and legal review

The [LGPD](https://planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm) requires a valid purpose and appropriate safeguards for processing personal data. Its consent rules require a specific, informed, affirmative choice and an easy way to revoke it; the [ANPD explains data subject rights](https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados-1/direito-dos-titulares). Have Brazilian privacy counsel review the final basis, notices, retention, vendor contracts, and withdrawal behavior before launch.

- Separate private receipt processing from public contribution. Default to asking for each receipt; allow a persistent choice for future imports only through settings. Record the consent text/version, timestamp, active setting, and any one-receipt override for each contribution.
- Strip consumer fields before creating public data. Do not treat removal of a CPF alone as proof of anonymity: rare purchases, exact times, and full baskets can still identify someone indirectly.
- Publish item-level observations independently rather than a public receipt page. Consider aggregation or suppression for rare or sensitive products after testing re-identification risk.
- Encrypt private receipt data, restrict administrative access, rate-limit import and search, and provide account export/deletion paths.
- Document source provenance and confidence. The [SEFAZ/AM consumer portal](https://portalnfce.sefaz.am.gov.br/consumidor/consulte-sua-nota/) supports checking NFC-e by QR code or key, but that does **not** establish a bulk import API or permission to automate it. Validate a permitted, reliable import method before promising one-tap scanning.
- A removed public observation may persist in third-party search caches for some time. State this clearly in the consent screen.

## 8. Minimum acceptance criteria

1. A shopper can import a valid Manaus supermarket NFC-e, inspect every item and total, correct parsing mistakes, and find the saved receipt later.
2. Importing the same receipt twice does not double-count spending or public prices.
3. Monthly spending and approximate tax sums include receipts from every supermarket used in that month. Spending reconciles to saved receipt totals; missing approximate tax fields are excluded and coverage is visible.
4. Price history does not merge different brands or package sizes without an explicit, labeled normalized comparison.
5. Replenishment appears only with enough repeat data and states its uncertainty.
6. A shopper can turn prior purchases into an editable next-trip list and set a maximum of 1, 2, 3, … supermarkets. With 1, the result is a single-store estimate; with a larger limit, the list is split among no more than that many stores, with items and subtotals per store and a comparison against the single-store estimate. Missing prices and observation dates remain visible. A low-coverage plan is never presented as definitively cheapest.
7. Public contribution defaults to a per-receipt decision. A user can explicitly persist a future-sharing preference in settings, see it during import, and override it for one receipt. Public pages and metadata expose none of the prohibited private fields or full basket linkage.
8. Withdrawing a contribution removes its observations from product/store pages and search indexes under the site's control.
9. Public prices show store, product variant, observed date, and a “price may have changed” notice.

## 9. Validation plan and launch gates

1. **Receipt feasibility:** Test a small, consented sample of Manaus supermarket receipts from different stores. Measure successful retrieval, item accuracy, tax-field availability, canceled-document handling, and manual correction time. Do not put real receipt contents in the public repository.
2. **User value:** Interview 8–12 Manaus shoppers. Prototype the spending dashboard and next-trip list comparison; ask whether this combined flow would make them return after the first import. Measure willingness to opt into public contribution separately.
3. **Competitive differentiation:** Have testers compare the next-trip planning flow and proposed public page with Busca Preço Amazonas for the same shopping task. Proceed with public pages only if they solve a clear unmet task or present meaningfully better context.
4. **Privacy and source review:** Approve consent wording, withdrawal behavior, data retention, and the receipt retrieval method before a public beta.
5. **Initial beta:** Launch private history first if price data is sparse. Publish comparison pages when product matching and observation freshness are credible; no empty pages for SEO.

Suggested early metrics: percentage of receipts imported without correction, median correction time, week-four return rate, percentage of users who opt into sharing, percentage of public observations confidently matched, and proportion of searches with a recent comparable price.

## 10. Open decisions

- Can a reliable, permitted NFC-e retrieval method provide item details and reported taxes for the supermarkets in scope? What is the fallback if a source blocks automation?
- Which supermarket branches and product categories should the Manaus pilot cover first?
- Should contributors select individual items to exclude, in addition to the per-receipt choice?
- What minimum evidence and freshness threshold makes a public comparison useful without exposing sparse purchase patterns?
- What minimum proportion of a shopping list needs recent, comparable prices before the product can recommend one or several supermarkets? Test the threshold with Manaus shoppers.
