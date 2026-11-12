from dotenv import load_dotenv
load_dotenv()

import os
import sys
import csv
import json
import time
from datetime import date
from urllib.parse import urlparse
from groq import Groq
from tavily import TavilyClient

client = Groq(timeout=60, max_retries=3)
tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
MODEL = "openai/gpt-oss-120b"

FIELDS = [
    "what_it_does", "target_customer", "pricing_model",
    "key_features", "claimed_differentiator", "notable_customers",
    "recent_news",
]

# Edit these questions to retarget the tool for a different audience.
CRITERIA = {
    "clear_customer": "Is the target customer specific and clear, not just 'everyone'?",
    "pricing_clarity": "Is pricing transparent, and does the model look scalable (tiers, usage, seats)?",
    "specific_differentiation": "Is the differentiator concrete and specific rather than generic 'AI-powered' language?",
    "proof": "Does the company show proof such as named customers or case studies?",
    "momentum": "Does recent news suggest momentum, such as launches, partnerships or growth?",
}

BLOCKED = [
    "wikipedia.org", "wikiwand.com", "quora.com", "reddit.com",
    "fandom.com", "tavily.com",
]

PRESS = [
    "reuters.com", "bloomberg.com", "techcrunch.com", "wsj.com", "ft.com",
    "cnbc.com", "forbes.com", "theinformation.com", "businessinsider.com",
    "axios.com", "fortune.com", "nytimes.com", "venturebeat.com", "sifted.eu",
]

DATA = [
    "crunchbase.com", "pitchbook.com", "dealroom.co", "cbinsights.com",
    "tracxn.com",
]

SOCIAL = ["linkedin.com", "twitter.com", "x.com", "medium.com", "substack.com"]

SOURCES = {}


def get_host(url):
    return urlparse(url or "").netloc.lower().replace("www.", "")


def host_matches(host, domains):
    for d in domains:
        if host == d or host.endswith("." + d):
            return True
    return False


def search(query, seen, domain=None):
    if domain:
        print("Searching:", query, "(site: " + domain + ")")
    else:
        print("Searching:", query)
    try:
        if domain:
            results = tavily.search(
                query, max_results=4, include_domains=[domain]
            )["results"]
        else:
            results = tavily.search(
                query, max_results=5, exclude_domains=BLOCKED
            )["results"]
    except Exception as e:
        print("  search failed:", e)
        return ""

    kept = []
    for r in results:
        if host_matches(get_host(r["url"]), BLOCKED):
            continue
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        SOURCES[r["url"]] = r["content"][:700]
        kept.append(r)

    return "\n\n".join(
        "SOURCE: " + r["url"] + "\n" + r["content"][:700] for r in kept
    )


def call_json(prompt):
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
            if isinstance(data, dict):
                return data
            return {}
        except Exception as e:
            print("  model call failed (" + str(e)[:80] + "), retrying...")
            time.sleep(10)
    return {}


def find_domain(name):
    key = "".join(c for c in name.lower().split(" ")[0] if c.isalnum())
    try:
        results = tavily.search(
            name + " official website", max_results=8, exclude_domains=BLOCKED
        )["results"]
    except Exception:
        return None
    for r in results:
        host = get_host(r["url"])
        flat = host.replace(".", "")
        if key in flat and not host_matches(host, SOCIAL + PRESS + DATA):
            parts = host.split(".")
            return ".".join(parts[-2:])
    return None


def source_tier(url, domain):
    host = get_host(url)
    if not host:
        return "none"
    if domain and (host == domain or host.endswith("." + domain)):
        return "primary"
    if "linkedin.com/company/" in (url or "").lower():
        return "primary"
    if host_matches(host, ["sec.gov"]):
        return "primary"
    if host_matches(host, PRESS):
        return "press"
    if host_matches(host, DATA):
        return "data"
    if host_matches(host, SOCIAL):
        return "social"
    return "other"


def norm(s):
    s = (s or "").lower()
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    return " ".join(s.split())


