"""
Sugar Cosmetics - Instagram Performance Dashboard (Streamlit)

Run:  streamlit run app.py

Each tab matches one task from the project brief (Task 1 ... Task 10).
The file is organised in 5 blocks so it is easy to read top to bottom:
  1. Settings & constants
  2. Load + clean data
  3. Helper functions that build insights
  4. Sidebar filters
  5. The 10 tabs
"""
import re
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------------------------------
# 1. SETTINGS
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Sugar Cosmetics | Instagram Insights",
                   page_icon="💄", layout="wide")

BRAND = "#D6246E"          # one main colour, used for single-series charts
SEQ = ["#D6246E", "#7B3FA0", "#F4A259", "#2A9D8F"]   # categorical colours
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]
REQUIRED = ["post_date", "post_type", "likes", "comments", "reach"]
OPTIONAL = ["shares", "saves", "impressions", "hashtags", "caption"]
NUMERIC = ["likes", "comments", "shares", "saves", "reach", "impressions"]
ALIASES = {"date": "post_date", "posted_date": "post_date", "type": "post_type",
           "media_type": "post_type", "hashtag": "hashtags", "like": "likes",
           "comment": "comments", "share": "shares", "save": "saves"}
SAMPLE_FILE = Path(__file__).with_name("sample_data_SYNTHETIC.csv")

