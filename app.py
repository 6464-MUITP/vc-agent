import json
import time
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Competitor Analysis Agent", layout="wide")

try:
    import main
except KeyError as e:
    st.error("Missing API key " + str(e) + ". Add it to your .env file or Streamlit secrets.")
    st.stop()


def access_ok():
    try:
        code = st.secrets["ACCESS_CODE"]
    except Exception:
        return True
    return st.text_input("Access code", type="password") == code


st.title("Competitor Analysis Agent")
st.write(
    "Enter a company. The agent finds its competitors, researches each one from the "
    "company's own site and the press, checks every claim against its source, scores "
    "them 1-5, and writes a short memo. A run takes a few minutes."
)

if not access_ok():
    st.stop()

with st.sidebar:
    st.header("Settings")
    n_comp = st.slider("Number of competitors", 1, 4, 2)
    st.caption("More competitors means a longer wait and more API usage.")
    st.markdown("**How to read the results**")
    st.markdown(
        "- **TRUSTED**: the quote was found in the source, and the source is the "
        "company, the press, or a data provider.\n"
        "- **CHECK**: verify this one by hand."
    )

company = st.text_input("Company name", placeholder="e.g. Perplexity AI")
run = st.button("Analyze", type="primary")

if run and company.strip():
    target = company.strip()
    profiles = {}
    scores = {}
    memo = ""

    with st.status("Working...", expanded=True) as status:
        st.write("Finding competitors...")
        competitors = main.find_competitors(target, n_comp)
        st.write("Competitors: " + ", ".join(competitors))

        for name in [target] + competitors:
            st.write("Researching " + name + "...")
            try:
                profile = main.research_company(name)
            except Exception as e:
                st.write("Failed on " + name + ": " + str(e))
                continue
            if not profile:
                st.write("No data found for " + name)
                continue
            profiles[name] = profile
            scores[name] = main.score_company(name, profile)
            time.sleep(3)

        if profiles:
            st.write("Writing memo...")
            memo = main.write_memo(target, profiles, scores)
            status.update(label="Done", state="complete")
        else:
            status.update(label="No results", state="error")

    if profiles:
        st.session_state["result"] = {
            "target": target, "profiles": profiles, "scores": scores, "memo": memo,
        }
    else:
        st.error("No data found. Try a different company name or wait a minute (rate limits).")

res = st.session_state.get("result")
if res:
    st.header("Results for " + res["target"])

    st.subheader("Scorecard (1-5, empty means not enough information)")
    rows = []
    for name, sc in res["scores"].items():
        row = {"Company": name}
        for k in main.CRITERIA:
            row[k.replace("_", " ").title()] = sc[k]["score"]
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True)

    st.subheader("Memo")
    st.markdown(res["memo"])

    st.subheader("Details and sources")
    for name, profile in res["profiles"].items():
        with st.expander(name):
            for field in main.FIELDS:
                item = profile.get(field) or {}
                label = field.replace("_", " ").title()
                value = item.get("value") or "Not found"
                st.markdown("**" + label + ":** " + str(value))
                if item.get("source_url"):
                    flag = "TRUSTED" if item.get("trusted") else "CHECK"
                    st.caption(flag + " | " + str(item.get("tier")) + " | " + str(item["source_url"]))
                else:
                    st.caption("no source found")

    st.download_button("Download memo (.md)", res["memo"], file_name="memo.md")
    st.download_button(
        "Download full data (.json)",
        json.dumps({"profiles": res["profiles"], "scores": res["scores"]}, indent=2),
        file_name="full_data.json",
    )
    st.caption(
        "Scores are a model's judgement from the profile data. Product claims largely "
        "come from company marketing. Check the CHECK items before relying on them."
    )