def verify(profile, domain):
    for field in FIELDS:
        item = profile.get(field)
        if not isinstance(item, dict):
            profile[field] = {}
            continue
        if not item.get("value"):
            continue
        url = item.get("source_url")
        seen_text = norm(SOURCES.get(url, ""))
        ev = norm(item.get("evidence"))
        item["verified"] = bool(ev) and ev in seen_text
        item["tier"] = source_tier(url, domain)
        item["trusted"] = item["verified"] and item["tier"] in (
            "primary", "press", "data"
        )
        if not item["trusted"]:
            item["confidence"] = "low"
    return profile


def data_quality(profile):
    filled = 0
    trusted = 0
    for f in FIELDS:
        item = profile.get(f) or {}
        if item.get("value"):
            filled += 1
            if item.get("trusted"):
                trusted += 1
    return filled, trusted


def find_competitors(name, n=4):
    seen = set()
    context = search(name + " competitors alternatives startups", seen)
    context = context + "\n\n" + search(
        "venture-backed startups similar to " + name, seen
    )
    prompt = (
        "Based only on these search results, list the " + str(n)
        + " most direct competitors of " + name + ". "
        + "Direct means they sell a similar product to a similar customer. "
        + "Only include independent startups or scale-ups. "
        + "Do NOT include products owned by big tech companies (Google, Microsoft, "
        + "Meta, Amazon, Apple). Do not include " + name + " itself. "
        + 'Return JSON only, like {"competitors": ["Company A", "Company B"]}.\n\n'
        + context
    )
    data = call_json(prompt)
    found = []
    for c in data.get("competitors", []):
        if isinstance(c, str) and c.lower() != name.lower() and c not in found:
            found.append(c)
    return found[:n]


def research_company(name):
    domain = find_domain(name)
    print("Official site:", domain)

    seen = set()
    chunks = []
    if domain:
        for topic in ["pricing plans", "product features",
                      "customers case studies", "about what we do"]:
            chunks.append(search(name + " " + topic, seen, domain))
    for topic in ["review strengths weaknesses", "latest news",
                  "vs alternatives comparison"]:
        chunks.append(search(name + " " + topic, seen))

    context = "\n\n".join(c for c in chunks if c)
    if not context:
        return {}

    prompt = (
        "You are a research analyst profiling " + name + ". "
        + "Using ONLY the sources below, output a JSON object with exactly these keys: "
        + str(FIELDS) + ". Each value must be an object: "
        + '{"value": string or null, "source_url": string or null, '
        + '"evidence": string or null, "confidence": "low" or "medium" or "high"}. '
        + "RULES: 'value' is a plain summary under 25 words. 'evidence' must be one "
        + "sentence copied word for word from the SOURCE block at source_url. Do not "
        + "use outside knowledge. Do not combine facts from different sources. If you "
        + "cannot find a word-for-word sentence supporting a value, set value, "
        + "source_url and evidence to null. Output JSON only.\n\n"
        + context
    )
    profile = call_json(prompt)
    if not profile:
        return {}
    return verify(profile, domain)


def score_company(name, profile):
    summary = {}
    for f in FIELDS:
        item = profile.get(f) or {}
        summary[f] = item.get("value")

    prompt = (
        "You are a careful analyst scoring " + name + " on a scorecard. "
        + "Use ONLY the profile data below, which comes mostly from the company's "
        + "own marketing. For each criterion, give an integer score from 1 (weak) "
        + "to 5 (strong) and a reason under 20 words. If the profile lacks the "
        + "information needed, use null for the score and write 'not enough "
        + "information' as the reason. Do not guess. Criteria: "
        + json.dumps(CRITERIA) + ". "
        + 'Return JSON only: {"criterion_key": {"score": 4, "reason": "..."}} '
        + "using exactly the criterion keys given.\n\nProfile:\n"
        + json.dumps(summary, indent=2)
    )
    data = call_json(prompt)

    scores = {}
    for key in CRITERIA:
        entry = data.get(key)
        if not isinstance(entry, dict):
            entry = {}
        score = entry.get("score")
        if not isinstance(score, int) or score < 1 or score > 5:
            score = None
        scores[key] = {"score": score, "reason": entry.get("reason")}
    return scores


def print_profile(company, profile):
    print("\n=== " + company + " ===")
    for field in FIELDS:
        item = profile.get(field) or {}
        status = "TRUSTED" if item.get("trusted") else "CHECK"
        print("\n" + field + ": " + str(item.get("value")))
        print("   " + str(item.get("tier")) + " | " + status
              + " | " + str(item.get("source_url")))


