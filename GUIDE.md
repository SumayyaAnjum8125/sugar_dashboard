# Beginner's guide – Sugar Cosmetics Instagram Analytics

## 0. Read this first (important)
1. **Your brief asks for Tableau Public** (workbook + PPT). The Streamlit app is a
   great companion, but check with your mentor whether Streamlit is accepted
   *instead of* Tableau. Safe plan: use this app to find the insights fast, then
   rebuild the 10 charts in Tableau using the cleaned CSV the app exports.
2. **The real dataset was not in the Word file.** `sample_data_SYNTHETIC.csv` is
   random test data – never quote numbers from it. Ask your mentor for
   `sugar_cosmetics_instagram_data` (CSV/Excel).

## 1. Run the dashboard (5 minutes)
```bash
pip install -r requirements.txt
streamlit run app.py
```
Browser opens → upload the real file in the sidebar → done. Required columns:
`post_date, post_type, likes, comments, reach` (+ `shares, saves, impressions,
hashtags, caption` as in your brief). Column names are matched case-insensitively.

## 2. How the app maps to your 10 tasks
| Task | Tab | What to look at |
|---|---|---|
| 1 KPIs | 1 KPIs | posts, likes, comments, reach, avg engagement rate |
| 2 Monthly trend | 2 Posting trend | posts/month; gaps = inconsistency |
| 3 Top 10 likes | 3 Top by likes | which captions/formats win on likes |
| 4 Top 10 ER | 4 Top by ER | "hidden gems" vs Task 3 |
| 5 Post types | 5 Post types | avg likes/comments/shares/saves per type |
| 6 Weekday | 6 Weekday | best day; check number of posts too |
| 7 Funnel | 7 Funnel | impressions → reach → likes → comments → shares → saves |
| 8 Hashtags | 8 Hashtags | ER per hashtag (min uses slider) |
| 9 Dashboard | whole app | sidebar filters: post type, month range, hashtag |
| 10 Strategy | 9 Insights + 10 Strategy | auto-written findings & recommendations |

## 3. Key concept: engagement rate
`Engagement rate = (likes + comments + shares + saves) ÷ reach × 100`
Calculated **per post**, then averaged. Write this definition on a slide –
evaluators check "accuracy of calculations". (Some teams divide by followers;
no follower data here, so reach is the right base.)

## 4. 10-day plan
| Day | Do |
|---|---|
| 1 | Get the data, read the brief, run the app, understand each column |
| 2 | Clean data (app's cleaning log shows what was fixed); note problems |
| 3 | Tasks 1–2 (KPIs, trend) |
| 4 | Tasks 3–4 (top posts) |
| 5 | Tasks 5–6 (type, weekday) |
| 6 | Tasks 7–8 (funnel, hashtags) |
| 7 | Build Tableau sheets (if required) / finalise dashboard, filters |
| 8 | Write insights + recommendations (Task 10) in your own words |
| 9 | PPT, 5–10 slides |
| 10 | Rehearse, fix, submit |

## 5. PPT outline (8 slides)
1. Title & objective  2. KPI snapshot  3. Posting trend & consistency
4. Best content (formats + top posts)  5. Best timing (weekday)
6. Engagement funnel  7. Hashtags  8. Recommendations + gaps / next steps.
Each slide: **one headline sentence that is the insight**, one chart, 2 bullets.

## 6. How to explain an insight (formula)
**What** (number) → **So what** (why it matters) → **Now what** (action).
> "Carousels get 40% more saves than images → people find them useful →
> post more tutorial-style carousels."

## 7. Common beginner mistakes
- Quoting averages from very few posts (check counts).
- Confusing correlation with cause (a festival, not Friday, may explain a spike).
- Ranking hashtags used once (use the minimum-uses slider).
- Reporting synthetic-sample numbers.
- Too many charts: one message per chart.

## 8. Understanding the code (app.py)
Blocks: **1** settings → **2** `clean()` (renaming, dates, numbers, calculated
fields = Tableau "calculated fields") → **3** `build_insights()` (the sentences)
→ **4** sidebar filters → **5** tabs. Try changing a colour or adding a chart in
one tab to learn.

## 9. Questions to ask your mentor
- Is Streamlit allowed, or is Tableau Public mandatory?
- Is there follower history / audience demographics / story data?
- Is the engagement-rate definition (÷ reach) acceptable?
- Which date range is in scope, and were any campaigns running?
