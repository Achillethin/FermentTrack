# Published pH(t) curves for lacto ferments (recommender v2, release 2)

Collected 2026-10-24 for the release-2 check "the forecast's 90 % band covers 85–95 % of
the literature points" (`tests/test_lacto_literature.py`). Every number below was read from
the opened source at the location given; nothing was read off a figure.

## Datasets

| id | source | location | conditions | comparability |
|---|---|---|---|---|
| kristek2004 | Kristek S., Bešlo D., Pavlović H., Kristek A. 2004. Effect of starter cultures L. mesenteroides and L. lactis ssp. lactis on sauerkraut fermentation and quality. *Czech J. Food Sci.* 22(4):125–132. DOI 10.17221/3416-CJFS | Table 1, variant A (control, spontaneous), cycles I–III | whole cabbage heads covered with boiled, cooled 2.5 % NaCl brine in 100 L barrels; 21 °C; 28 d; brine pH | whole heads in brine, not shredded dry-salted: the model runs the library's dry-salted kraut at 2.5 % salt as a proxy |
| kim2020 | Kim J.Y., Kim B.S., Kim J.H., Oh S.I., Koo J. 2020. Development of dynamic model for real-time monitoring of ripening changes of kimchi during distribution. *Foods* 9(8):1075. DOI 10.3390/foods9081075 | § 3.1 text | commercial napa-cabbage kimchi, 500 g PE packs, 20 °C constant; salt not stated | commercial: LAB counts at packing likely higher than homemade; composition not given |
| hong2016 | Hong S.P., Lee E.J., Kim Y.H., Ahn D.U. 2016. Effect of fermentation temperature on the volatile composition of kimchi. *J. Food Sci.* 81(11):C2623–C2629. DOI 10.1111/1750-3841.13517 | abstract | kimchi at 20 °C: optimum ripening at 2 d, pH 4.41, TA 0.76 % | one point; salt not confirmed |
| foods2025 | Effect of fermentation conditions on functional quality of napa cabbage kimchi. *Foods* 2025, 14(16):2826. DOI 10.3390/foods14162826 (PMC12385461) | Table 3; § 2.2.4; Tables 1, 4 | homemade: brined napa (10 % brine, 10 h) + radish 13 %, green onion 2 %, garlic 1.4 %, ginger 0.6 %, red pepper powder 3.5 %, sugar 1 %, fish sauce 2.2 % (of cabbage); final salt 2.3 %; 4 and 15 °C | 15 °C is just below the model's 16–24 °C range: reported, not in the coverage criterion |

Also used for the priors (not as pH points):
- Johanningsmeier S., McFeeters R.F., Fleming H.P., Thompson R.L. 2007. *J. Food Sci.* 72(5):M166–M172, Table 2: raw shredded cabbage 1e3.0–1e3.6 LAB/g.
- Foods 2025 Tables 1, 4: brined napa cabbage Leuconostoc not detected, Lactobacillus 1e3.12; fresh kimchi (1 h after seasoning) Leuconostoc 1e5.50, Lactobacillus 1e5.64 CFU/mL.
- Wang et al. 2013, *PLoS ONE* 8:e64995, Tables 2 and 4 (data of Zurera-Cosano et al. 2005): L. mesenteroides growth rates at 10.5–24.5 °C, pH 5.5–7.5, 0.25–6.25 % NaCl.
- Patra J.K. et al. 2016, *Front. Microbiol.* 7:1493: "final salt level is calculated at 2.5%".

## Points

