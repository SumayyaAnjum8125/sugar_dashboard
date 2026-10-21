"""Create a SYNTHETIC sample dataset with the same columns as the real
`sugar_cosmetics_instagram_data` file, so the dashboard can be tested
before you have the real data.

!! Everything produced here is random. Never report insights from it. !!

Run:  python make_sample_data.py
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
N = 320

dates = pd.to_datetime("2024-01-01") + pd.to_timedelta(
    np.sort(rng.integers(0, 540, N)), unit="D"
)
types = rng.choice(["Image", "Video", "Carousel"], N, p=[0.45, 0.30, 0.25])

type_boost = {"Image": 1.0, "Video": 1.6, "Carousel": 1.25}
tags_pool = [
    "#sugarcosmetics", "#lipstick", "#makeup", "#mattelipstick", "#sugarpop",
    "#bridalmakeup", "#eyeliner", "#kajal", "#festivemakeup", "#skincare",
    "#foundation", "#giveaway", "#beautytips", "#makeupindia", "#newlaunch",
]
captions = [
    "Meet your new everyday lipstick", "Smudge-proof all day", "Festive glam ready",
    "Behind the scenes with our makeup artists", "Giveaway time! Tag a friend",
    "3 ways to wear matte red", "New launch alert", "Bridal glow tutorial",
    "Wear it your way", "Tried and tested by you",
]

rows = []
for d, t in zip(dates, types):
    reach = int(rng.lognormal(10.2, 0.45) * type_boost[t])
    impressions = int(reach * rng.uniform(1.1, 1.8))
    wk = 1.25 if d.dayofweek in (4, 5) else 1.0
    likes = int(reach * rng.uniform(0.02, 0.08) * wk)
    comments = int(likes * rng.uniform(0.01, 0.06))
    shares = int(likes * rng.uniform(0.01, 0.08) * (1.5 if t == "Video" else 1))
    saves = int(likes * rng.uniform(0.03, 0.15) * (1.4 if t == "Carousel" else 1))
    k = rng.integers(2, 8)
    tags = " ".join(rng.choice(tags_pool, k, replace=False))
    rows.append(
        dict(
            post_date=d.date(), post_type=t, likes=likes, comments=comments,
            shares=shares, saves=saves, reach=reach, impressions=impressions,
            hashtags=tags, caption=rng.choice(captions),
        )
    )

df = pd.DataFrame(rows)
# add a few realistic data problems so the cleaning code is exercised
df.loc[rng.choice(N, 4, replace=False), "saves"] = np.nan
df.loc[rng.choice(N, 3, replace=False), "post_type"] = " video "
df = pd.concat([df, df.iloc[[5]]], ignore_index=True)  # one duplicate row
df.to_csv("sample_data_SYNTHETIC.csv", index=False)
print("Wrote sample_data_SYNTHETIC.csv", df.shape)