def print_scoreboard(scores_by_company):
    print("\n=== SCORECARD (1-5, - means not enough information) ===")
    header = "company".ljust(24)
    for k in CRITERIA:
        header += k[:13].ljust(15)
    print(header)
    for company, scores in scores_by_company.items():
        line = company[:22].ljust(24)
        for k in CRITERIA:
            s = scores[k]["score"]
            line += str(s if s is not None else "-").ljust(15)
        print(line)


def write_memo(target, profiles, scores_by_company):
    compact = {}
    for company, profile in profiles.items():
        compact[company] = {}
        for f in FIELDS:
            compact[company][f] = (profile.get(f) or {}).get("value")
        compact[company]["scorecard"] = {
            k: scores_by_company[company][k]["score"] for k in CRITERIA
        }

    prompt = (
        "You are an analyst. Below are profiles and 1-5 scorecards of " + target
        + " and its competitors, gathered from company websites and press. "
        + "Write a short competitive memo in markdown, max 400 words, with these "
        + "sections: 1) Positioning: one line per company on who it targets and how "
        + "it differs. 2) Scorecard takeaways: who leads on which criteria. "
        + "3) Where " + target + " looks stronger and weaker. "
        + "4) Gaps or white space in the market. 5) What to verify before relying "
        + "on this. Use ONLY the data given. If a field or score is null, say it "
        + "is unknown. Note that product and differentiator claims largely come "
        + "from company marketing.\n\n" + json.dumps(compact, indent=2)
    )
    resp = client.chat.completions.create(
        model=MODEL, messages=[{"role": "user", "content": prompt}]
    )
    memo = resp.choices[0].message.content

    lines = ["", "", "## Data quality", ""]
    for company, profile in profiles.items():
        filled, trusted = data_quality(profile)
        lines.append(
            "- " + company + ": " + str(filled) + " of " + str(len(FIELDS))
            + " fields found, " + str(trusted)
            + " backed by a verified quote from a company, press or data source"
        )
    lines.append("")
    lines.append(
        "Scores are the model's judgement from the profile data, not independent "
        "facts. Generated " + str(date.today()) + "."
    )
    return memo + "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = input("Target company: ")

    n_competitors = 4
    if len(sys.argv) > 2 and sys.argv[2].isdigit():
        n_competitors = int(sys.argv[2])

    competitors = find_competitors(target, n_competitors)
    print("Competitors found:", competitors)

    profiles = {}
    scores_by_company = {}
    rows = []

    for company in [target] + competitors:
        print("\n--- Researching " + company + " ---")
        try:
            profile = research_company(company)
        except Exception as e:
            print("Failed on " + company + ": " + str(e))
            continue
        if not profile:
            print("No data found for " + company)
            continue

        scores = score_company(company, profile)
        print_profile(company, profile)

        profiles[company] = profile
        scores_by_company[company] = scores

        filled, trusted = data_quality(profile)
        row = {"company": company, "fields_found": filled, "fields_trusted": trusted}
        for field in FIELDS:
            item = profile.get(field) or {}
            row[field] = item.get("value")
            row[field + "_evidence"] = item.get("evidence")
            row[field + "_source"] = item.get("source_url")
            row[field + "_tier"] = item.get("tier")
            row[field + "_trusted"] = item.get("trusted")
        for key in CRITERIA:
            row["score_" + key] = scores[key]["score"]
            row["score_" + key + "_reason"] = scores[key]["reason"]
        rows.append(row)
        time.sleep(5)

    if not rows:
        print("No results to save.")
        sys.exit()

    base = target.lower().replace(" ", "_")

    with open("comparison_" + base + ".csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    full = {}
    for company in profiles:
        full[company] = {
            "profile": profiles[company],
            "scorecard": scores_by_company[company],
        }
    with open("full_data_" + base + ".json", "w") as f:
        json.dump(full, f, indent=2)

    print_scoreboard(scores_by_company)

    memo = write_memo(target, profiles, scores_by_company)
    with open("memo_" + base + ".md", "w") as f:
        f.write(memo)

    print("\nSaved: comparison_" + base + ".csv, full_data_" + base
          + ".json, memo_" + base + ".md\n")
    print(memo)