st.markdown("""
<style>
.block-container {padding-top: 1.5rem;}
div[data-testid="stMetric"] {background: rgba(214,36,110,.07);
    border-radius: 10px; padding: 12px 16px;}
</style>""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# 2. LOAD + CLEAN
# ----------------------------------------------------------------------------
def read_any(name: str, raw: bytes) -> pd.DataFrame:
    if name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(BytesIO(raw))
    return pd.read_csv(BytesIO(raw))


@st.cache_data(show_spinner=False)
def clean(name: str, raw: bytes):
    """Return (clean_df, list_of_notes). Notes tell you what was fixed."""
    notes = []
    df = read_any(name, raw)
    n0 = len(df)

    # standard column names: lowercase, underscores
    df.columns = (df.columns.str.strip().str.lower()
                  .str.replace(r"[\s\-]+", "_", regex=True))
    df = df.rename(columns=ALIASES)

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        return None, [f"Missing required column(s): {missing}. "
                      f"Found: {list(df.columns)}"]

    # duplicates
    d = df.duplicated().sum()
    if d:
        df = df.drop_duplicates()
        notes.append(f"Removed {d} duplicate row(s).")

    # dates
    df["post_date"] = pd.to_datetime(df["post_date"], errors="coerce")
    bad = df["post_date"].isna().sum()
    if bad:
        df = df.dropna(subset=["post_date"])
        notes.append(f"Dropped {bad} row(s) with an unreadable date.")

    # text
    df["post_type"] = df["post_type"].astype(str).str.strip().str.title()
    for c in ("hashtags", "caption"):
        if c not in df.columns:
            df[c] = ""
            notes.append(f"Column '{c}' not found - related charts are limited.")
        df[c] = df[c].fillna("").astype(str)

    # numbers
    for c in NUMERIC:
        if c not in df.columns:
            df[c] = pd.NA
            notes.append(f"Column '{c}' not found - treated as unavailable.")
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["likes", "comments", "shares", "saves"]:
        n = df[c].isna().sum()
        if n and df[c].notna().any():
            notes.append(f"Filled {n} blank '{c}' value(s) with 0.")
        df[c] = df[c].fillna(0)

    # derived fields (calculated fields in Tableau language)
    df["interactions"] = df[["likes", "comments", "shares", "saves"]].sum(axis=1)
    reach = df["reach"].where(df["reach"] > 0)
    df["engagement_rate"] = df["interactions"] / reach * 100   # % of reach
    df["month"] = df["post_date"].dt.to_period("M").dt.to_timestamp()
    df["weekday"] = pd.Categorical(df["post_date"].dt.day_name(),
                                   DAY_ORDER, ordered=True)
    df["tags"] = df["hashtags"].apply(extract_tags)
    df["tag_count"] = df["tags"].str.len()
    df["caption_short"] = df["caption"].str.slice(0, 40) + \
        df["caption"].str.len().gt(40).map({True: "…", False: ""})
    df["post_id"] = df["post_date"].dt.strftime("%d %b %y") + " · " + \
        df["caption_short"].replace("", "(no caption)")
    notes.append(f"{n0} rows loaded -> {len(df)} rows after cleaning.")
    return df.reset_index(drop=True), notes


def extract_tags(text: str):
    found = re.findall(r"#\w+", text.lower())
    if found:
        return list(dict.fromkeys(found))
    parts = [p for p in re.split(r"[,\s]+", text.lower().strip()) if p]
    return list(dict.fromkeys("#" + p.lstrip("#") for p in parts))


# ----------------------------------------------------------------------------
# 3. INSIGHT HELPERS
# ----------------------------------------------------------------------------
def fmt(n):
    n = float(n)
    for lim, s in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= lim:
            return f"{n / lim:.1f}{s}"
    return f"{n:,.0f}"


def hashtag_table(d: pd.DataFrame) -> pd.DataFrame:
    ex = d[["tags", "engagement_rate", "reach", "likes"]].explode("tags").dropna(
        subset=["tags"])
    ex = ex[ex["tags"] != ""]
    if ex.empty:
        return pd.DataFrame(columns=["hashtag", "posts", "avg_engagement_rate",
                                     "avg_reach", "avg_likes"])
    t = (ex.groupby("tags")
         .agg(posts=("tags", "size"), avg_engagement_rate=("engagement_rate", "mean"),
              avg_reach=("reach", "mean"), avg_likes=("likes", "mean"))
         .reset_index().rename(columns={"tags": "hashtag"}))
    return t


def build_insights(d: pd.DataFrame) -> dict:
    """Turn the filtered data into plain-English findings. Returns a dict so
    both the 'Insights' tab and the 'Recommendations' tab can reuse it."""
    out = {"findings": [], "recs": [], "gaps": []}
    F, R, G = out["findings"], out["recs"], out["gaps"]
    if len(d) < 5:
        F.append("Too few posts in the current filter to draw conclusions - "
                 "widen the filters.")
        return out

    # overall
    F.append(f"**Overall:** {len(d)} posts, average engagement rate "
             f"**{d.engagement_rate.mean():.2f}%** (median "
             f"{d.engagement_rate.median():.2f}%). Average reach per post: "
             f"{fmt(d.reach.mean())}.")

    # post type
    g = d.groupby("post_type").agg(er=("engagement_rate", "mean"),
                                   n=("post_type", "size"),
                                   likes=("likes", "mean"),
                                   saves=("saves", "mean"),
                                   shares=("shares", "mean"))
    if len(g) > 1:
        best, worst = g["er"].idxmax(), g["er"].idxmin()
        lift = (g.loc[best, "er"] / g.loc[worst, "er"] - 1) * 100
        F.append(f"**Format:** {best} posts have the highest engagement rate "
                 f"({g.loc[best, 'er']:.2f}%), about {lift:.0f}% higher than "
                 f"{worst} ({g.loc[worst, 'er']:.2f}%). {best} is "
                 f"{g.loc[best, 'n'] / g.n.sum():.0%} of all posts.")
        R.append(f"**Content type:** lean into **{best}** - it earns the most "
                 f"engagement per person reached. Keep {worst} for "
                 f"announcements or product shots, not as the main format.")
        sv = g["saves"].idxmax()
        if sv != best:
            F.append(f"**Saves:** {sv} posts are saved most "
                     f"({g.loc[sv, 'saves']:.0f} per post) - a sign of "
                     f"'useful / reference' content.")
        small = g[g.n < 5].index.tolist()
        if small:
            G.append(f"Sample size is small (<5 posts) for: {', '.join(small)}. "
                     f"Treat those averages with caution.")

    # weekday
    w = d.groupby("weekday", observed=True).agg(er=("engagement_rate", "mean"),
                                                n=("post_type", "size"))
    if len(w) > 2:
        b, wst = w["er"].idxmax(), w["er"].idxmin()
        F.append(f"**Timing:** {b} is the best day (avg ER "
                 f"{w.loc[b, 'er']:.2f}%, {int(w.loc[b, 'n'])} posts); "
                 f"{wst} is weakest ({w.loc[wst, 'er']:.2f}%).")
        top3 = ", ".join(w["er"].nlargest(3).index.astype(str))
        R.append(f"**Timing:** schedule priority posts on **{top3}**; test "
                 f"moving content away from {wst}.")
        under = w[w.n < 5].index.astype(str).tolist()
        if under:
            G.append(f"Few posts on {', '.join(under)} - weekday "
                     f"conclusions there are weak.")

    # posting frequency
    m = d.groupby("month").size()
    full = pd.date_range(m.index.min(), m.index.max(), freq="MS")
    m = m.reindex(full, fill_value=0)
    if len(m) >= 4:
        half = len(m) // 2
        a, b2 = m.iloc[:half].mean(), m.iloc[half:].mean()
        trend = "increased" if b2 > a * 1.1 else "decreased" if b2 < a * 0.9 else "stayed steady"
        F.append(f"**Frequency:** the brand posts about {m.mean():.1f} times a "
                 f"month. Posting {trend} ({a:.1f}/month in the first half vs "
                 f"{b2:.1f}/month in the second). {int((m == 0).sum())} "
                 f"month(s) had no posts.")
        mm = d.groupby("month").engagement_rate.mean().reindex(full)
        if m.nunique() > 2 and mm.notna().sum() > 3:
            corr = m.corr(mm)
            if pd.notna(corr):
                F.append(f"**Frequency vs quality:** correlation between "
                         f"posts-per-month and monthly engagement rate is "
                         f"{corr:+.2f} ({'posting more did not hurt' if corr > -0.2 else 'more posts coincided with lower engagement'}).")
        R.append(f"**Frequency:** aim for a steady rhythm (~{max(m.mean(), 1):.0f}+ "
                 f"posts/month, no empty months) - consistency lets you "
                 f"compare formats fairly.")

    # top posts / hidden gems
    top10 = d.nlargest(10, "likes")
    share = top10.likes.sum() / d.likes.sum() if d.likes.sum() else 0
    F.append(f"**Top posts:** the top 10 posts by likes bring "
             f"{share:.0%} of all likes. The most common format among them is "
             f"{top10.post_type.mode().iat[0]}.")
    gems = d[(d.engagement_rate >= d.engagement_rate.quantile(.75)) &
             (d.likes <= d.likes.median())]
    if len(gems):
        ex = gems.nlargest(1, "engagement_rate").iloc[0]
        F.append(f"**Hidden gems:** {len(gems)} posts have top-quartile "
                 f"engagement rate but below-median likes, e.g. "
                 f"\"{ex.caption_short}\" ({ex.engagement_rate:.1f}% ER). "
                 f"They convert a small audience well - worth repeating.")
        R.append("**Hidden gems:** re-use the themes / formats of the "
                 "high-ER, low-likes posts and boost them with a bit of "
                 "paid or collab support.")

    # funnel
    reach, likes = d.reach.sum(), d.likes.sum()
    if reach:
        spk = d.shares.sum() / reach * 1000
        svk = d.saves.sum() / reach * 1000
        F.append(f"**Funnel:** per 1,000 people reached: "
                 f"{likes / reach * 1000:.0f} likes, "
                 f"{d.comments.sum() / reach * 1000:.1f} comments, "
                 f"{spk:.1f} shares, {svk:.1f} saves. "
                 + ("Comments are far lower than likes - the audience likes "
                    "but rarely talks." if d.comments.sum() < likes * .05 else ""))
        R.append("**Conversation:** end captions with a question / poll "
                 "prompt and reply to comments within the first hour to lift "
                 "comments and shares.")
    if d.impressions.notna().any() and d.reach.sum():
        F.append(f"**Repeat exposure:** impressions / reach = "
                 f"{d.impressions.sum() / d.reach.sum():.2f} - each person "
                 f"sees a post about that many times.")

    # hashtags
    ht = hashtag_table(d)
    ht_use = ht[ht.posts >= 3]
    if len(ht_use) >= 3:
        best_tags = ht_use.nlargest(3, "avg_engagement_rate")
        used = ht.nlargest(1, "posts").iloc[0]
        F.append(f"**Hashtags:** best average ER (min 3 uses): "
                 + ", ".join(f"{r.hashtag} ({r.avg_engagement_rate:.2f}%)"
                             for r in best_tags.itertuples())
                 + f". Most used: {used.hashtag} ({int(used.posts)} posts).")
        R.append("**Hashtags:** make the top-ER tags above part of the "
                 "standard set; retire tags that are frequent but below "
                 "average.")
        c = d[["tag_count", "engagement_rate"]].dropna()
        if c.tag_count.nunique() > 2:
            r = c.tag_count.corr(c.engagement_rate)
            F.append(f"**Hashtag count:** correlation between number of "
                     f"hashtags and ER is {r:+.2f} "
                     f"({'weak - count matters less than which tags' if abs(r) < .2 else 'noticeable'}).")

    # gaps
    G.append("No follower-count data in the dataset, so account *growth* and "
             "audience demographics (project objective 4) cannot be measured. "
             "Ask the mentor for follower history or use Instagram Insights export.")
    G.append("Stories are not in the dataset (only posts), so the 'posts vs "
             "reels vs stories' comparison is limited to Image / Video / Carousel.")
    G.append("Correlation is not causation: a post may do well because of the "
             "product or a campaign, not the weekday or format.")
    R.append("**Campaign ideas:** a UGC / 'tag us' lipstick-shade series, "
             "festive & bridal tutorials as saveable Carousels, and "
             "behind-the-scenes Reels - then A/B test them against the "
             "current best format.")
    return out


# ----------------------------------------------------------------------------
# 4. SIDEBAR - data source + filters
# ----------------------------------------------------------------------------
st.sidebar.title("💄 Sugar Cosmetics")
st.sidebar.caption("Instagram performance dashboard")
up = st.sidebar.file_uploader("Upload the real dataset (CSV or Excel)",
                              type=["csv", "xlsx", "xls"])
if up is not None:
    name, raw, synthetic = up.name, up.getvalue(), False
elif SAMPLE_FILE.exists():
    name, raw, synthetic = SAMPLE_FILE.name, SAMPLE_FILE.read_bytes(), True
else:
    st.title("Sugar Cosmetics – Instagram Insights")
    st.info("Upload `sugar_cosmetics_instagram_data` (CSV/Excel) in the sidebar "
            "to begin. Or run `python make_sample_data.py` for test data.")
    st.stop()

df_all, notes = clean(name, raw)
if df_all is None:
    st.error(notes[0])
    st.stop()

if synthetic:
    st.warning("⚠️ You are looking at **SYNTHETIC SAMPLE DATA** (random numbers) "
               "so the dashboard can be tested. Upload the real file in the "
               "sidebar before drawing any conclusions.")

st.sidebar.subheader("Filters")
types = sorted(df_all.post_type.unique())
sel_types = st.sidebar.multiselect("Post type", types, default=types)

months = sorted(df_all.month.unique())
labels = [pd.Timestamp(m).strftime("%b %Y") for m in months]
if len(labels) > 1:
    lo, hi = st.sidebar.select_slider("Month range", options=labels,
                                      value=(labels[0], labels[-1]))
else:
    lo = hi = labels[0]
mask = (df_all.post_type.isin(sel_types)
        & (df_all.month >= pd.to_datetime(lo, format="%b %Y"))
        & (df_all.month <= pd.to_datetime(hi, format="%b %Y")))

tag_counts = (df_all.tags.explode().dropna().loc[lambda s: s != ""]
              .value_counts())
sel_tags = st.sidebar.multiselect("Hashtag (post contains any)",
                                  tag_counts.index.tolist()[:60])
if sel_tags:
    mask &= df_all.tags.apply(lambda t: any(x in t for x in sel_tags))

df = df_all[mask]
st.sidebar.markdown(f"**{len(df)}** of {len(df_all)} posts selected")
with st.sidebar.expander("Data-cleaning log"):
    for n in notes:
        st.write("•", n)
st.sidebar.download_button("⬇️ Download cleaned data (CSV)",
                           df_all.drop(columns=["tags"]).to_csv(index=False),
                           "sugar_instagram_cleaned.csv", "text/csv")

st.title("Sugar Cosmetics – Instagram Insights Report")
if df.empty:
    st.warning("No posts match the filters.")
    st.stop()


def style(fig, h=380):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=40, b=10),
                      legend_title_text="")
    return fig


# ----------------------------------------------------------------------------
# 5. TABS (one per task)
# ----------------------------------------------------------------------------
tabs = st.tabs(["1 KPIs", "2 Posting trend", "3 Top by likes", "4 Top by ER",
                "5 Post types", "6 Weekday", "7 Funnel", "8 Hashtags",
                "9 Insights", "10 Strategy"])

# ---- Task 1: KPIs -----------------------------------------------------------
with tabs[0]:
    st.subheader("How is the overall account performing?")
    c = st.columns(5)
    c[0].metric("Total posts", f"{len(df):,}")
    c[1].metric("Total likes", fmt(df.likes.sum()))
    c[2].metric("Total comments", fmt(df.comments.sum()))
    c[3].metric("Total reach", fmt(df.reach.sum()))
    c[4].metric("Avg engagement rate", f"{df.engagement_rate.mean():.2f}%")
    st.caption("Engagement rate per post = (likes + comments + shares + saves) "
               "÷ reach × 100. The KPI is the average across posts. "
               f"Reach-weighted rate: {df.interactions.sum() / df.reach.sum() * 100:.2f}%.")
    k = st.columns(3)
    k[0].metric("Avg likes / post", fmt(df.likes.mean()))
    k[1].metric("Avg reach / post", fmt(df.reach.mean()))
    k[2].metric("Total shares + saves", fmt(df.shares.sum() + df.saves.sum()))

# ---- Task 2: monthly trend --------------------------------------------------
with tabs[1]:
    st.subheader("Monthly posting trend")
    m = df.groupby("month").size()
    full = pd.date_range(m.index.min(), m.index.max(), freq="MS")
    m = m.reindex(full, fill_value=0).rename("posts").rename_axis("month").reset_index()
    fig = px.line(m, x="month", y="posts", markers=True,
                  title="Posts per month", color_discrete_sequence=[BRAND])
    fig.update_xaxes(tickformat="%b %Y")
    st.plotly_chart(style(fig), width="stretch")
    me = df.groupby("month").engagement_rate.mean().reset_index()
    fig2 = px.line(me, x="month", y="engagement_rate", markers=True,
                   title="Average engagement rate by month (%)",
                   color_discrete_sequence=[SEQ[1]])
    fig2.update_xaxes(tickformat="%b %Y")
    st.plotly_chart(style(fig2, 300), width="stretch")

# ---- Task 3: top by likes ---------------------------------------------------
with tabs[2]:
    st.subheader("Top 10 posts by likes")
    t = df.nlargest(10, "likes").sort_values("likes")
    fig = px.bar(t, x="likes", y="post_id", orientation="h", color="post_type",
                 color_discrete_sequence=SEQ, title="Most-liked posts")
    fig.update_yaxes(title="")
    st.plotly_chart(style(fig, 450), width="stretch")
    st.dataframe(t.iloc[::-1][["post_date", "post_type", "caption", "likes",
                               "reach", "engagement_rate"]],
                 hide_index=True, width="stretch")

# ---- Task 4: top by ER ------------------------------------------------------
with tabs[3]:
    st.subheader("Top 10 posts by engagement rate")
    min_reach = st.slider("Ignore posts with reach below", 0,
                          int(df.reach.max()), 0,
                          help="Tiny-reach posts can show unrealistically high rates.")
    pool = df[df.reach >= min_reach]
    t = pool.nlargest(10, "engagement_rate").sort_values("engagement_rate")
    fig = px.bar(t, x="engagement_rate", y="post_id", orientation="h",
                 color="post_type", color_discrete_sequence=SEQ,
                 title="Highest engagement rate (%)")
    fig.update_yaxes(title="")
    st.plotly_chart(style(fig, 450), width="stretch")
    st.dataframe(t.iloc[::-1][["post_date", "post_type", "caption", "likes",
                               "reach", "engagement_rate"]],
                 hide_index=True, width="stretch")
    st.caption("Compare with Task 3: posts here but not there are your "
               "'hidden gems'.")

# ---- Task 5: post type ------------------------------------------------------
with tabs[4]:
    st.subheader("Post type performance")
    cols = ["likes", "comments", "shares", "saves"]
    g = df.groupby("post_type")[cols].mean().reset_index().melt(
        "post_type", var_name="metric", value_name="average")
    fig = px.bar(g, x="post_type", y="average", color="post_type",
                 facet_col="metric", color_discrete_sequence=SEQ,
                 title="Average per post (each metric has its own scale)")
    fig.update_yaxes(matches=None, showticklabels=True)
    fig.update_xaxes(title="")
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1].title()))
    fig.update_layout(showlegend=False)
    st.plotly_chart(style(fig, 400), width="stretch")
    s = df.groupby("post_type").agg(posts=("likes", "size"),
                                    avg_engagement_rate=("engagement_rate", "mean"),
                                    avg_reach=("reach", "mean")).round(2)
    st.dataframe(s, width="stretch")

# ---- Task 6: weekday --------------------------------------------------------
with tabs[5]:
    st.subheader("Day-of-week analysis")
    metric = st.radio("Metric", ["Average engagement rate (%)", "Average likes",
                                 "Average reach", "Number of posts"],
                      horizontal=True)
    w = df.groupby("weekday", observed=False).agg(
        er=("engagement_rate", "mean"), likes=("likes", "mean"),
        reach=("reach", "mean"), posts=("likes", "size")).reset_index()
    col = {"Average engagement rate (%)": "er", "Average likes": "likes",
           "Average reach": "reach", "Number of posts": "posts"}[metric]
    fig = px.bar(w, x="weekday", y=col, color_discrete_sequence=[BRAND],
                 title=metric, text_auto=".2s" if col != "er" else ".2f")
    fig.update_xaxes(title="")
    st.plotly_chart(style(fig), width="stretch")
    st.caption("Check 'Number of posts' too - a day with very few posts can "
               "look best purely by chance.")

# ---- Task 7: funnel ---------------------------------------------------------
with tabs[6]:
    st.subheader("Engagement funnel")
    steps = [("Impressions", df.impressions.sum(min_count=1)),
             ("Reach", df.reach.sum()), ("Likes", df.likes.sum()),
             ("Comments", df.comments.sum()), ("Shares", df.shares.sum()),
             ("Saves", df.saves.sum())]
    steps = [(n, v) for n, v in steps if pd.notna(v)]
    fig = go.Figure(go.Funnel(y=[s[0] for s in steps], x=[s[1] for s in steps],
                              textinfo="value+percent previous",
                              marker=dict(color=BRAND)))
    st.plotly_chart(style(fig, 450), width="stretch")
    st.caption("Percentages show each step vs the previous one. Shares and "
               "saves can be higher than comments, so this is a 'funnel-style' "
               "view, not a strict drop-off.")
    fl = pd.DataFrame(steps, columns=["step", "total"])
    fl["per 1,000 reach"] = (fl.total / df.reach.sum() * 1000).round(1)
    st.dataframe(fl, hide_index=True, width="stretch")

# ---- Task 8: hashtags -------------------------------------------------------
with tabs[7]:
    st.subheader("Hashtag analysis")
    ht = hashtag_table(df)
    if ht.empty:
        st.info("No hashtags found in this selection.")
    else:
        cc = st.columns(2)
        min_uses = cc[0].slider("Minimum posts using the hashtag", 1,
                                max(int(ht.posts.max()), 2), min(3, int(ht.posts.max())))
        by = cc[1].selectbox("Rank by", ["avg_engagement_rate", "avg_reach",
                                         "avg_likes", "posts"])
        t = ht[ht.posts >= min_uses].nlargest(15, by).sort_values(by)
        fig = px.bar(t, x=by, y="hashtag", orientation="h", hover_data=["posts"],
                     color_discrete_sequence=[BRAND], title=f"Top hashtags by {by}")
        fig.update_yaxes(title="")
        st.plotly_chart(style(fig, 480), width="stretch")
        used = ht.nlargest(8, "posts")
        pie = px.pie(used, names="hashtag", values="posts", hole=.45,
                     title="Share of usage - top 8 hashtags",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(style(pie, 360), width="stretch")
        st.dataframe(ht.sort_values("posts", ascending=False).round(2),
                     hide_index=True, width="stretch")

# ---- Task 9: insights (the "final dashboard" is the whole app) --------------
ins = build_insights(df)
with tabs[8]:
    st.subheader("Auto-generated insights for the current filters")
    st.caption("These sentences are computed from the data you see - change a "
               "filter and they update. Always sanity-check against the charts.")
    for f in ins["findings"]:
        st.markdown("- " + f)

# ---- Task 10: strategy ------------------------------------------------------
with tabs[9]:
    st.subheader("Strategic recommendations")
    cL, cR = st.columns(2)
    with cL:
        st.markdown("#### Recommended actions")
        for r in ins["recs"]:
            st.markdown("- " + r)
    with cR:
        st.markdown("#### Gaps & limitations")
        for g_ in ins["gaps"]:
            st.markdown("- " + g_)
    st.info("Use these as a **draft**. Add your own judgement about the brand "
            "(launches, festivals, campaigns) before presenting.")
