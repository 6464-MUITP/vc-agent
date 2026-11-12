# Competitor Analysis Agent

A Python agent that takes a company name, finds its competitors, researches each one,
and produces a sourced comparison table, a 1-5 scorecard, and a short written memo.

## What it does

1. Finds the target company's direct competitors (independent startups, not big-tech products).
2. Locates each company's official website and searches that site for pricing, features and customers.
3. Searches the wider web for reviews, news and comparisons.
4. Extracts a fixed set of fields, each with a source URL and a word-for-word quote.
5. Checks that every quote really appears in the retrieved text, and tags the source
   (primary, press, data, social, other).
6. Scores each company 1-5 on five criteria and writes a comparison memo.

## Why the verification step exists

Language models often attach a plausible link to a number that is not on that page.
Requiring a copied quote, then checking it in code, caught real errors during testing
(for example a valuation that did not match its source). Weak sources such as Wikipedia
are blocked, and anything unverified is flagged `CHECK`.

## Setup

```bash
git clone https://github.com/[6464-MUITP]/[vc-agent].git
cd [vc-agent]
pip install -r requirements.txt
```

Create a `.env` file:

```
GROQ_API_KEY=your_key
TAVILY_API_KEY=your_key

```

Both have free tiers (console.groq.com, tavily.com).

## Usage

```bash
python main.py "Perplexity AI"        # target + 4 competitors
python main.py "Perplexity AI" 3      # target + 3 competitors
```

Outputs: `comparison_*.csv`, `full_data_*.json` (all evidence), `memo_*.md`.

To retarget the scorecard for a different audience, edit the `CRITERIA` dictionary in `main.py`.

## Sample output

[**Competitive Memo – Perplexity AI vs. Core Search‑AI Players**  
*Prepared for VC review – 350 words max*

---

### 1. Positioning (one‑liner per company)

| Company | Target Customer | How It Differentiates (marketing claim) |
|--------|----------------|------------------------------------------|
| **Perplexity AI** | Developers & businesses embedding an AI answer engine | Real‑time web‑grounded answers with verifiable citations; “Perplexity Computer” for autonomous ad spend. |
| **You.com** | Knowledge workers (law, consulting, journalism, academia, enterprises) needing deep research | Web‑Search API that “surfaces the most up‑to‑date and relevant information” with zero data retention and BYOK encryption. |
| **Elicit** | Institutes and companies at scale | “Most accurate AI product for scientific research”; finds up to 1,000 papers & analyzes 20,000 data points. |
| **Consensus AI** | Students, researchers, policy professionals, science writers | Academic‑search engine that filters by journal tier (Q1‑Q4) and displays a “consensus meter”; HIPAA‑compliant NLP. |

2. Scorecard Takeaways (who leads on each criterion)  

| Criterion | Leader(s) (score = 5) | Comments |
|-----------|----------------------|----------|
| **Clear customer** | **Perplexity AI, Exa, You.com** (5) | All three articulate a specific buyer persona.|
| **Pricing clarity** | **Perplexity AI, Exa, You.com, Kagi** (5) | Transparent tiered or pay‑per‑request models; Tavily lags (2). |
| **Specific differentiation** | **Perplexity AI, You.com, Kagi** (5) | Each markets a unique hook (cited answers, LLM‑agnostic API, privacy). |
| **Proof** | **Exa** (5) – strongest public evidence; **You.com** (4) moderate; others unknown. |
| **Momentum** | **Exa** (5) – most recent partnership & developer traction; **You.com, Kagi, Tavily** (4);Perplexity AI unknown. |]


## Limitations

- Data comes from search snippets, not full pages, so details can be missed.
- Product and differentiator claims mostly reflect company marketing, not independent proof.
- Scores are a model's judgement from the profile data, not facts.
- Funding, valuation and headcount are deliberately excluded because free web search is
  unreliable for them. A paid source such as Crunchbase or PitchBook would be needed.
- Uses free-tier models and APIs, so rate limits apply.
- Output accuracy has not been systematically tested. Check the `CHECK` flags and source links before relying on any value.