```csv
dataset,ferment,temp_c,salt_pct,t_h,ph,read_from
kristek2004-I,sauerkraut,21,2.5,0,6.20,table
kristek2004-I,sauerkraut,21,2.5,24,5.98,table
kristek2004-I,sauerkraut,21,2.5,48,5.34,table
kristek2004-I,sauerkraut,21,2.5,72,4.80,table
kristek2004-I,sauerkraut,21,2.5,96,4.46,table
kristek2004-I,sauerkraut,21,2.5,120,4.35,table
kristek2004-I,sauerkraut,21,2.5,144,4.22,table
kristek2004-I,sauerkraut,21,2.5,168,4.18,table
kristek2004-I,sauerkraut,21,2.5,336,3.91,table
kristek2004-I,sauerkraut,21,2.5,504,3.82,table
kristek2004-I,sauerkraut,21,2.5,672,3.78,table
kristek2004-II,sauerkraut,21,2.5,0,6.03,table
kristek2004-II,sauerkraut,21,2.5,24,5.78,table
kristek2004-II,sauerkraut,21,2.5,48,5.41,table
kristek2004-II,sauerkraut,21,2.5,72,5.08,table
kristek2004-II,sauerkraut,21,2.5,96,4.62,table
kristek2004-II,sauerkraut,21,2.5,120,4.21,table
kristek2004-II,sauerkraut,21,2.5,144,4.16,table
kristek2004-II,sauerkraut,21,2.5,168,4.08,table
kristek2004-II,sauerkraut,21,2.5,336,3.88,table
kristek2004-II,sauerkraut,21,2.5,504,3.74,table
kristek2004-II,sauerkraut,21,2.5,672,3.69,table
kristek2004-III,sauerkraut,21,2.5,0,6.28,table
kristek2004-III,sauerkraut,21,2.5,24,5.92,table
kristek2004-III,sauerkraut,21,2.5,48,5.54,table
kristek2004-III,sauerkraut,21,2.5,72,5.26,table
kristek2004-III,sauerkraut,21,2.5,96,4.80,table
kristek2004-III,sauerkraut,21,2.5,120,4.48,table
kristek2004-III,sauerkraut,21,2.5,144,4.30,table
kristek2004-III,sauerkraut,21,2.5,168,4.20,table
kristek2004-III,sauerkraut,21,2.5,336,3.92,table
kristek2004-III,sauerkraut,21,2.5,504,3.72,table
kristek2004-III,sauerkraut,21,2.5,672,3.66,table
kim2020,kimchi,20,,0,5.93,text
kim2020,kimchi,20,,48,4.43,text
kim2020,kimchi,20,,240,3.83,text
hong2016,kimchi,20,,48,4.41,text
foods2025,kimchi,15,2.3,0,5.57,table
foods2025,kimchi,15,2.3,72,4.36,table
foods2025,kimchi,15,2.3,336,3.89,table
```

## Consistency and gaps

- Kimchi at ~20 °C: two independent sources put pH ≈ 4.4 at 48 h (Kim 2020, Hong 2016); the
  BC CDC fermented-foods guideline (3.3 Kimchi, 2023/2024) restates Kim 2020's "pH 4.6 or
  lower in 2 days at 20 °C". Foods 2025 reaches 4.36 at day 3 even at 15 °C.
- Sauerkraut (Kristek 2004, whole heads in brine) is slower in the first two days than
  kimchi: pH 5.3–5.5 at 48 h, 4.5–4.8 at 96 h, ~3.9 at 14 d.
- Gaps: no day-by-day homemade kimchi series inside 16–24 °C with stated salt; no shredded
  dry-salted kraut table (Johanningsmeier 2007 and Plengvidhya 2007 plot pH in figures only);
  no pickles or hot sauces.

## Model check (tests/test_lacto_literature.py)

| Date | Engine | Points inside the 90 % band | Misses |
|---|---|---|---|
| 2026-10-24 | L. plantarum + Leuconostoc, seasoning flora | 35 / 37 | kimchi 48 h (both studies): band ends at 4.44, median 5.26 |
| 2026-10-26 | + L. sakei (migration 0024) | 35 / 37 | Kristek's slowest cycle at 120 h (4.48 vs P95 4.44) and 144 h (4.30 vs 4.29) |

L. sakei brought kimchi at 20 °C to a 48 h median of 4.75 (band 3.98–5.55). Its known
limit is the species split: at 18 °C the model lets L. sakei lead the sauerkraut
lactobacilli (8.75 vs 7.54 log CFU/g on day 7), whereas Plengvidhya 2007 names L. plantarum
and the test checks the lactobacilli total only.

Kristek's sauerkraut sits at pH 5.3–5.5 at 48 h, so a normal kraut fails the "≤ 4.6
within 48 h at > 10 °C" line (BOT-002, cited to ANSES 2014-SA-0174 with no URL). Kimchi
meets it (BC CDC restates Kim 2020). Whether the line applies to dry-salted vegetables at
≥ 2 % salt is an open owner decision (site critique 2026-10-26, fix 3).
