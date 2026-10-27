# Recipe round 2: Noma and Sandor Katz

Group: `noma-katz`. Brief: `BRIEF-noma-katz.md` (rules 1-9 of `BRIEF.md` apply).
Provenance `chef_published` = a recognised practitioner's published recipe (Noma, Katz, or a
publication explicitly following their method). `catalogue_status` uses the three values of
`BRIEF.md`: `existing` (in `seed_data.py` and in `AROMA_INGREDIENTS`), `existing_no_aroma` (in
`seed_data.py` only), `new`.

Unit conventions used throughout (all from NIST-conversions unless a source gives grams):
1 lb = 453.6 g; 1 oz = 28.35 g; 1 US cup = 236.6 mL; 1 qt = 946 mL; 1 gal = 3.785 L;
1 Tbsp = 14.8 mL; 1 tsp = 4.93 mL; deg C = (deg F - 32) / 1.8. Water, juices and brines are
taken at 1 g/mL. Salt % = salt / total batch mass (vegetable + water + salt + everything else).

## Summary

43 candidate recipes: lacto_ferment 20, miso 7, garum 5, kombucha 4, vinegar 4, koji 2, kefir 1. Status: 17 active, 26 draft. All `chef_published`.

By origin: Noma (book excerpts, Noma channels, Zilber) 14; Noma 2 % rule family (rule-derived) 11; Katz (own text or direct adaptations) 10; Noma/Katz-inspired (Forager Chef, Koji Alchemy, wildfermentation.com guest posts) 8.

Read with care: the 11 `noma_rule_*` rows apply Noma's stated 2 % rule to produce Noma names as lacto ferments, borrowing time and temperature from the Lacto Blueberries recipe (soft fruit) or leaving them empty (brined vegetables); they are drafts the curator may collapse. Three Noma Projects rows (two peasos, mushroom garum) come from product ingredient declarations, not home recipes.

## A. Sources opened

Every number in this round comes from one of these pages, opened during the round (2026-10-26). Each recipe entry in section B repeats the citation with its locator.

- **SplendidTable-lacto-blueberries** — Redzepi, René; Zilber, David. 2018. "Lacto Blueberries", excerpted from *The Noma Guide to Fermentation* (Artisan Books), republished by The Splendid Table (American Public Media), 2018-10-31. URL: https://www.splendidtable.org/recipes/lacto-blueberries. Locator: ingredient list; fermentation step. *(used by 7 recipes)*
- **NomaProjects-lacto** — Redzepi & Zilber, "Lacto-Fermentation: noma's Not So Secret Ingredient" (book excerpt), Noma Projects journal. URL: https://nomaprojects.com/blogs/journal/lacto-fermentation-nomas-not-so-secret-ingredient. Locator: method paragraph (2 % salt by weight; days depend on desired sourness; blueberries, raspberries, mulberries, blackberries, white currants lacto-fermented each September). *(used by 13 recipes)*
- **KCRW-noma-kombucha** — Redzepi, René; Zilber, David. 2018. "Lemon Verbena Kombucha", excerpted from *The Noma Guide to Fermentation* (Artisan Books), published as "Noma at home: Lemon verbena kombucha", KCRW Good Food, 2018-11-02. URL: https://www.kcrw.com/shows/good-food/stories/noma-at-home-lemon-verbena-kombucha (opened in a browser; plain fetch is blocked by a bot checkpoint). Locator: ingredient list; "In-Depth Instructions" (28 °C lab; 7-9 days; pH); numbered steps 7-8. *(used by 3 recipes)*
- **WF-sauerkraut** — Katz, Sandor Ellix. "Making Sauerkraut" (easy sauerkraut recipe from *Wild Fermentation*, Chelsea Green, 2003), wildfermentation.com, posted 2012-04-27. URL: https://www.wildfermentation.com/making-sauerkraut-2/. Locator: "Timeframe" line and ingredient list. *(used by 1 recipe)*
- **WF-sour-pickles** — Katz, S. E. "Making Sour Pickles" (excerpt from *Wild Fermentation*), wildfermentation.com, 2012-04-27. URL: https://www.wildfermentation.com/making-sour-pickles-2/. Locator: brine-strength paragraph (1 Tbsp sea salt weighs about 0.6 oz; 15 mL salt weighs 17 g). *(used by 2 recipes)*
- **CG-art-kraut** — Katz, "Making the Best Sauerkraut on Earth in Four Simple Steps: Chop, Salt, Pack, Wait" (excerpt from *The Art of Fermentation*, Chelsea Green 2012), Chelsea Green blog. URL: https://www.chelseagreen.com/blog/chop-salt-pack-wait-four-simple-steps-to-making-the-best-sauerkraut-on-earth/. Locator: "Steps for Fermenting Vegetables" (method only, no numbers). *(used by 0 recipes)*
- **CG-sour-pickles** — Katz, S. E. "Sour Pickles" (excerpt from *Wild Fermentation*) within "Unique Pickling Ideas: We Can Pickle That!", Chelsea Green blog. URL: https://www.chelseagreen.com/blog/we-can-pickle-that/. Locator: "RECIPE: Sour Pickles" (same quantities, confirms the WF page). *(used by 1 recipe)*
- **ST-chicken-garum** — Redzepi, René; Zilber, David. 2018. "Roasted Chicken Wing Garum", excerpted from *The Noma Guide to Fermentation* (Artisan Books), The Splendid Table, 2018-10-31. URL: https://www.splendidtable.org/story/2018/10/31/roasted-chicken-wing-garum. Locator: ingredient list; steps (stock, roasting, combining, 60 °C fermentation, skimming). *(used by 1 recipe)*
- **NomaProjects-garum** — Redzepi & Zilber, "Garum: Got to Have the Funk" (book excerpt), Noma Projects journal. URL: https://nomaprojects.com/blogs/journal/garum-got-to-have-the-funk. Locator: paragraphs on the 60 °C room (10-12 weeks for meat garums) and salt "about 12 % by weight". *(used by 1 recipe)*
- **ST-perry-vinegar** — Redzepi, René; Zilber, David. 2018. "Perry Vinegar", excerpted from *The Noma Guide to Fermentation* (Artisan Books), The Splendid Table, 2018. URL: https://splendidtable.org/recipes/perry-vinegar. Locator: yield, ingredient list, first fermentation (18 °C, 7-10 days), pasteurisation (70 °C, 15 min), backslop (20 % of perry weight; 1.8 kg perry -> 360 g vinegar), aeration (10-14 days), pH note. *(used by 1 recipe)*
- **NomaProjects-vinegar** — Redzepi & Zilber, "Vinegar: How to Improve Practically Anything" (book excerpt), Noma Projects journal, https://nomaprojects.com/blogs/journal/vinegar-how-to-improve-practically-anything (yeast stage 10-14 days to 6-7 % ABV; heat to 70 °C; aerate 10-14 days; AAB need 6-8 % ABV for ~5 % acidity; fruit under 14 °Bx needs added ethanol). *(used by 1 recipe)*
- **ST-katz-kombucha** — Katz, Sandor Ellix. "Making kombucha, an excerpt from *The Art of Fermentation*" (Chelsea Green, 2012), The Splendid Table, 2012-05-18. URL: https://www.splendidtable.org/story/2012/05/18/making-kombucha-an-excerpt-from-the-art-of-fermentation. Locator: tea, sweetening, acidifying and temperature paragraphs. *(used by 1 recipe)*
- **ST-katz-kombucha-interview** — Katz, interviewed by Lynne Rossetto Kasper, "How to make kombucha, the mother of fermented drinks", The Splendid Table, 2013-05-16. URL: https://www.splendidtable.org/story/2013/05/16/how-to-make-kombucha-the-mother-of-fermented-drinks. Locator: answer on method ("anywhere from a week to 2 weeks"). *(used by 1 recipe)*
- **MrPorter-lacto-ceps** — Taylor, Heather. "How To Ferment Like Mr René Redzepi", *The Journal*, MR PORTER (n.d., 2018 book promotion; photographs courtesy of Artisan), reproducing the Lacto Ceps recipe from Redzepi & Zilber, *The Noma Guide to Fermentation* (Artisan, 2018). URL: https://www.mrporter.com/en-gb/journal/lifestyle/how-to-ferment-like-mr-ren-redzepi-428028 (opened in a browser; plain fetch returns 403). Locator: recipe block ("Makes 1kg lacto mushrooms and juice"). *(used by 3 recipes)*
- **PDX-lacto-mushrooms** — "Make Noma's Umami Bomb Mushrooms in Your Home Kitchen", *Portland Monthly*, 2019-09-23 (October 2019 issue), adapting David Zilber's lacto-mushroom recipe from the book. URL: https://www.pdxmonthly.com/articles/2019/9/23/make-nomas-umami-bomb-mushrooms-in-your-home-kitchen. Locator: recipe steps. *(used by 1 recipe)*
- **EcoWatch-apple-kombucha** — Barth, Brian. "How to Make Apple Kombucha", EcoWatch, 2018-10-17 (reposted from *Modern Farmer*), reproducing "Apple Kombucha" from Redzepi & Zilber, *The Noma Guide to Fermentation*. URL: https://www.ecowatch.com/how-to-make-apple-kombucha-2613052862.html. Locator: headnote, ingredient list, steps 1-2. *(used by 1 recipe)*
- **FDC-173933** — USDA FoodData Central (SR Legacy) 173933 "Apple juice, canned or bottled, unsweetened, without added ascorbic acid", read offline from `src/fermenttrack/fdc_catalog_v1.csv.gz`: sugars_total 9.62 g/100 g. *(used by 1 recipe)*
- **Munchies-coffee-kombucha** — Zilber, David. "Coffee Kombucha Recipe", VICE (Munchies), 2018-11-07. URL: https://www.vice.com/en/article/coffee-kombucha-recipe/. Locator: yield, ingredient list, directions. *(used by 1 recipe)*
- **GR-noma-highlights** — Redzepi, René; Zilber, David. *The Noma Guide to Fermentation* (Artisan, 2018), verbatim Kindle highlights published by a reader (Jason Toups) on Goodreads, "Kindle Notes & Highlights for Foundations of Flavor: The Noma Guide to Fermentation". URL: https://www.goodreads.com/notes/39351834-foundations-of-flavor/37025960-jason-toups. Locator: Lacto Plums highlights (2 % of pitted weight, 950 g -> 19 g; 28 °C 5 days; 21 °C 6-7 days; ~125 mL juice; kahm yeast), lacto chapter highlights (2 % rule; brine method; safety rule pH < 5 within two days and < 4.6 at completion). *(used by 12 recipes)*
- **Interview-zilber-caviar** — Zilber, David (as told to *Interview* magazine). "How to Ruin Perfectly Good Caviar with Noma's David Zilber", *Interview*, Winter 2019 issue. URL: https://www.interviewmagazine.com/culture/david-zilber-noma-how-to-ruin-perfectly-good-caviar. Locator: numbered quotes "Grow koji", "Blend your kilo of caviar...", "Pour the blended...", "Strain". *(used by 2 recipes)*
- **NomaProjects-microbes** — Redzepi & Zilber, "Setting the Table for Microbes" (book excerpt), Noma Projects journal. URL: https://nomaprojects.com/blogs/journal/setting-the-table-for-microbes. Locator: *Aspergillus oryzae* paragraph (30 °C and 70-80 % humidity ideal; above 42 °C kills it; grows on cooked rice or barley; secretes protease, amylase, a little lipase). *(used by 1 recipe)*
- **CG-katz-persimmon-vinegar** — Katz, Sandor Ellix. "The Promising Persimmon: How to Make Persimmon Vinegar" (excerpt from *Sandor Katz's Fermentation Journeys*, Chelsea Green, 2021), Chelsea Green blog. URL: https://www.chelseagreen.com/blog/how-to-make-persimmon-vinegar/. Locator: "Making Persimmon Vinegar" (Time Frame, Ingredients, Process). *(used by 1 recipe)*
- **CG-koji-alchemy-amino-paste** — Umansky, Jeremy; Shih, Rich. "Greater Flavor: How to Make A Basic Miso Paste" (excerpt from *Koji Alchemy*, Chelsea Green, 2020), Chelsea Green blog. URL: https://www.chelseagreen.com/blog/basic-amino-paste/. Locator: "What You Need to Make Miso" (quotes "a simple guideline from Sandor Katz's *The Art of Fermentation*"), "Basic Amino Paste" ingredient lists (Light / Dark) and procedure. *(used by 2 recipes)*
- **NP-elderflower-peaso** — Noma Projects. "Elderflower Peaso" (product page), nomaprojects.com, published 2026-01-21. URL: https://nomaprojects.com/products/elderflower-peaso-miso. Locator: "Ingredients and Nutrition" (yellow split peas 60 %, rice koji, elderflower 5 %, salt; nutrition salt 5 g per 100 g); "Salt" section (5 % vs 12-18 % for traditional misos); story (pulp from elderflower oil combined with cooked split peas, rice koji and salt; aged three months; flavoured peasos take pulp at 5 % of total weight). *(used by 2 recipes)*
- **NomaProjects-peaso** — Noma Projects journal, "The Lab Dispatch: Miso" (https://nomaprojects.com/blogs/journal/the-lab-dispatch-miso; peaso 4 % salt vs 12-20 % for Japanese miso) and "What's the Difference: Miso Versus Peaso" (https://nomaprojects.com/blogs/journal/what-s-the-difference-miso-versus-peaso; 4 % salt vs typical 8 %; brighter, fruitier flavour). *(used by 2 recipes)*
- **NP-flavor-box** — Noma Projects, "Flavor Box 1" (Taste Buds box page), nomaprojects.com. URL: https://nomaprojects.com/pages/tb26-box1. Locator: Cep Tamari and Ryeso paragraphs (rice koji first; peaso is a three-month fermentation of yellow split peas mixed with koji and salt into a thick paste; ryeso made the same way from rye bread, rice koji and salt, aged at least three months). *(used by 1 recipe)*
- **NP-kyoto-peaso** — Noma Projects. "Kyoto Peaso" (product page), nomaprojects.com, published 2026-02-10. URL: https://nomaprojects.com/products/kyoto-peaso. Locator: "Ingredients and Nutrition" (yellow split peas (Denmark) 34 %, rice koji (rice, koji culture), kanzuri paste (red pepper, koji, yuzu) 22 %, salt; nutrition per 100 g: 586 kJ, fat 1 g, saturates 0 g, carbohydrate 27 g, sugars 1 g, protein 6 g, salt 5 g). Field order of the panel checked against the page's table labels. *(used by 1 recipe)*
- **NP-mushroom-garum** — Noma Projects. "Mushroom Garum" (product page), nomaprojects.com, published 2024-03-12. URL: https://nomaprojects.com/products/mushroom-garum. Locator: "Ingredients and Nutrition" (water, mushrooms 34 %, oats, rice koji, salt; nutrition per 100 g: carbohydrate 8.5 g, sugars 6.5 g, protein 4.2 g, salt 7 g) and product story (combines fermented mushrooms, rice koji and Oat Garum made from oat-milk by-products; koji instead of fish enzymes gives less salty garums). *(used by 1 recipe)*
- **NP-about-garums** — Noma Projects journal, "About Garums". URL: https://nomaprojects.com/blogs/journal/about-garums. Locator: process paragraph (press the raw ingredient, mix with salt and water, ferment 6 to 10 weeks depending on the ingredient, strain). *(used by 1 recipe)*
- **WF-garbanzo-miso** — Greenforest, Favero. "Cobbler time – Sweet Garbanzo Miso", guest post on wildfermentation.com (Sandor Katz's site), 2013-08-03. URL: https://www.wildfermentation.com/cobbler-time-sweet-garbanzo-miso/. Locator: batch list. *(used by 1 recipe)*
- **WF-black-bean-miso** — Greenforest, Favero. "Black bean Miso with Smoked Salt", guest post on wildfermentation.com, 2012-09-01. URL: https://www.wildfermentation.com/black-bean-miso-with-smoked-salt/. Locator: ingredient list and paragraph on timing. *(used by 1 recipe)*
- **NNS-katz-kimchi** — Nature and Nurture Seeds. "Chinese (Napa) Cabbage" page, kimchi recipe "by our fermentation guru Sandor Katz", "adapted from *Wild Fermentation*... by Sandor Ellix Katz, pg. 47 (2003)". URL: https://natureandnurtureseeds.com/pages/chinese-napa-cabbage. Locator: kimchi ingredient list and steps 1-5. *(used by 1 recipe)*
- **CG-katz-mexican-kimchi** — Katz, Sandor Ellix. "Kick Your Kimchi Up a Notch!" (excerpt from *Sandor Katz's Fermentation Journeys*, Chelsea Green, 2021), Chelsea Green blog. URL: https://www.chelseagreen.com/blog/mexican-inspired-kimchi/. Locator: "Mexican-Inspired Kimchi" (Timeframe, Ingredients for 2 quarts/2 liters, Process). *(used by 1 recipe)*
- **EYB-katz-kefir-WF** — Eat Your Books recipe index, "Kefir", from Katz, *Wild Fermentation*, 2nd edition (Chelsea Green, 2016), page 119. URL: https://www.eatyourbooks.com/library/recipes/3399309/kefir. Locator: ingredients (milk, kefir grains), serves approx. 1 quart/litre, takes 1-3 days. *(used by 1 recipe)*
- **EYB-katz-kefir-AoF** — Eat Your Books recipe index, "Kefir", from Katz, *The Art of Fermentation* (2012), page 192. URL: https://www.eatyourbooks.com/library/recipes/3352748/kefir. Locator: "Ferments for 24 hours. See recipe for variations." *(used by 1 recipe)*
- **FC-meat-garum** — Bergo, Alan. "Meat Garum", Forager Chef (foragerchef.com), published 2019-02-09, modified 2023-08-05. URL: https://foragerchef.com/meat-garum/. Locator: introduction (planned after reading the Noma Guide; book uses beef, barley koji, a 140 °F hold for 70 days per the author) and recipe card ("adapted from the Noma Guide to Fermentation": ingredients, dehydrator at 140 °F, remove after 30 days). *(used by 1 recipe)*
- **FC-ramp-garum** — Bergo, Alan. "Ramp Leaf Garum (Vegan Fish Sauce)", Forager Chef, published 2022-05-21. URL: https://foragerchef.com/ramp-leaf-garum-vegan-fish-sauce/. Locator: intro ("my meat garum recipe I modified from the Noma Guide to Fermentation"), "Koji: The Secret" (soy sauce and garum ~18 % salt; koji lets salty liquids ferment; 145-150 °F for thirty days; 3 % salt first if no koji), recipe card. *(used by 1 recipe)*
- **FC-scrap-vinegar** — Bergo, Alan. "Fruit Scrap Vinegar", Forager Chef, published 2020-04-11, modified 2025-12-09. URL: https://foragerchef.com/fruit-scrap-vinegar/. Locator: intro ("a hybrid of two of my favorites: one from the Art of Fermentation by Sandor Katz, and the other by Rene Redzepi in the Noma Guide... The Sandor Katz recipe is the most basic... fruit and sugar water"), "Classic Fruit Scrap Vinegar" card, and the accelerated card (for the 1/4 cup = 50 g sugar conversion). *(used by 2 recipes)*
- **FC-wild-mushroom-fermentation** — Bergo, Alan. "Wild Mushroom Fermentation", Forager Chef, published 2020-02-08, modified 2023-08-05. URL: https://foragerchef.com/wild-mushroom-fermentation/. Locator: text (Noma Guide's lacto-fermented porcini and dryad-saddle condiments; Katz's *Wild Fermentation* in the book list; brine at 2-5 %, faster at 2 % and slower at 5 %; kimchee-style ~7 %; mushroom ferments end around pH 3-3.5 after 2-4 weeks; FDA 4.6 line), "Brine Fermented Mushrooms" card and notes (3 % of total; 5-10 days, refrigerate after about 5; 7-14 days for decent flavour; vacuum version 3 % of mushroom weight). *(used by 1 recipe)*
- **CG-koji-alchemy-growing** — Umansky, Jeremy; Shih, Rich. "Growing Koji in Your Own Kitchen" (excerpt from *Koji Alchemy*, Chelsea Green, 2020), Chelsea Green blog. URL: https://www.chelseagreen.com/blog/growing-koji-in-your-own-kitchen/. Locator: requirements paragraph and steps 1-5. *(used by 1 recipe)*
- **CG-koji-alchemy-book** — Chelsea Green product page for *Koji Alchemy* (https://www.chelseagreen.com/product/koji-alchemy/): "Foreword by Sandor Ellix Katz"; praised by David Zilber. *(used by 0 recipes)*
- **TT-katz-sauerkraut** — "Sandor Katz's Sauerkraut" ("Recipe adapted from Sandor Katz"), Tasting Table, 2015-04-21. URL: https://www.tastingtable.com/cook/recipes/how-to-make-sauerkraut-sandor-katz-recipe. Locator: ingredient list and steps. *(used by 1 recipe)*
- **Morton-kosher** — Morton Salt, "Morton Coarse Kosher Salt" product page, nutrition facts "Serving Size 1/4 tsp (1.2g)". URL: https://www.mortonsalt.com/shop/kosher-salt/morton-coarse-kosher-salt/. *(used by 1 recipe)*


## B. Recipes

### noma_lacto_blueberries — Lacto blueberries (Noma)

- Sources: **SplendidTable-lacto-blueberries** — Redzepi, René; Zilber, David. 2018. "Lacto Blueberries", excerpted from *The Noma Guide to Fermentation* (Artisan Books), republished by The Splendid Table (American Public Media), 2018-10-31. URL: https://www.splendidtable.org/recipes/lacto-blueberries. Locator: ingredient list; fermentation step. **NomaProjects-lacto** — Redzepi & Zilber, "Lacto-Fermentation: noma's Not So Secret Ingredient" (book excerpt), Noma Projects journal. URL: https://nomaprojects.com/blogs/journal/lacto-fermentation-nomas-not-so-secret-ingredient. Locator: method paragraph (2 % salt by weight; days depend on desired sourness; blueberries, raspberries, mulberries, blackberries, white currants lacto-fermented each September).
- Facts copied: 1 kg blueberries; 20 g non-iodized salt; yield 1 kg; 28 °C (82 °F) for 4-5 days, or a few days longer at room temperature; berries should be slightly soured but keep their sweet, fruity perfume.
- Derivations: total = 1000 + 20 = 1020 g. Blueberries 1000/1020 = 980.4 g/kg; salt 20/1020 = 19.6 g/kg = 1.96 %. 4-5 days = 96-120 h, median 108 h. Temperature is a point value (28 °C).
- One-line method: Toss berries with 2 % salt, seal airless (vacuum bag or weighted jar), vent gas, and stop by chilling once lightly sour.
- Notes: 28 °C sits above the `lacto_ferment` 16-24 °C range; the "room temperature" alternative has no number, so it is not in the envelope. Salt of 1.96 % of total batch trips the 2 % SALT-001 warning by rounding only; Noma's rule is 2 % of the produce weight. Juice and pulp are both used downstream (condiment, coulis).

### noma_lemon_verbena_kombucha — Lemon verbena kombucha (Noma)

- Sources: **KCRW-noma-kombucha** — Redzepi, René; Zilber, David. 2018. "Lemon Verbena Kombucha", excerpted from *The Noma Guide to Fermentation* (Artisan Books), published as "Noma at home: Lemon verbena kombucha", KCRW Good Food, 2018-11-02. URL: https://www.kcrw.com/shows/good-food/stories/noma-at-home-lemon-verbena-kombucha (opened in a browser; plain fetch is blocked by a bot checkpoint). Locator: ingredient list; "In-Depth Instructions" (28 °C lab; 7-9 days; pH); numbered steps 7-8.
- Facts copied: yield 2 L; 240 g sugar; 1.76 kg water; 20 g dried lemon verbena; 200 g unpasteurized kombucha (stated as 10 % of the other ingredients); one SCOBY; syrup made with 240 g of the water, verbena steeped ~10 min; Noma's kombucha room at 28 °C (82 °F), room temperature also works but slower; 7-9 days to taste, an extra 1-2 days for a sourer result; infused syrup pH just under 7, about 5 after backslopping, 3.5-4 when close to ready; starter organisms do not survive above 60 °C.
- Derivations: total = 240 + 1760 + 20 + 200 = 2220 g. Per kg: water 792.8, sugar 108.1, lemon verbena 9.0, starter liquid 90.1. 7-9 days = 168-216 h, median 192 h.
- One-line method: Steep dried verbena in a hot sugar syrup, top up with cool water, backslop with 10 % mature kombucha, add a SCOBY and ferment under cloth until pH 3.5-4.
- Notes: Active: every number in the row is stated; the SCOBY pellicle itself is unweighed (the 200 g liquid starter is weighed), as in the round-1 Cohen2023 row. Sugar 108 g/kg is well above the profile's typical 70 g/kg; 28 °C is the top of the `kombucha` 20-28 °C range. The aromas recorded are only the two the source names (the target is a balance of sweetness and acidity that keeps the base ingredient's essence). This is Noma's template kombucha: other bases (teas, herbs, fruit juices) follow the same ratios in the book, but only this one was opened.

### katz_sauerkraut_basic — Basic sauerkraut (Katz, Wild Fermentation)

- Sources: **WF-sauerkraut** — Katz, Sandor Ellix. "Making Sauerkraut" (easy sauerkraut recipe from *Wild Fermentation*, Chelsea Green, 2003), wildfermentation.com, posted 2012-04-27. URL: https://www.wildfermentation.com/making-sauerkraut-2/. Locator: "Timeframe" line and ingredient list. **WF-sour-pickles** — Katz, S. E. "Making Sour Pickles" (excerpt from *Wild Fermentation*), wildfermentation.com, 2012-04-27. URL: https://www.wildfermentation.com/making-sour-pickles-2/. Locator: brine-strength paragraph (1 Tbsp sea salt weighs about 0.6 oz; 15 mL salt weighs 17 g). Also opened: **CG-art-kraut** — Katz, "Making the Best Sauerkraut on Earth in Four Simple Steps: Chop, Salt, Pack, Wait" (excerpt from *The Art of Fermentation*, Chelsea Green 2012), Chelsea Green blog. URL: https://www.chelseagreen.com/blog/chop-salt-pack-wait-four-simple-steps-to-making-the-best-sauerkraut-on-earth/. Locator: "Steps for Fermenting Vegetables" (method only, no numbers).
- Facts copied: 2 lb / 1 kg vegetables per quart / liter (any cabbages, or at least half cabbage with radish, turnip, carrot, beet, kohlrabi, Jerusalem artichoke, onion, shallot, leek, garlic, greens, peppers); approximately 1 Tbsp salt, starting with a little less and adding to taste; timeframe 3 days to 3 months (and beyond); faster in warm, slower in cool conditions. Katz's own conversion: 1 Tbsp (15 mL) sea salt = 17 g.
- Derivations: 1000 g vegetables + 17 g salt = 1017 g. Cabbage 983.3 g/kg; salt 16.7 g/kg = 1.67 %. 3 days-3 months = 72-2160 h (3 months taken as 90 days); midpoint median 1116 h.
- One-line method: Chop and lightly salt the vegetables, squeeze until juicy, pack hard into a jar under their own brine, and taste over days to months.
- Notes: Salt is "to taste" and the 1 Tbsp is approximate with a suggestion to start lower, so 1.67 % is a point anchor (`point`) that sits below the 2 % SALT-001 warning line. No temperature is given, so the envelope uses only time; the 3-month top exceeds the 672 h `lacto_ferment` horizon. The vegetable is recorded as Cabbage because the recipe requires at least half cabbage.

### katz_sour_pickles — Sour brine pickles (Katz, Wild Fermentation)

- Sources: **WF-sour-pickles** (defined above; ingredient list, "Timeframe: 1-4 weeks", brine-strength paragraph, process steps). **CG-sour-pickles** — Katz, S. E. "Sour Pickles" (excerpt from *Wild Fermentation*) within "Unique Pickling Ideas: We Can Pickle That!", Chelsea Green blog. URL: https://www.chelseagreen.com/blog/we-can-pickle-that/. Locator: "RECIPE: Sour Pickles" (same quantities, confirms the WF page).
- Facts copied: 3-4 lb / 1.5-2 kg unwaxed small-medium cucumbers; 3/8 cup (6 Tbsp) / 90 mL sea salt dissolved in 1/2 gallon / 2 L water; 3-4 heads flowering dill or 3-4 Tbsp (45-60 mL) dill; 2-3 heads garlic; a handful of grape/cherry/oak/horseradish leaves; a pinch of black peppercorns; timeframe 1-4 weeks depending on temperature; store in a cool place; Katz calls this ~5.4 % brine (half-sours ~3.5 %, egg-floating brine ~10 %); top-up brine just under 1 Tbsp salt per cup water; 15 mL salt = 17 g.
- Derivations: salt = 6 x 17 = 102 g. Median batch (1.75 kg cucumbers) = 1750 + 2000 + 102 = 3852 g: cucumber 454.3, water 519.2, salt 26.5 g/kg (2.65 %). Extremes: 1.5 kg -> 3602 g total, salt 2.83 %, cucumber 416.4, water 555.2; 2 kg -> 4102 g, salt 2.49 %, cucumber 487.6, water 487.6. 1-4 weeks = 168-672 h, median 420 h. Brine alone: 102 / 2102 = 4.85 % w/w (Katz's 5.4 % is a w/v approximation).
- One-line method: Lay dill, garlic and tannic leaves in a crock, add cucumbers, cover with ~5 % brine under a weighted plate, skim daily and taste until sour.
- Notes: Status `draft`, following round 1 (dill pickles): core aromatics (dill, garlic) are stated only as heads or spoons, not mass. Medians sum to 1000 g/kg without the unweighed aromatics (dill, garlic, leaves, peppercorns), which are listed with empty masses. No temperature number ("cool place"); time is the only envelope. Salt 2.5-2.8 % of total batch is inside the 2-10 % band.

### noma_chicken_wing_garum — Roasted chicken wing garum (Noma)

- Sources: **ST-chicken-garum** — Redzepi, René; Zilber, David. 2018. "Roasted Chicken Wing Garum", excerpted from *The Noma Guide to Fermentation* (Artisan Books), The Splendid Table, 2018-10-31. URL: https://www.splendidtable.org/story/2018/10/31/roasted-chicken-wing-garum. Locator: ingredient list; steps (stock, roasting, combining, 60 °C fermentation, skimming). **NomaProjects-garum** — Redzepi & Zilber, "Garum: Got to Have the Funk" (book excerpt), Noma Projects journal. URL: https://nomaprojects.com/blogs/journal/garum-got-to-have-the-funk. Locator: paragraphs on the 60 °C room (10-12 weeks for meat garums) and salt "about 12 % by weight".
- Facts copied: yield 1.5 L; 2 kg chicken bones simmered 3 h in about 3 L water for stock; 3 kg chicken wings roasted at 180 °C for 40-50 min, of which 2 kg chopped go into the ferment; 450 g pearl barley koji (commercial koji acceptable); 480 g non-iodized salt; 1.6 kg of the stock; plastic wrap on the surface, lid slightly ajar; 60 °C (or a rice cooker on keep-warm) for 4 weeks; skim fat daily in week 1, then weekly. Roasting gives developed flavour and umami so about a month suffices (beef or squid garums run longer). The general Noma garum excerpt gives salt about 12 % by weight and 10-12 weeks at 60 °C for meat garums.
- Derivations: ferment batch = 2000 + 450 + 480 + 1600 = 4530 g. Per kg: wings 441.5, stock 353.2, koji 99.3, salt 106.0 (10.6 %). 4 weeks = 672 h.
- One-line method: Make a chicken stock, roast and chop wings, mix with crumbled barley koji, salt and stock, and hold covered at 60 °C for four weeks, skimming fat, then strain.
- Notes: 60 °C sits inside the `garum` profile's 20-60 °C range at its top; 10.6 % salt is close to the profile's typical 12 %. Koji share ~10 % of the batch is below the profile note's 20-30 % koji. Koji recorded as Pearl barley in the starter role, following the round-1 convention for koji rows. Reported aromas: the source names umami and deep, meaty "ramen" tones from roasting (mapped to umami; roasty).

### noma_perry_vinegar — Perry (pear) vinegar (Noma)

- Sources: **ST-perry-vinegar** — Redzepi, René; Zilber, David. 2018. "Perry Vinegar", excerpted from *The Noma Guide to Fermentation* (Artisan Books), The Splendid Table, 2018. URL: https://splendidtable.org/recipes/perry-vinegar. Locator: yield, ingredient list, first fermentation (18 °C, 7-10 days), pasteurisation (70 °C, 15 min), backslop (20 % of perry weight; 1.8 kg perry -> 360 g vinegar), aeration (10-14 days), pH note. Also consistent with **NomaProjects-vinegar** — Redzepi & Zilber, "Vinegar: How to Improve Practically Anything" (book excerpt), Noma Projects journal, https://nomaprojects.com/blogs/journal/vinegar-how-to-improve-practically-anything (yeast stage 10-14 days to 6-7 % ABV; heat to 70 °C; aerate 10-14 days; AAB need 6-8 % ABV for ~5 % acidity; fruit under 14 °Bx needs added ethanol).
- Facts copied: yield about 2 L; 4 kg sweet ripe pears; 1 packet (35 mL) liquid saison yeast; first fermentation at about 18 °C for 7-10 days (warm fermentation gives murky, musty notes); perry heated to about 70 °C and held 15 min; backslop with unpasteurized pear (or mild, e.g. cider) vinegar at 20 % of the perry weight (1.8 kg perry -> 360 g); air-stone aeration for 10-14 days; pH 3.5-4 is usually right; the unaerated long method takes months. The finished vinegar is described as lightly sweet and fruity, less harsh than white wine vinegar; saison yeast gives a good bouquet.
- Derivations: acetic batch (worked example) = 1800 + 360 = 2160 g: perry 833.3 g/kg, vinegar starter 166.7 g/kg. 10-14 days = 240-336 h, median 288 h. 1F 7-10 days = 168-240 h.
- One-line method: Blend pears with saison yeast and ferment cool into perry, press and pasteurise, backslop with 20 % live vinegar and aerate with an air stone until sour.
- Notes: The `vinegar` profile starts from an alcoholic liquid, so the row describes the acetic stage; the upstream pear mash and yeast are listed with empty masses. No temperature is given for the acetic stage ("room temperature"), so temp fields are empty; 1F at 18 °C is in `stages`. Starter share 16.7 % is close to the profile's 15 %. The ABV of the perry is not stated on the page.

### katz_kombucha_basic — Kombucha, first ferment (Katz, Art of Fermentation)

- Sources: **ST-katz-kombucha** — Katz, Sandor Ellix. "Making kombucha, an excerpt from *The Art of Fermentation*" (Chelsea Green, 2012), The Splendid Table, 2012-05-18. URL: https://www.splendidtable.org/story/2012/05/18/making-kombucha-an-excerpt-from-the-art-of-fermentation. Locator: tea, sweetening, acidifying and temperature paragraphs. **ST-katz-kombucha-interview** — Katz, interviewed by Lynne Rossetto Kasper, "How to make kombucha, the mother of fermented drinks", The Splendid Table, 2013-05-16. URL: https://www.splendidtable.org/story/2013/05/16/how-to-make-kombucha-the-mother-of-fermented-drinks. Locator: answer on method ("anywhere from a week to 2 weeks").
- Facts copied: tea from *Camellia sinensis* (black, green, white, kukicha, pu-er; avoid Earl Grey), strength to taste; sugar to taste, "try about 1/2 cup / 125 mL (4 oz / 113 g) per quart/liter"; cool below body temperature; mature kombucha at about 5-10 % of the sweet-tea volume (or about 2 Tbsp / 30 mL vinegar per quart/liter if none); wide vessel, cloth cover; best at 75-85 °F / 24-30 °C; about 10 days in warm weather; at 60 °F / 16 °C it can take months; interview: a week to 2 weeks depending on kitchen temperature. Kombucha "sometimes compared to sparkling apple cider", usually drunk while still somewhat sweet.
- Derivations: per 1 L tea: 1000 g water + 113 g sugar + 50-100 g starter (median 75). Median total 1188 g: water 841.8, sugar 95.1, starter 63.1 g/kg. Extremes: starter 50 g -> 1163 g total (sugar 97.2, starter 43.0, water 859.8); starter 100 g -> 1213 g total (sugar 93.2, starter 82.4, water 824.4). Temperature 24-30 °C, median 27 °C. Time: AoF ~10 days (240 h, point) and interview 168-336 h (median 252 h); median across sources 246 h, range 168-336 h.
- One-line method: Sweeten tea at roughly 113 g sugar per litre, cool, acidify with 5-10 % mature kombucha, float a mother on top and ferment under cloth in a warm spot, tasting until tart but still sweet.
- Notes: Draft because no tea mass is given. Starter treated at 1 g/mL. Sugar 95 g/kg is above the profile's typical 70 g/kg; 24-30 °C slightly overshoots the 20-28 °C profile range at the top.

### noma_lacto_ceps — Lacto ceps / porcini and their juice (Noma)

- Sources: **MrPorter-lacto-ceps** — Taylor, Heather. "How To Ferment Like Mr René Redzepi", *The Journal*, MR PORTER (n.d., 2018 book promotion; photographs courtesy of Artisan), reproducing the Lacto Ceps recipe from Redzepi & Zilber, *The Noma Guide to Fermentation* (Artisan, 2018). URL: https://www.mrporter.com/en-gb/journal/lifestyle/how-to-ferment-like-mr-ren-redzepi-428028 (opened in a browser; plain fetch returns 403). Locator: recipe block ("Makes 1kg lacto mushrooms and juice"). **PDX-lacto-mushrooms** — "Make Noma's Umami Bomb Mushrooms in Your Home Kitchen", *Portland Monthly*, 2019-09-23 (October 2019 issue), adapting David Zilber's lacto-mushroom recipe from the book. URL: https://www.pdxmonthly.com/articles/2019/9/23/make-nomas-umami-bomb-mushrooms-in-your-home-kitchen. Locator: recipe steps. **NomaProjects-lacto** (defined above): ceps lacto-fermented into a seasoning liquid.
- Facts copied: Mr Porter: 1 kg cleaned ceps frozen at least 24 h; 20 g non-iodized salt; vacuum-sealed in one layer; 5-6 days at 28 °C (82 °F), or a few days longer at room temperature, tasting from the first few days; yield 1 kg mushrooms and juice; the juice is "the true prize". The general rule quoted there: weigh, add 2 % salt by weight, wait. PDX: 1 lb cleaned mushrooms (porcini, chanterelle, shiitake, oyster) frozen 24 h; roughly 1 Tbsp kosher salt or 2 % of mushroom weight; jar weighted with a water bag, loose lid; warm place out of direct sun, roughly a week at room temperature.
- Derivations: 1000 + 20 = 1020 g: mushrooms 980.4 g/kg, salt 19.6 g/kg = 1.96 %. Time: Mr Porter 5-6 days at 28 °C (120-144 h); PDX ~1 week (168 h) at room temperature; range 120-168 h, midpoint 144 h. Temperature recorded as the stated 28 °C (point); the room-temperature alternative has no number.
- One-line method: Freeze cleaned ceps, toss with 2 % salt, vacuum-seal (or weight in a jar), ferment warm until they weep, yellow and sour, then separate mushrooms from juice.
- Notes: 28 °C is above the `lacto_ferment` 16-24 °C range; PDX's room-temperature week falls inside it. Salt 1.96 % of total sits at the SALT-001 2 % line by rounding (2 % of produce weight). Porcini is a new catalogue ingredient; reported aromas: soured, earthy/funky, a seasoning juice (mapped to sour; mushroom; umami).

### noma_apple_kombucha — Apple kombucha (Noma)

- Sources: **EcoWatch-apple-kombucha** — Barth, Brian. "How to Make Apple Kombucha", EcoWatch, 2018-10-17 (reposted from *Modern Farmer*), reproducing "Apple Kombucha" from Redzepi & Zilber, *The Noma Guide to Fermentation*. URL: https://www.ecowatch.com/how-to-make-apple-kombucha-2613052862.html. Locator: headnote, ingredient list, steps 1-2. **KCRW-noma-kombucha** (defined above; the apple recipe names Lemon Verbena Kombucha as its template: 28 °C lab, pH 3.5-4 when close to ready). **FDC-173933** — USDA FoodData Central (SR Legacy) 173933 "Apple juice, canned or bottled, unsweetened, without added ascorbic acid", read offline from `src/fermenttrack/fdc_catalog_v1.csv.gz`: sugars_total 9.62 g/100 g.
- Facts copied: 2 kg unfiltered apple juice (or good unfiltered store-bought cider); no added sugar because the juice is sweet; 200 g unpasteurized kombucha (or the SCOBY's packing liquid); 1 SCOBY; cloth cover; warm place; 7-10 days to taste; the Lemon Verbena Kombucha instructions are the template for all the book's kombuchas. Serving ideas: 25 g fir needles or 10 g rosemary blended with 500 g kombucha; 4:1 kombucha to cooked vegetable smoothies.
- Derivations: 2000 + 200 = 2200 g: apple juice 909.1, starter 90.9 g/kg. Sugar (derived, FDC proxy): 2000 x 0.0962 = 192.4 g -> 87.5 g/kg. 7-10 days = 168-240 h, median 204 h. Temperature 28 °C taken from the template (Noma's kombucha room), flagged.
- One-line method: Backslop unfiltered apple juice with 10 % mature kombucha, lay on a SCOBY, cover with cloth and ferment warm for about a week.
- Notes: Active (every number in the row is stated or derived from a named offline source), but sugar and temperature are flagged as derived/template values. No aromas are stated beyond serving suggestions, so `reported_aromas` is empty. Apple juice is a new ingredient (catalogue has Apple as a flavoring).

### noma_coffee_kombucha — Coffee kombucha (Noma)

- Sources: **Munchies-coffee-kombucha** — Zilber, David. "Coffee Kombucha Recipe", VICE (Munchies), 2018-11-07. URL: https://www.vice.com/en/article/coffee-kombucha-recipe/. Locator: yield, ingredient list, directions. Context: Noma uses a coffee kombucha in tiramisu (MrPorter-lacto-ceps article). **KCRW-noma-kombucha** (template: 28 °C lab, pH 3.5-4).
- Facts copied: makes 2 L; 240 g granulated sugar; 1.76 kg water; 730 g leftover coffee grounds or 200 g freshly ground coffee; 200 g unpasteurized kombucha; 1 SCOBY; sugar boiled with 240 g of the water and poured over the coffee, rest of the water added, cooled and infused overnight in the fridge, then strained; backslop, SCOBY, cloth cover, warm place; 7-10 days.
- Derivations: fresh-coffee option: 240 + 1760 + 200 + 200 = 2400 g: water 733.3, sugar 100.0, coffee 83.3, starter 83.3 g/kg. Spent-grounds option: 2930 g total; sugar 81.9, water 600.7, grounds 249.1, starter 68.3 g/kg (in notes only; the grounds are mostly absorbed water and are strained off). 7-10 days = 168-240 h, median 204 h.
- One-line method: Pour a hot sugar syrup over coffee grounds, top up with water and cold-infuse overnight, strain, backslop with 10 % kombucha, add a SCOBY and ferment warm.
- Notes: Same 240 g sugar / 1.76 kg water / 200 g starter frame as the lemon verbena template. Coffee and its strained grounds count in the batch as tea leaves did in round 1. No aromas stated.

### noma_lacto_plums — Lacto plums (Noma)

- Sources: **GR-noma-highlights** — Redzepi, René; Zilber, David. *The Noma Guide to Fermentation* (Artisan, 2018), verbatim Kindle highlights published by a reader (Jason Toups) on Goodreads, "Kindle Notes & Highlights for Foundations of Flavor: The Noma Guide to Fermentation". URL: https://www.goodreads.com/notes/39351834-foundations-of-flavor/37025960-jason-toups. Locator: Lacto Plums highlights (2 % of pitted weight, 950 g -> 19 g; 28 °C 5 days; 21 °C 6-7 days; ~125 mL juice; kahm yeast), lacto chapter highlights (2 % rule; brine method; safety rule pH < 5 within two days and < 4.6 at completion). **SplendidTable-lacto-blueberries** (defined above): states that Lacto Plums is the book's template for its lactic ferments.
- Facts copied: weigh pitted plums and take 2 % of that weight as salt (950 g plums -> 19 g salt); cut into eighths for a jar, or halves in a vacuum bag; 28 °C (82 °F): usually 5 days; 21 °C (70 °F): 6-7 days; taste daily; skim kahm yeast; about 125 mL juice depending on ripeness; refrigerate up to a week. General: a ferment that reaches pH < 5 within two days and < 4.6 by completion is generally recognised as safe.
- Derivations: 950 + 19 = 969 g: plums 980.4, salt 19.6 g/kg = 1.96 %. Two stated conditions give temp 21-28 °C (midpoint 24.5) and time 120-168 h (midpoint 144 h); the pairs are linked (28 °C -> 120 h, 21 °C -> 144-168 h).
- One-line method: Pit and cut ripe plums, toss with 2 % of their weight in salt, seal airless and ferment warm about five days, tasting daily, then separate fruit and juice.
- Notes: The 21 °C condition sits inside the `lacto_ferment` profile range; 28 °C sits above it. The source is a reader's highlights rather than the publisher's page, but the passages are verbatim book text and agree with Noma's own excerpt (NomaProjects-lacto) on the 2 % rule.

### zilber_caviar_koji_garum — Caviar rice-koji garum (David Zilber, Noma)

- Sources: **Interview-zilber-caviar** — Zilber, David (as told to *Interview* magazine). "How to Ruin Perfectly Good Caviar with Noma's David Zilber", *Interview*, Winter 2019 issue. URL: https://www.interviewmagazine.com/culture/david-zilber-noma-how-to-ruin-perfectly-good-caviar. Locator: numbered quotes "Grow koji", "Blend your kilo of caviar...", "Pour the blended...", "Strain".
- Facts copied: rice koji grown on steamed rice inoculated with *A. oryzae*, incubated 48 h at 28 °C and 75 % relative humidity (rice koji preferred for a cleaner finish than barley or wheat); 1 kg caviar blended with 250 g koji, 500 g water and 140 g salt; caviar is normally salted at 3 %, extra salt here because it stays a full year at room temperature; covered but not airtight; rest one year; strain through a coffee filter.
- Derivations: 1000 + 250 + 500 + 140 = 1890 g: caviar 529.1, koji 132.3, water 264.6, salt 74.1 g/kg (7.41 %). One year = 8760 h.
- One-line method: Blend roe with rice koji, water and salt, cover loosely and leave a year at room temperature, then filter off the clear sauce.
- Notes: Salt 7.4 % is well below the profile's typical 12 % and traditional fish sauces; the piece is satirical in tone (albino caviar, "offend the sensibilities"), but every quantity is stated. Room temperature has no number, so temp fields are empty; 8760 h exceeds the `garum` 180-day horizon. Koji recorded as White rice in the starter role (round-1 convention). Koji share 13 % sits below the profile note's 20-30 %.

### zilber_rice_koji — Rice koji (David Zilber, Noma)

- Sources: **Interview-zilber-caviar** (defined above; "Grow koji" step). **NomaProjects-microbes** — Redzepi & Zilber, "Setting the Table for Microbes" (book excerpt), Noma Projects journal. URL: https://nomaprojects.com/blogs/journal/setting-the-table-for-microbes. Locator: *Aspergillus oryzae* paragraph (30 °C and 70-80 % humidity ideal; above 42 °C kills it; grows on cooked rice or barley; secretes protease, amylase, a little lipase).
- Facts copied: steam rice, inoculate with *A. oryzae* spores, incubate 48 h at 28 °C and 75 % RH (Zilber); 30 °C and 70-80 % humidity generally ideal, above 42 °C lethal (book excerpt).
- Derivations: temp 28-30 °C across the two sources, median 29 °C; 48 h (point). Substrate normalised to 1000 g/kg white rice, as the round-1 single-grain koji row.
- One-line method: Steam rice, cool, dust with koji spores and hold 48 h warm and humid until the grains are bound in white mycelium.
- Notes: Draft: no rice, water or spore masses. 28-30 °C and 48 h sit inside the `koji` profile (28-35 °C; 72 h horizon). Noma's book also has a Pearl Barley Koji recipe (used in the chicken-wing garum) whose numbers were not opened (see Unverified leads).

### katz_persimmon_vinegar — Persimmon vinegar (Katz, Fermentation Journeys)

- Sources: **CG-katz-persimmon-vinegar** — Katz, Sandor Ellix. "The Promising Persimmon: How to Make Persimmon Vinegar" (excerpt from *Sandor Katz's Fermentation Journeys*, Chelsea Green, 2021), Chelsea Green blog. URL: https://www.chelseagreen.com/blog/how-to-make-persimmon-vinegar/. Locator: "Making Persimmon Vinegar" (Time Frame, Ingredients, Process).
- Facts copied: about 3 months in a cool environment; ingredients for roughly 2 cups / 500 mL: 2 lb / 1 kg persimmons (any kind; firm Fuyu/Hachiya per Hachisu, or ripe American persimmons); remove calyx; cloth-covered crock; stir every day or two as the fruit softens and bubbles; once bubbling subsides and it tastes a little vinegary, leave covered for a few months, tasting every week or two; a mother may or may not form; drink young as a light vinegar or ferment 2-3 months for higher acidity; harvest before hot weather; press the mash through muslin.
- Derivations: single ingredient, 1000 g/kg. 2-3 months = 1440-2160 h (30-day months), median 1800 h.
- One-line method: Leave whole de-crowned persimmons under a cloth to soften, ferment and sour on their own, stirring early, then strain and press after two to three months.
- Notes: The `vinegar` profile starts from an alcoholic liquid with a starter; this is a spontaneous whole-fruit vinegar (yeast then acetic bacteria, no starter, no added sugar), so the profile fits only the second half. No temperature number ("cool environment"). The companion Persimmon Pickling Medium (250 g vegetables, 1-2 Tbsp coarse salt, ~500 g pulp, 2-3 days) is listed under Out of model.

### katz_miso_short_light — Short-term light miso, 1:1 koji to beans (Katz guideline)

- Sources: **CG-koji-alchemy-amino-paste** — Umansky, Jeremy; Shih, Rich. "Greater Flavor: How to Make A Basic Miso Paste" (excerpt from *Koji Alchemy*, Chelsea Green, 2020), Chelsea Green blog. URL: https://www.chelseagreen.com/blog/basic-amino-paste/. Locator: "What You Need to Make Miso" (quotes "a simple guideline from Sandor Katz's *The Art of Fermentation*"), "Basic Amino Paste" ingredient lists (Light / Dark) and procedure.
- Facts copied: Katz's guideline as quoted: short-term (two weeks to three months) miso = 1 part koji to 1 part base by weight plus 6 % salt against the total (the authors typically use 5 %); long-term = 1 part koji to 2 parts base plus 13 % salt. Koji Alchemy Light recipe (2 weeks-3 months): 250 g koji, 25 g kosher salt, 250 g protein; dry koji hydrated with 25 g water; store at ambient temperature; pack tightly, purée at least half, salt the surface and weight it with a small gap for CO2.
- Derivations: Katz: salt 6 % -> koji = base = (1000 - 60) / 2 = 470 g/kg. KA: 250 + 250 + 25 = 525 g -> koji = base = 476.2, salt 47.6 g/kg (4.76 %). Ranges cover both; medians are midpoints (koji/base 473.1, salt 53.8 g/kg = 5.38 %). 2 weeks-3 months = 336-2160 h, midpoint 1248 h.
- One-line method: Knead salt into koji, mash in an equal weight of cooked beans (half puréed), pack airless under a salted, weighted cover and age a few weeks to three months at room temperature.
- Notes: Draft because the base and koji grain are free choices (soybeans and rice koji are recorded as the traditional default, in the round-1 convention: koji as White rice, role starter). Salt 4.8-6 % sits between Noma's 4-5 % peaso and the Kagawa sweet miso (5.5-6.6 %). Koji share ~47 % gives the high koji enzyme load of a sweet miso (profile note: up to ~0.7 for sweet white miso).

### katz_miso_long_dark — Long-term dark miso, 1:2 koji to beans (Katz guideline)

- Sources: **CG-koji-alchemy-amino-paste** (defined above; Katz guideline paragraph and Dark recipe).
- Facts copied: long-term (six months to several years) "dark" miso driven by umami = 1 part koji to 2 parts base by weight plus 13 % salt against the total (Katz, as quoted); Koji Alchemy Dark recipe (6 months-1 year+): 165 g koji, 65 g kosher salt, 330 g protein; ambient temperature.
- Derivations: Katz: salt 130 g/kg; koji = 870/3 = 290, base = 580 g/kg. KA: 165 + 330 + 65 = 560 g -> koji 294.6, base 589.3, salt 116.1 g/kg (11.6 %). Midpoints: koji 292.3, base 584.6, salt 123.0 g/kg (12.3 %). 6-12 months = 4320-8760 h, midpoint 6540 h ("1 year+" open-ended).
- One-line method: Knead salt into koji, mash in twice its weight of cooked beans, pack airless under a salted, weighted cover and age six months to a year or more.
- Notes: Draft for the same reason as the light version (free choice of base and koji). Salt 11.6-13 % brackets the Kagawa red miso (10.7-13 %) and the profile's typical 11 %. The upper duration exceeds the 180-day `miso` horizon.

### noma_elderflower_peaso — Elderflower peaso, yellow split pea miso (Noma Projects)

- Sources: **NP-elderflower-peaso** — Noma Projects. "Elderflower Peaso" (product page), nomaprojects.com, published 2026-01-21. URL: https://nomaprojects.com/products/elderflower-peaso-miso. Locator: "Ingredients and Nutrition" (yellow split peas 60 %, rice koji, elderflower 5 %, salt; nutrition salt 5 g per 100 g); "Salt" section (5 % vs 12-18 % for traditional misos); story (pulp from elderflower oil combined with cooked split peas, rice koji and salt; aged three months; flavoured peasos take pulp at 5 % of total weight). **NomaProjects-peaso** — Noma Projects journal, "The Lab Dispatch: Miso" (https://nomaprojects.com/blogs/journal/the-lab-dispatch-miso; peaso 4 % salt vs 12-20 % for Japanese miso) and "What's the Difference: Miso Versus Peaso" (https://nomaprojects.com/blogs/journal/what-s-the-difference-miso-versus-peaso; 4 % salt vs typical 8 %; brighter, fruitier flavour).
- Facts copied: yellow split peas 60 %; rice koji (rice, koji culture); elderflower 5 %; salt; 5 % salt; aged three months; floral, fruity, slightly acidic, less sweet and less salty than most misos.
- Derivations: rice koji = 100 - 60 - 5 - 5 = 30 % (allowed by the label's descending order: 60 >= 30 >= 5 >= 5). Three months = 2160 h (90 days).
- One-line method: Mix cooked yellow split peas with rice koji, 5 % salt and elderflower pulp, pack and age three months.
- Notes: A commercial product's declared composition (EU QUID percentages refer to ingredients at the time of use), not a home recipe, hence the precise shares; whether the 60 % is cooked or dry pea weight is not stated (recorded as cooked, as mixed). No temperature number. The plain peaso of the journal pieces uses 4 % salt (see noma_peaso_plain).

### noma_peaso_plain — Peaso, yellow split pea miso (Noma)

- Sources: **NomaProjects-peaso** (defined above). **NP-flavor-box** — Noma Projects, "Flavor Box 1" (Taste Buds box page), nomaprojects.com. URL: https://nomaprojects.com/pages/tb26-box1. Locator: Cep Tamari and Ryeso paragraphs (rice koji first; peaso is a three-month fermentation of yellow split peas mixed with koji and salt into a thick paste; ryeso made the same way from rye bread, rice koji and salt, aged at least three months).
- Facts copied: peaso = yellow split peas + koji + salt; 4 % salt (12-20 % or "typical 8 %" for Japanese miso); lower salt lets yeasts, lactic and acetic bacteria flourish, giving a brighter, fruitier peaso that needs less ageing; three-month fermentation.
- Derivations: 4 % = 40 g/kg; three months = 2160 h.
- One-line method: Mash cooked yellow split peas with rice koji and 4 % salt, pack and age about three months.
- Notes: Draft: pea and koji shares are not stated (only the elderflower product's 60:30 is). 4 % salt is the lowest in this round's miso set; the `miso` profile's typical salt is 11 %. No temperature number.

### noma_kyoto_peaso — Kyoto peaso with kanzuri (Noma Projects)

- Sources: **NP-kyoto-peaso** — Noma Projects. "Kyoto Peaso" (product page), nomaprojects.com, published 2026-02-10. URL: https://nomaprojects.com/products/kyoto-peaso. Locator: "Ingredients and Nutrition" (yellow split peas (Denmark) 34 %, rice koji (rice, koji culture), kanzuri paste (red pepper, koji, yuzu) 22 %, salt; nutrition per 100 g: 586 kJ, fat 1 g, saturates 0 g, carbohydrate 27 g, sugars 1 g, protein 6 g, salt 5 g). Field order of the panel checked against the page's table labels. **NP-elderflower-peaso** (defined above; flavoured peasos aged three months).
- Facts copied: composition and nutrition as above; described as a Danish miso of yellow split peas accented with kanzuri.
- Derivations: salt 5 % (nutrition, total). Rice koji = 100 - 34 - 22 - 5 = 39 % if the 5 % were all added salt; because kanzuri brings some salt, added salt is somewhat below 5 % and koji somewhat above 39 % (descending label order is satisfied: koji >= 22 %).
- One-line method: Mash cooked yellow split peas with rice koji, kanzuri chile paste and salt, pack and age.
- Notes: Draft: ageing time not stated for this product, and the salt/koji split is bounded rather than exact. No temperature number.

### noma_mushroom_oat_garum — Mushroom and oat koji garum (Noma Projects)

- Sources: **NP-mushroom-garum** — Noma Projects. "Mushroom Garum" (product page), nomaprojects.com, published 2024-03-12. URL: https://nomaprojects.com/products/mushroom-garum. Locator: "Ingredients and Nutrition" (water, mushrooms 34 %, oats, rice koji, salt; nutrition per 100 g: carbohydrate 8.5 g, sugars 6.5 g, protein 4.2 g, salt 7 g) and product story (combines fermented mushrooms, rice koji and Oat Garum made from oat-milk by-products; koji instead of fish enzymes gives less salty garums). **NP-about-garums** — Noma Projects journal, "About Garums". URL: https://nomaprojects.com/blogs/journal/about-garums. Locator: process paragraph (press the raw ingredient, mix with salt and water, ferment 6 to 10 weeks depending on the ingredient, strain).
- Facts copied: as above.
- Derivations: salt 7 % (nutrition). Label order gives water >= 34 %; oats >= koji >= salt (7 %); so water + oats + koji = 59 %, water 34-45 %, oats + koji 14-25 %. Centre chosen: water 39.5 %, oats + koji 19.5 % split oats 11.1 / koji 8.4 (feasible bounds oats 7-18 %, koji 7-12.5 %). 6-10 weeks = 1008-1680 h, midpoint 1344 h.
- One-line method: Mix pressed mushrooms and oat solids with rice koji, salt and water, ferment for six to ten weeks, then strain.
- Notes: Draft: the water/oats/koji shares are inferred bounds from the declaration order, not stated values, and no temperature is given (Noma's book garums run at 60 °C; plant-protein garums are said to need less time in the heat). Salt 7 % is well below the profile's 12 %.

### wf_sweet_garbanzo_miso — Sweet chickpea (garbanzo) miso (wildfermentation.com guest post)

- Sources: **WF-garbanzo-miso** — Greenforest, Favero. "Cobbler time – Sweet Garbanzo Miso", guest post on wildfermentation.com (Sandor Katz's site), 2013-08-03. URL: https://www.wildfermentation.com/cobbler-time-sweet-garbanzo-miso/. Locator: batch list.
- Facts copied: 8 lb cooked garbanzo beans; 7 lb 6 oz rice koji; 4 % sea salt (10 oz); garbanzo miso as starter; filled two 1-gallon crocks; tasted at 2 months, "young", sweet and mild; scant, honey-sweet tamari.
- Derivations: 8 lb = 3628.8 g; 7 lb 6 oz = 3345.3 g; 10 oz = 283.5 g; total 7257.6 g: chickpeas 500.0, koji 460.9, salt 39.1 g/kg (3.91 %, matching the stated 4 %). 2 months = 1440 h (point).
- One-line method: Mash cooked chickpeas with nearly equal weight rice koji, 4 % salt and a spoon of older miso, pack into crocks and taste from two months.
- Notes: Draft: a practitioner guest post (not Katz's own text) and the duration is a tasting age. Proportions match the light-miso guideline (about 1:1 koji to base, low salt).

### wf_black_bean_miso — Black bean rice-koji miso with hijiki (wildfermentation.com guest post)

- Sources: **WF-black-bean-miso** — Greenforest, Favero. "Black bean Miso with Smoked Salt", guest post on wildfermentation.com, 2012-09-01. URL: https://www.wildfermentation.com/black-bean-miso-with-smoked-salt/. Locator: ingredient list and paragraph on timing.
- Facts copied: 5 lb rice koji (10 cups uncooked rice); 10 lb cooked black beans (5 lb dry); salt 8 % by weight plus 5 Tbsp smoked salt; hijiki 2 oz; 2 heads garlic; a handful of red pepper flakes; started May 2011; tamari harvested after 6 weeks and replenished with brine; miso harvested "last week" (post dated 2012-09-01); no mould; very wet mash.
- Derivations: koji 2268 g, beans 4536 g, hijiki 56.7 g = 6860.7 g; with salt at 8 % of the total, total = 6860.7 / 0.92 = 7457.3 g and salt 596.6 g. Per kg: beans 608.3, koji 304.1, hijiki 7.6, salt 80.0. Duration May 2011 -> late Aug 2012 ≈ 15 months: 442-470 days = 10608-11280 h, midpoint 10944 h.
- One-line method: Mix cooked black beans with half their weight in rice koji, 8 % salt, seaweed and garlic, pack and age over a year, drawing tamari along the way.
- Notes: Draft: guest post, the 8 % basis is interpreted as of the total, extra smoked salt and aromatics are unweighed. The koji:base ratio (1:2) matches the long-term guideline, though salt is lower (8 % vs 13 %). Duration exceeds the 180-day `miso` horizon.

### katz_kimchi_brine_soaked — Kimchi, brine-soaked (Katz, Wild Fermentation p.47 adaptation)

- Sources: **NNS-katz-kimchi** — Nature and Nurture Seeds. "Chinese (Napa) Cabbage" page, kimchi recipe "by our fermentation guru Sandor Katz", "adapted from *Wild Fermentation*... by Sandor Ellix Katz, pg. 47 (2003)". URL: https://natureandnurtureseeds.com/pages/chinese-napa-cabbage. Locator: kimchi ingredient list and steps 1-5. Brine conversion from **WF-sour-pickles** (1 Tbsp sea salt = 17 g). Corroborating leads (not used as data): permies.com forum summaries of the same 4 cups / 4 Tbsp brine.
- Facts copied: sea salt; 1 lb / 500 g napa or bok choi; a few red radishes (optional); 1-2 carrots (optional); 1-2 onions/leeks/scallions; 3-4 garlic cloves; 3-4 hot red chilies; 3 Tbsp grated ginger; soak cabbage, radish and carrot overnight in about 4 cups water + 4 Tbsp sea salt; make a paste of ginger, garlic, onion and chilies; drain, mix, pack, pour brine back to fill the jar; ferment 1-3 days at room temperature, then refrigerate.
- Derivations: brine = 68 g salt / (946 + 68) g = 6.7 % w/w. 1-3 days = 24-72 h, midpoint 48 h. No g/kg: only the cabbage is weighed and the share of brine returned is undefined.
- One-line method: Soak chopped cabbage, radish and carrot overnight in strong brine, drain, mix with a ginger-garlic-chili-onion paste, pack under some of the brine and ferment a few days.
- Notes: Draft: an adaptation on a seed company's page, with almost no masses; kept because it is the most specific opened statement of Katz's book kimchi. The 6.7 % soak brine is not the ferment's salt.

### katz_mexican_kimchi — Mexican-inspired kimchi with masa, pineapple and chapulines (Katz)

- Sources: **CG-katz-mexican-kimchi** — Katz, Sandor Ellix. "Kick Your Kimchi Up a Notch!" (excerpt from *Sandor Katz's Fermentation Journeys*, Chelsea Green, 2021), Chelsea Green blog. URL: https://www.chelseagreen.com/blog/mexican-inspired-kimchi/. Locator: "Mexican-Inspired Kimchi" (Timeframe, Ingredients for 2 quarts/2 liters, Process).
- Facts copied: timeframe a few days to 1 week; for 2 quarts / 2 L: 3 lb / 1.5 kg cabbage and/or radishes and/or other vegetables; 6 Tbsp salt; a few chilies; about 4 Tbsp / 70 g masa; 1 garlic head; 4 Tbsp grated ginger; 1 pineapple; 1 large or 2 small onions and/or scallions; 4 Tbsp / 20 g chapulines (optional); vegetables covered with water and salt ~24 h, drained; masa cooked with ~1 cup / 250 mL water into a paste; 1-2 tsp salt into the paste if needed; ferment no longer than about a week to keep the pineapple sweet.
- Derivations: 6 Tbsp salt ≈ 102 g at Katz's 17 g/Tbsp (soak only). A few days to 1 week read as 72-168 h, midpoint 120 h. No g/kg: most aromatics are counted, not weighed, and the soak salt is drained.
- One-line method: Brine-soak chopped vegetables a day, drain, coat with a cooked masa paste of chilies, garlic and ginger, fold in pineapple, onion and grasshoppers, pack and ferment under a week.
- Notes: Draft (indeterminate salt and masses). Interesting as a fruit-and-starch kimchi: Katz eats it while the fruit is still sweet.

### katz_milk_kefir — Milk kefir from grains (Katz)

- Sources: **EYB-katz-kefir-WF** — Eat Your Books recipe index, "Kefir", from Katz, *Wild Fermentation*, 2nd edition (Chelsea Green, 2016), page 119. URL: https://www.eatyourbooks.com/library/recipes/3399309/kefir. Locator: ingredients (milk, kefir grains), serves approx. 1 quart/litre, takes 1-3 days. **EYB-katz-kefir-AoF** — Eat Your Books recipe index, "Kefir", from Katz, *The Art of Fermentation* (2012), page 192. URL: https://www.eatyourbooks.com/library/recipes/3352748/kefir. Locator: "Ferments for 24 hours. See recipe for variations."
- Facts copied: milk; kefir grains; about 1 quart / 1 litre; 1-3 days (WF); 24 hours (AoF).
- Derivations: WF 24-72 h (midpoint 48 h) and AoF 24 h (point): median across the two = 36 h, range 24-72 h.
- One-line method: Drop kefir grains into a jar of milk, leave at room temperature about a day (up to three), then strain the grains out for the next batch.
- Notes: Draft: the index pages give no grain-to-milk ratio and no temperature; the book pages themselves were not opened. 24-72 h straddles the `kefir` profile's 48 h horizon. No Noma kefir recipe exists in the opened material.

### noma_rule_lacto_raspberries — Lacto raspberries (Noma 2% rule)

- Sources: rule and fruit from **GR-noma-highlights** and **NomaProjects-lacto** (each September Noma lacto-ferments blueberries, raspberries, mulberries, blackberries, white currants and other soft fruit; "weigh your ingredient, add 2 % salt by weight, and wait"); time and temperature template **SplendidTable-lacto-blueberries** (28 °C, 4-5 days, or a few days longer at room temperature).
- Facts copied: the fruit is named by Noma as a lacto ferment; salt 2 % of the fruit weight; soft fruits lose their shape and are often pressed for their juice (body, effervescence, saltiness, sweetness and acidity).
- Derivations: 1000 g fruit + 20 g salt = 1020 g: fruit 980.4, salt 19.6 g/kg (1.96 %). 4-5 days = 96-120 h (template).
- One-line method: Toss the fruit with 2 % of its weight in salt, seal airless and ferment warm a few days until lightly sour; press for juice.
- Notes: Draft, rule-derived: no opened page gives a raspberries-specific recipe, so time and temperature are the blueberry template's. Part of a rule family (with the other soft fruits) the curator may collapse into one row.

### noma_rule_lacto_blackberries — Lacto blackberries (Noma 2% rule)

- Sources: rule and fruit from **GR-noma-highlights** and **NomaProjects-lacto** (each September Noma lacto-ferments blueberries, raspberries, mulberries, blackberries, white currants and other soft fruit; "weigh your ingredient, add 2 % salt by weight, and wait"); time and temperature template **SplendidTable-lacto-blueberries** (28 °C, 4-5 days, or a few days longer at room temperature).
- Facts copied: the fruit is named by Noma as a lacto ferment; salt 2 % of the fruit weight; soft fruits lose their shape and are often pressed for their juice (body, effervescence, saltiness, sweetness and acidity).
- Derivations: 1000 g fruit + 20 g salt = 1020 g: fruit 980.4, salt 19.6 g/kg (1.96 %). 4-5 days = 96-120 h (template).
- One-line method: Toss the fruit with 2 % of its weight in salt, seal airless and ferment warm a few days until lightly sour; press for juice.
- Notes: Draft, rule-derived: no opened page gives a blackberries-specific recipe, so time and temperature are the blueberry template's. Part of a rule family (with the other soft fruits) the curator may collapse into one row.

### noma_rule_lacto_mulberries — Lacto mulberries (Noma 2% rule)

- Sources: rule and fruit from **GR-noma-highlights** and **NomaProjects-lacto** (each September Noma lacto-ferments blueberries, raspberries, mulberries, blackberries, white currants and other soft fruit; "weigh your ingredient, add 2 % salt by weight, and wait"); time and temperature template **SplendidTable-lacto-blueberries** (28 °C, 4-5 days, or a few days longer at room temperature).
- Facts copied: the fruit is named by Noma as a lacto ferment; salt 2 % of the fruit weight; soft fruits lose their shape and are often pressed for their juice (body, effervescence, saltiness, sweetness and acidity).
- Derivations: 1000 g fruit + 20 g salt = 1020 g: fruit 980.4, salt 19.6 g/kg (1.96 %). 4-5 days = 96-120 h (template).
- One-line method: Toss the fruit with 2 % of its weight in salt, seal airless and ferment warm a few days until lightly sour; press for juice.
- Notes: Draft, rule-derived: no opened page gives a mulberries-specific recipe, so time and temperature are the blueberry template's. Part of a rule family (with the other soft fruits) the curator may collapse into one row.

### noma_rule_lacto_white_currants — Lacto white currants (Noma 2% rule)

- Sources: rule and fruit from **GR-noma-highlights** and **NomaProjects-lacto** (each September Noma lacto-ferments blueberries, raspberries, mulberries, blackberries, white currants and other soft fruit; "weigh your ingredient, add 2 % salt by weight, and wait"); time and temperature template **SplendidTable-lacto-blueberries** (28 °C, 4-5 days, or a few days longer at room temperature).
- Facts copied: the fruit is named by Noma as a lacto ferment; salt 2 % of the fruit weight; soft fruits lose their shape and are often pressed for their juice (body, effervescence, saltiness, sweetness and acidity).
- Derivations: 1000 g fruit + 20 g salt = 1020 g: fruit 980.4, salt 19.6 g/kg (1.96 %). 4-5 days = 96-120 h (template).
- One-line method: Toss the fruit with 2 % of its weight in salt, seal airless and ferment warm a few days until lightly sour; press for juice.
- Notes: Draft, rule-derived: no opened page gives a white currants-specific recipe, so time and temperature are the blueberry template's. Part of a rule family (with the other soft fruits) the curator may collapse into one row.

### noma_rule_lacto_gooseberries — Lacto gooseberries (Noma 2% rule)

- Sources: rule and fruit from **GR-noma-highlights** and **NomaProjects-lacto** (each September Noma lacto-ferments blueberries, raspberries, mulberries, blackberries, white currants and other soft fruit; "weigh your ingredient, add 2 % salt by weight, and wait"); gooseberries named in **MrPorter-lacto-ceps** ("plums, gooseberries or white asparagus"); time and temperature template **SplendidTable-lacto-blueberries** (28 °C, 4-5 days, or a few days longer at room temperature).
- Facts copied: the fruit is named by Noma as a lacto ferment; salt 2 % of the fruit weight; soft fruits lose their shape and are often pressed for their juice (body, effervescence, saltiness, sweetness and acidity).
- Derivations: 1000 g fruit + 20 g salt = 1020 g: fruit 980.4, salt 19.6 g/kg (1.96 %). 4-5 days = 96-120 h (template).
- One-line method: Toss the fruit with 2 % of its weight in salt, seal airless and ferment warm a few days until lightly sour; press for juice.
- Notes: Draft, rule-derived: no opened page gives a gooseberries-specific recipe, so time and temperature are the blueberry template's. Part of a rule family (with the other soft fruits) the curator may collapse into one row.

### noma_rule_brined_beets — Brined beets (Noma 2% brine rule)

- Sources: **GR-noma-highlights** (lacto chapter: brine method — tare the vessel, add vegetables, cover with water, take 2 % of the total weight as salt, dissolve and return; "crunchier vegetables of manageable size (beets, radishes, or young carrots) do extremely well submerged in salted water"; onions and turnips with a fistful of lemon thyme or orange blossom; replace 5-10 % of brine water with fruit juice; tannic grape or horseradish leaves or unrefined salt for crunch; horseradish or a halved chile for spice; pH < 5 within two days and < 4.6 at completion is generally safe). **NomaProjects-lacto** (white asparagus, small pumpkins, beets and cabbage stems made successful pickles).
- Facts copied: as above; beets named by GR-noma-highlights (brine) and NomaProjects-lacto (successful pickles).
- Derivations: salt = 2 % of (vegetables + water), i.e. 20 / 1020 = 1.96 % of the final batch (19.6 g/kg). Vegetable and water shares, time and temperature are not stated, so those fields are empty.
- One-line method: Pack the vegetables snugly, cover with water, weigh, dissolve 2 % of that weight in salt into the water, return the brine and ferment weighted until sour.
- Notes: Draft, rule-derived (no vegetable-specific recipe opened). Part of the Noma brine rule family. 1.96 % trips SALT-001 by rounding only.

### noma_rule_brined_radishes — Brined radishes (Noma 2% brine rule)

- Sources: **GR-noma-highlights** (lacto chapter: brine method — tare the vessel, add vegetables, cover with water, take 2 % of the total weight as salt, dissolve and return; "crunchier vegetables of manageable size (beets, radishes, or young carrots) do extremely well submerged in salted water"; onions and turnips with a fistful of lemon thyme or orange blossom; replace 5-10 % of brine water with fruit juice; tannic grape or horseradish leaves or unrefined salt for crunch; horseradish or a halved chile for spice; pH < 5 within two days and < 4.6 at completion is generally safe). **NomaProjects-lacto** (white asparagus, small pumpkins, beets and cabbage stems made successful pickles).
- Facts copied: as above; radishes named by GR-noma-highlights (brine).
- Derivations: salt = 2 % of (vegetables + water), i.e. 20 / 1020 = 1.96 % of the final batch (19.6 g/kg). Vegetable and water shares, time and temperature are not stated, so those fields are empty.
- One-line method: Pack the vegetables snugly, cover with water, weigh, dissolve 2 % of that weight in salt into the water, return the brine and ferment weighted until sour.
- Notes: Draft, rule-derived (no vegetable-specific recipe opened). Part of the Noma brine rule family. 1.96 % trips SALT-001 by rounding only.

### noma_rule_brined_young_carrots — Brined young carrots (Noma 2% brine rule)

- Sources: **GR-noma-highlights** (lacto chapter: brine method — tare the vessel, add vegetables, cover with water, take 2 % of the total weight as salt, dissolve and return; "crunchier vegetables of manageable size (beets, radishes, or young carrots) do extremely well submerged in salted water"; onions and turnips with a fistful of lemon thyme or orange blossom; replace 5-10 % of brine water with fruit juice; tannic grape or horseradish leaves or unrefined salt for crunch; horseradish or a halved chile for spice; pH < 5 within two days and < 4.6 at completion is generally safe). **NomaProjects-lacto** (white asparagus, small pumpkins, beets and cabbage stems made successful pickles).
- Facts copied: as above; young carrots named by GR-noma-highlights (brine).
- Derivations: salt = 2 % of (vegetables + water), i.e. 20 / 1020 = 1.96 % of the final batch (19.6 g/kg). Vegetable and water shares, time and temperature are not stated, so those fields are empty.
- One-line method: Pack the vegetables snugly, cover with water, weigh, dissolve 2 % of that weight in salt into the water, return the brine and ferment weighted until sour.
- Notes: Draft, rule-derived (no vegetable-specific recipe opened). Part of the Noma brine rule family. 1.96 % trips SALT-001 by rounding only.

### noma_rule_brined_onions_turnips_herbs — Lacto onions and turnips with aromatic herbs (Noma 2% rule)

- Sources: **GR-noma-highlights** (lacto chapter: brine method — tare the vessel, add vegetables, cover with water, take 2 % of the total weight as salt, dissolve and return; "crunchier vegetables of manageable size (beets, radishes, or young carrots) do extremely well submerged in salted water"; onions and turnips with a fistful of lemon thyme or orange blossom; replace 5-10 % of brine water with fruit juice; tannic grape or horseradish leaves or unrefined salt for crunch; horseradish or a halved chile for spice; pH < 5 within two days and < 4.6 at completion is generally safe). **NomaProjects-lacto** (white asparagus, small pumpkins, beets and cabbage stems made successful pickles).
- Facts copied: as above; onions and turnips with a fistful of lemon thyme or orange blossom named by GR-noma-highlights.
- Derivations: salt = 2 % of (vegetables + water), i.e. 20 / 1020 = 1.96 % of the final batch (19.6 g/kg). Vegetable and water shares, time and temperature are not stated, so those fields are empty.
- One-line method: Pack the vegetables snugly, cover with water, weigh, dissolve 2 % of that weight in salt into the water, return the brine and ferment weighted until sour.
- Notes: Draft, rule-derived (no vegetable-specific recipe opened). Part of the Noma brine rule family. 1.96 % trips SALT-001 by rounding only.

### noma_rule_lacto_white_asparagus — Lacto white asparagus (Noma 2% rule)

- Sources: **NomaProjects-lacto** (white asparagus, small pumpkins, beets and cabbage stems made successful pickles; watercress and ramsons less so). **MrPorter-lacto-ceps** ("the longer you leave the fruit or vegetable – be it plums, gooseberries or white asparagus – the sourer"). **GR-noma-highlights** (2 % rule).
- Facts copied: white asparagus is a Noma lacto pickle; 2 % salt by weight; sourness grows with time.
- Derivations: 1000 g asparagus + 20 g salt: asparagus 980.4, salt 19.6 g/kg (1.96 %).
- One-line method: Salt white asparagus at 2 % of its weight, seal airless (or brine it at 2 % of the total) and ferment until pleasantly sour.
- Notes: Draft, rule-derived; no time, temperature or salting style is stated for asparagus.

### bergo_meat_garum_noma_style — Meat (lamb) koji garum after Noma (Forager Chef)

- Sources: **FC-meat-garum** — Bergo, Alan. "Meat Garum", Forager Chef (foragerchef.com), published 2019-02-09, modified 2023-08-05. URL: https://foragerchef.com/meat-garum/. Locator: introduction (planned after reading the Noma Guide; book uses beef, barley koji, a 140 °F hold for 70 days per the author) and recipe card ("adapted from the Noma Guide to Fermentation": ingredients, dehydrator at 140 °F, remove after 30 days).
- Facts copied: 1000 g lean meat (lamb tongue); 240 g kosher salt; 800 g water; 200 g koji rice; sealed with plastic pressed to the surface, dehydrator at 140 °F; skim fat often in week 1 then weekly; raft and gentle bubbles after a couple of days; remove after 30 days, strain, chill and de-fat, strain again, top the liquid back to 800 g with water. Text: the book's slurry is held at 140 °F for 70 days; toasty, nutty, dark, rich and aggressively salty.
- Derivations: 1000 + 240 + 800 + 200 = 2240 g: meat 446.4, water 357.1, koji 89.3, salt 107.1 g/kg (10.71 %). 140 °F = 60 °C. 30-70 days = 720-1680 h, midpoint 1200 h.
- One-line method: Mix ground lean meat with crumbled koji rice, salt and water, press plastic onto the surface and hold at 60 °C for one to two months, skimming fat, then strain clear.
- Notes: A chef's explicit adaptation of Noma's beef garum; numbers agree with Noma's own excerpt (about 12 % salt, 60 °C). 60 °C is the top of the `garum` profile range. Lamb is a new ingredient.

### bergo_ramp_leaf_koji_garum — Ramp leaf koji garum, vegan fish sauce (Forager Chef)

- Sources: **FC-ramp-garum** — Bergo, Alan. "Ramp Leaf Garum (Vegan Fish Sauce)", Forager Chef, published 2022-05-21. URL: https://foragerchef.com/ramp-leaf-garum-vegan-fish-sauce/. Locator: intro ("my meat garum recipe I modified from the Noma Guide to Fermentation"), "Koji: The Secret" (soy sauce and garum ~18 % salt; koji lets salty liquids ferment; 145-150 °F for thirty days; 3 % salt first if no koji), recipe card.
- Facts copied: makes about 6 cups; 400 g fresh ramp leaves; 240 g salt; 1300 g strained ramp juice (from about 2000 g leaves); 120 g koji rice; ferment 5 days at room temperature, then 145 °F (dehydrator high) for 30 days until dark and syrupy, cling film on the surface (replace evaporated water by weight); strain and refrigerate. Text: browning gives a caramel colour, toasted notes; ramp leaves have an "almost fishy" flavour when fermented.
- Derivations: 400 + 240 + 1300 + 120 = 2060 g: juice 631.1, leaves 194.2, koji 58.3, salt 116.5 g/kg (11.65 %). 145 °F = 62.8 °C. 5 + 30 days = 840 h.
- One-line method: Crush chopped ramp leaves with salt and koji rice, cover with ramp juice, ferment five days at room temperature, then hold at about 63 °C for a month and strain.
- Notes: 62.8 °C is just above the `garum` profile's 60 °C upper limit (the text's 145-150 °F = 62.8-65.6 °C). The substrate is a low-protein leaf juice rather than fish or meat, so the profile's protein-driven model fits loosely. Ramp leaves and juice are new ingredients.

### bergo_fruit_scrap_vinegar_classic — Classic fruit-scrap vinegar, Katz style (Forager Chef)

- Sources: **FC-scrap-vinegar** — Bergo, Alan. "Fruit Scrap Vinegar", Forager Chef, published 2020-04-11, modified 2025-12-09. URL: https://foragerchef.com/fruit-scrap-vinegar/. Locator: intro ("a hybrid of two of my favorites: one from the Art of Fermentation by Sandor Katz, and the other by Rene Redzepi in the Noma Guide... The Sandor Katz recipe is the most basic... fruit and sugar water"), "Classic Fruit Scrap Vinegar" card, and the accelerated card (for the 1/4 cup = 50 g sugar conversion).
- Facts copied: 1 cup granulated sugar; 2 lb fruit scraps (skins, seeds); 2 Tbsp living vinegar; 2 qt water; cloth cover, room temperature, stir often; strain after 2 weeks, continue another month or so until strong; fermentation time 60 days (card); optional sweetening 1/2 cup per quart afterwards.
- Derivations: sugar 200 g (author's own 50 g per 1/4 cup), scraps 907.2 g, vinegar 2 Tbsp ≈ 30 g, water 2 qt = 1892.7 g; total 3029.9 g: water 624.7, scraps 299.4, sugar 66.0, live vinegar 9.9 g/kg. Time 6 weeks (text: 2 weeks + about a month) to 60 days (card) = 1008-1440 h, midpoint 1224 h.
- One-line method: Cover fruit scraps with sugared water and a splash of live vinegar under cloth, stir for two weeks, strain and let it sour about another month.
- Notes: The `vinegar` profile assumes an alcoholic start; this is a sugar-water scrap vinegar (yeast and acetic stages together, 6.6 % added sugar plus fruit sugar). Starter share ~1 % is far below the profile's 15 %. No temperature number.

### bergo_fruit_scrap_vinegar_vodka — Accelerated fruit-scrap vinegar with added alcohol, Noma style (Forager Chef)

- Sources: **FC-scrap-vinegar** (defined above; "Accelerated Fruit Scrap Vinegar with Alcohol" card; intro naming the Noma Guide as the second parent recipe). Context: **NomaProjects-vinegar** (Noma feeds acetic bacteria with distilled ethanol when fruit is under 14 °Bx; 100 g of 96 % ethanol ≈ 130 g of 75 % vodka; AAB need 6-8 % ABV for ~5 % acidity).
- Facts copied: makes about 4 cups; 750 g water; 172 g previous fruit vinegar or live cider vinegar; 184 g 80-proof vodka; 1 lb fruit scrap; 50 g sugar; 2-quart container, cheesecloth, room temperature, stir; strain after 2 weeks; continue a month or two until no sweetness is left; fermenting time 45 days (card).
- Derivations: total 750 + 172 + 184 + 453.6 + 50 = 1609.6 g: water 466.0, scraps 281.8, vodka 114.3, live vinegar 106.9, sugar 31.1 g/kg. Ethanol: 184 g x 0.40 v/v x 0.789 / 0.951 (vodka density) ≈ 61 g, ≈ 38 g/kg (profile typical 55 g/kg). Time 2 weeks + 1-2 months = 44-74 days = 1056-1776 h, midpoint 1416 h (card: 45 days).
- One-line method: Combine fruit scraps, water, a little sugar, vodka and live vinegar under cloth, stir for two weeks, strain and let it sour one to two months.
- Notes: Closest of this round's vinegars to the `vinegar` profile (ethanol start, ~11 % live-vinegar starter vs the profile's 15 %). No temperature number. Vodka is a new ingredient (the catalogue has wines and cider).

### bergo_lacto_mushrooms_3pct — Lacto-fermented wild mushrooms, 3% (Forager Chef after Noma and Katz)

- Sources: **FC-wild-mushroom-fermentation** — Bergo, Alan. "Wild Mushroom Fermentation", Forager Chef, published 2020-02-08, modified 2023-08-05. URL: https://foragerchef.com/wild-mushroom-fermentation/. Locator: text (Noma Guide's lacto-fermented porcini and dryad-saddle condiments; Katz's *Wild Fermentation* in the book list; brine at 2-5 %, faster at 2 % and slower at 5 %; kimchee-style ~7 %; mushroom ferments end around pH 3-3.5 after 2-4 weeks; FDA 4.6 line), "Brine Fermented Mushrooms" card and notes (3 % of total; 5-10 days, refrigerate after about 5; 7-14 days for decent flavour; vacuum version 3 % of mushroom weight).
- Facts copied: as above.
- Derivations: vacuum version: 1000 g mushrooms + 30 g salt = 1030 g: mushrooms 970.9, salt 29.1 g/kg (2.91 %). Time 5-14 days = 120-336 h, midpoint 228 h. The brine version has the same salt fraction of the total (3 % of mushrooms + water, i.e. 2.91 % of the final batch) but an unstated mushroom:water ratio.
- One-line method: Weigh mushrooms (and water if brining), add 3 % salt, vacuum-seal or weight under brine, and ferment at room temperature one to two weeks, burping as needed.
- Notes: Salt 2.9 % is above Noma's 2 % (the author's 2-5 % band); inside the 2-10 % safety band. No temperature number. Pairs with noma_lacto_ceps.

### koji_alchemy_long_grain_rice_koji — Long-grain rice koji, oven-cooked rice (Koji Alchemy, foreword by Katz)

- Sources: **CG-koji-alchemy-growing** — Umansky, Jeremy; Shih, Rich. "Growing Koji in Your Own Kitchen" (excerpt from *Koji Alchemy*, Chelsea Green, 2020), Chelsea Green blog. URL: https://www.chelseagreen.com/blog/growing-koji-in-your-own-kitchen/. Locator: requirements paragraph and steps 1-5. Context: **CG-koji-alchemy-book** — Chelsea Green product page for *Koji Alchemy* (https://www.chelseagreen.com/product/koji-alchemy/): "Foreword by Sandor Ellix Katz"; praised by David Zilber.
- Facts copied: koji needs a mild heat source for two days, airflow, and humidity that does not bead on the grain; optimal 30 °C for protease and 35 °C for amylase (general paragraph); method: long-grain rice, water to cover the knuckles, covered, 176 °C (350 °F) oven for 90 min, rest at least 1 h; break up clumps; inoculate below 37 °C (100 °F); tray no deeper than 5 cm; plastic wrap with finger holes; incubate 26 °C (80 °F) for more protease or 32 °C (90 °F) for more amylase; fully grown about 36 h; fresh koji keeps ~2 weeks refrigerated (6 weeks vacuum-packed).
- Derivations: temp 26-32 °C, midpoint 29 °C; 36 h (point). Substrate normalised to 1000 g/kg rice.
- One-line method: Bake unwashed long-grain rice under foil, rest and break it apart, dust with spores below 37 °C, spread thin under perforated film and incubate about 36 h.
- Notes: Draft (no masses for water or spores). Outside the brief's strict Noma/Katz authorship: kept because koji coverage is thin and the book carries Katz's foreword; the curator may drop it. 26 °C sits just below the `koji` profile's 28-35 °C range.

### katz_mixed_kraut_tastingtable — Mixed napa and purple cabbage kraut with coriander (Katz, via Tasting Table)

- Sources: **TT-katz-sauerkraut** — "Sandor Katz's Sauerkraut" ("Recipe adapted from Sandor Katz"), Tasting Table, 2015-04-21. URL: https://www.tastingtable.com/cook/recipes/how-to-make-sauerkraut-sandor-katz-recipe. Locator: ingredient list and steps. **Morton-kosher** — Morton Salt, "Morton Coarse Kosher Salt" product page, nutrition facts "Serving Size 1/4 tsp (1.2g)". URL: https://www.mortonsalt.com/shop/kosher-salt/morton-coarse-kosher-salt/.
- Facts copied: 1/2 lb shredded napa cabbage; 1/2 lb shredded purple cabbage; 1/4 lb grated carrots; 1/4 lb spring onions; 3 tsp kosher salt; 1 tsp toasted crushed coriander; 1/4 tsp red pepper flakes; toss and squeeze, rest 10-15 min to release juice, pack, cover with a towel or cheesecloth at room temperature, skim every day or so; taste after 4 days, when it should be ready; refrigerate up to 6 months. Presented as a guideline (kale for napa, fennel seed for coriander, etc.).
- Derivations: vegetables 226.8 + 226.8 + 113.4 + 113.4 = 680.4 g; salt 3 x 4.8 = 14.4 g; total 694.8 g: napa 326.4, purple cabbage 326.4, carrot 163.2, spring onion 163.2, salt 20.7 g/kg (2.07 %). 4 days = 96 h (point).
- One-line method: Squeeze shredded napa and red cabbage, carrot and spring onion with salt and spices until juicy, pack, cover with cloth and taste from four days.
- Notes: Draft: the kosher-salt brand (and so the salt mass) is not stated; at the Morton conversion salt sits right at the 2 % line, a lighter flake salt would put it below. No temperature number. Purple cabbage recorded as Cabbage; spring onions as Onion.

### noma_rule_lacto_small_pumpkins — Lacto small pumpkins (Noma 2% rule)

- Sources: **NomaProjects-lacto** (white asparagus, small pumpkins, beets and cabbage stems made successful pickles). **GR-noma-highlights** (2 % rule; brine alternative at 2 % of vegetables + water; safety rule).
- Facts copied: small pumpkins are a successful Noma lacto pickle; 2 % salt by weight.
- Derivations: 1000 g pumpkin + 20 g salt: pumpkin 980.4, salt 19.6 g/kg (1.96 %).
- One-line method: Salt small pumpkins (cut to fit) at 2 % of their weight, or brine them at 2 % of the total, and ferment airless until sour.
- Notes: Draft, rule-derived; no time or temperature stated. Part of the Noma rule family.

## C. Envelope check (against `profiles.py`)

Profile ranges read from `src/fermenttrack/prediction/profiles.py`: lacto_ferment 16-24 °C, horizon 672 h, typical salt 20 g/kg; kombucha 20-28 °C, 504 h, sucrose 70 g/kg, starter 10 %; vinegar 24-30 °C, 1440 h, starter 15 %; koji 28-35 °C, 72 h; miso 15-30 °C, 4320 h, salt 110 g/kg; garum 20-60 °C, 4320 h, salt 120 g/kg; kefir 18-25 °C, 48 h. Safety rules (`risk_rules.yaml`): SALT-001 warns below 2 % salt for vegetables, SALT-002 above 10 %, BOT-002 needs pH <= 4.6 within 48 h above 10 °C.

| key | type | temp °C | duration h | salt % | flags |
|---|---|---|---|---|---|
| noma_lacto_blueberries | lacto_ferment | 28 | 96-120 | 1.96 | temp above 24 °C; salt < 2 % (SALT-001) |
| noma_lemon_verbena_kombucha | kombucha | 28 | 168-216 |  | inside |
| katz_sauerkraut_basic | lacto_ferment |  | 72-2160 | 1.67 | no temperature stated; runs past the 672 h horizon; salt < 2 % (SALT-001) |
| katz_sour_pickles | lacto_ferment |  | 168-672 | 2.49-2.83 | no temperature stated |
| noma_chicken_wing_garum | garum | 60 | 672 | 10.6 | inside |
| noma_perry_vinegar | vinegar |  | 240-336 |  | no temperature stated |
| katz_kombucha_basic | kombucha | 24-30 | 168-336 |  | temp above 28 °C |
| noma_lacto_ceps | lacto_ferment | 28 | 120-168 | 1.96 | temp above 24 °C; salt < 2 % (SALT-001) |
| noma_apple_kombucha | kombucha | 28 | 168-240 |  | inside |
| noma_coffee_kombucha | kombucha | 28 | 168-240 |  | inside |
| noma_lacto_plums | lacto_ferment | 21-28 | 120-168 | 1.96 | temp above 24 °C; salt < 2 % (SALT-001) |
| zilber_caviar_koji_garum | garum |  | 8760 | 7.41 | no temperature stated; runs past the 4320 h horizon |
| zilber_rice_koji | koji | 28-30 | 48 |  | inside |
| katz_persimmon_vinegar | vinegar |  | 1440-2160 |  | no temperature stated; runs past the 1440 h horizon |
| katz_miso_short_light | miso |  | 336-2160 | 4.76-6 | no temperature stated |
| katz_miso_long_dark | miso |  | 4320-8760 | 11.6-13 | no temperature stated; runs past the 4320 h horizon |
| noma_elderflower_peaso | miso |  | 2160 | 5 | no temperature stated |
| noma_peaso_plain | miso |  | 2160 | 4 | no temperature stated |
| noma_kyoto_peaso | miso |  |  | 5 | no temperature stated; no duration stated |
| noma_mushroom_oat_garum | garum |  | 1008-1680 | 7 | no temperature stated |
| wf_sweet_garbanzo_miso | miso |  | 1440 | 3.91 | no temperature stated |
| wf_black_bean_miso | miso |  | 10608-11280 | 8 | no temperature stated; runs past the 4320 h horizon |
| katz_kimchi_brine_soaked | lacto_ferment |  | 24-72 |  | no temperature stated; salt not determinable |
| katz_mexican_kimchi | lacto_ferment |  | 72-168 |  | no temperature stated; salt not determinable |
| katz_milk_kefir | kefir |  | 24-72 |  | no temperature stated; runs past the 48 h horizon |
| noma_rule_lacto_raspberries | lacto_ferment | 28 | 96-120 | 1.96 | temp above 24 °C; salt < 2 % (SALT-001) |
| noma_rule_lacto_blackberries | lacto_ferment | 28 | 96-120 | 1.96 | temp above 24 °C; salt < 2 % (SALT-001) |
| noma_rule_lacto_mulberries | lacto_ferment | 28 | 96-120 | 1.96 | temp above 24 °C; salt < 2 % (SALT-001) |
| noma_rule_lacto_white_currants | lacto_ferment | 28 | 96-120 | 1.96 | temp above 24 °C; salt < 2 % (SALT-001) |
| noma_rule_lacto_gooseberries | lacto_ferment | 28 | 96-120 | 1.96 | temp above 24 °C; salt < 2 % (SALT-001) |
| noma_rule_brined_beets | lacto_ferment |  |  | 1.96 | no temperature stated; no duration stated; salt < 2 % (SALT-001) |
| noma_rule_brined_radishes | lacto_ferment |  |  | 1.96 | no temperature stated; no duration stated; salt < 2 % (SALT-001) |
| noma_rule_brined_young_carrots | lacto_ferment |  |  | 1.96 | no temperature stated; no duration stated; salt < 2 % (SALT-001) |
| noma_rule_brined_onions_turnips_herbs | lacto_ferment |  |  | 1.96 | no temperature stated; no duration stated; salt < 2 % (SALT-001) |
| noma_rule_lacto_white_asparagus | lacto_ferment |  |  | 1.96 | no temperature stated; no duration stated; salt < 2 % (SALT-001) |
| bergo_meat_garum_noma_style | garum | 60 | 720-1680 | 10.7 | inside |
| bergo_ramp_leaf_koji_garum | garum | 62.8 | 840 | 11.7 | temp above 60 °C |
| bergo_fruit_scrap_vinegar_classic | vinegar |  | 1008-1440 |  | no temperature stated |
| bergo_fruit_scrap_vinegar_vodka | vinegar |  | 1056-1776 |  | no temperature stated; runs past the 1440 h horizon |
| bergo_lacto_mushrooms_3pct | lacto_ferment |  | 120-336 | 2.91 | no temperature stated |
| koji_alchemy_long_grain_rice_koji | koji | 26-32 | 36 |  | temp below 28 °C |
| katz_mixed_kraut_tastingtable | lacto_ferment |  | 96 | 2.07 | no temperature stated |
| noma_rule_lacto_small_pumpkins | lacto_ferment |  |  | 1.96 | no temperature stated; no duration stated; salt < 2 % (SALT-001) |

## D. Catalogue proposals

42 new ingredient names. FDC matches were found offline in `src/fermenttrack/fdc_catalog_v1.csv.gz` (no USDA site fetched); "proxy" marks a near match, empty fdc_id means no usable row.

| ingredient (new) | recipes | fdc_id | FDC description | data type | used by |
|---|---:|---|---|---|---|
| Yellow split peas (cooked) | 3 | 172429 | Peas, split, mature seeds, cooked, boiled, without salt | SR Legacy | noma_elderflower_peaso; noma_kyoto_peaso; noma_peaso_plain |
| Fruit scraps | 2 | 171688 | Apples, raw, with skin (proxy: scraps are mixed fruit; apple as default) | SR Legacy | bergo_fruit_scrap_vinegar_classic; bergo_fruit_scrap_vinegar_vodka |
| Mushrooms | 2 | 169251 | Mushrooms, white, raw | SR Legacy | bergo_lacto_mushrooms_3pct; noma_mushroom_oat_garum |
| Apple juice (unfiltered) | 1 | 173933 | Apple juice, canned or bottled, unsweetened, without added ascorbic acid | SR Legacy | noma_apple_kombucha |
| Beets | 1 | 169145 | Beets, raw | SR Legacy | noma_rule_brined_beets |
| Black beans (cooked) | 1 | 173735 | Beans, black, mature seeds, cooked, boiled, without salt | SR Legacy | wf_black_bean_miso |
| Black peppercorns | 1 | 170931 | Spices, pepper, black | SR Legacy | katz_sour_pickles |
| Blackberries | 1 | 173946 | Blackberries, raw | SR Legacy | noma_rule_lacto_blackberries |
| Blueberries | 1 | 171711 | Blueberries, raw | SR Legacy | noma_lacto_blueberries |
| Caviar (fish roe) | 1 | 174188 | Fish, caviar, black and red, granular | SR Legacy | zilber_caviar_koji_garum |
| Chapulines (grasshoppers) | 1 |  | no match in the snapshot (no insects) |  | katz_mexican_kimchi |
| Chicken stock | 1 | 172884 | Soup, stock, chicken, home-prepared | SR Legacy | noma_chicken_wing_garum |
| Chicken wings (roasted) | 1 | 173630 | Chicken, broilers or fryers, wing, meat and skin, cooked, roasted | SR Legacy | noma_chicken_wing_garum |
| Chickpeas (cooked) | 1 | 173757 | Chickpeas (garbanzo beans, bengal gram), mature seeds, cooked, boiled, without salt | SR Legacy | wf_sweet_garbanzo_miso |
| Coffee (ground) | 1 |  | no ground-coffee row (only brewed 171890 / instant 171893) |  | noma_coffee_kombucha |
| Coriander seeds | 1 | 170922 | Spices, coriander seed | SR Legacy | katz_mixed_kraut_tastingtable |
| Elderflower | 1 |  | no match (171727 Elderberries, raw is the fruit) |  | noma_elderflower_peaso |
| Gooseberries | 1 | 173030 | Gooseberries, raw | SR Legacy | noma_rule_lacto_gooseberries |
| Grape leaves | 1 | 168575 | Grape leaves, raw | SR Legacy | katz_sour_pickles |
| Hijiki seaweed | 1 | 168457 | Seaweed, kelp, raw (proxy; no hijiki row) | SR Legacy | wf_black_bean_miso |
| Kanzuri (fermented chile paste) | 1 | 170106 | Peppers, hot chili, red, raw (proxy for the chile part only) | SR Legacy | noma_kyoto_peaso |
| Lamb (lean meat) | 1 | 174366 | Lamb, variety meats and by-products, tongue, raw (the cut used) | SR Legacy | bergo_meat_garum_noma_style |
| Lemon thyme | 1 | 173470 | Thyme, fresh | SR Legacy | noma_rule_brined_onions_turnips_herbs |
| Lemon verbena (dried) | 1 |  | no match |  | noma_lemon_verbena_kombucha |
| Masa (nixtamalized corn dough) | 1 | 169696 | Corn flour, masa, unenriched, white (dry flour; the recipe uses fresh dough) | SR Legacy | katz_mexican_kimchi |
| Miso (starter) | 1 | 172442 | Miso | SR Legacy | wf_sweet_garbanzo_miso |
| Mulberries | 1 | 169913 | Mulberries, raw | SR Legacy | noma_rule_lacto_mulberries |
| Oats | 1 | 169705 | Oats | SR Legacy | noma_mushroom_oat_garum |
| Pears | 1 | 169118 | Pears, raw | SR Legacy | noma_perry_vinegar |
| Perry (pear wine) | 1 | 174146 | Beverages, AMBER, hard cider (proxy; or map to catalogue Hard cider) | SR Legacy | noma_perry_vinegar |
| Persimmons | 1 | 169941 | Persimmons, japanese, raw (169943 native, raw also present) | SR Legacy | katz_persimmon_vinegar |
| Pineapple | 1 | 169124 | Pineapple, raw, all varieties | SR Legacy | katz_mexican_kimchi |
| Plums | 1 | 169949 | Plums, raw | SR Legacy | noma_lacto_plums |
| Porcini mushrooms | 1 |  | no porcini row (nearest 168422 Mushrooms, Chanterelle, raw) |  | noma_lacto_ceps |
| Pumpkin (small squash) | 1 | 168448 | Pumpkin, raw | SR Legacy | noma_rule_lacto_small_pumpkins |
| Ramp juice | 1 | 2727584 | Leeks, bulb and greens, root removed, raw (proxy; no ramps) | Foundation | bergo_ramp_leaf_koji_garum |
| Ramp leaves | 1 | 2727584 | Leeks, bulb and greens, root removed, raw (proxy; no ramps) | Foundation | bergo_ramp_leaf_koji_garum |
| Saison yeast | 1 | 175043 | Leavening agents, yeast, baker's, active dry (proxy; different strain) | SR Legacy | noma_perry_vinegar |
| Turnips | 1 | 170465 | Turnips, raw | SR Legacy | noma_rule_brined_onions_turnips_herbs |
| Vodka (40% ABV) | 1 | 174818 | Alcoholic beverage, distilled, vodka, 80 proof | SR Legacy | bergo_fruit_scrap_vinegar_vodka |
| White asparagus | 1 | 168389 | Asparagus, raw (green; proxy) | SR Legacy | noma_rule_lacto_white_asparagus |
| White currants | 1 | 173964 | Currants, red and white, raw | SR Legacy | noma_rule_lacto_white_currants |

Existing names that need a new type tag (from the `notes` of the ingredient rows):

- Raspberries (tagged kombucha, kefir): lacto_ferment (noma_rule_lacto_raspberries).
- Fresh ginger (tagged kombucha, kefir): lacto_ferment (the Katz kimchis).
- Cane sugar (tagged kombucha, kefir): vinegar (both fruit-scrap vinegars).
- White rice and Pearl barley as koji (tagged koji, miso): garum (all koji garums record the koji grain in the starter role, round-1 convention).
- Garlic, Chilies (tagged lacto_ferment): miso (wf_black_bean_miso).
- Onion (flavoring, lacto_ferment): used as a base vegetable in noma_rule_brined_onions_turnips_herbs.

Existing catalogue names used here that are absent from `AROMA_INGREDIENTS` (`existing_no_aroma`), by recipe count:

Salt (32), Water (15), Cane sugar (5), Chilies (4), Garlic (4), Onion (4), SCOBY / starter liquid (4), Carrot (3), Mother of vinegar (Acetobacter) (3), Koji spores (A. oryzae) (2), Radish (2), Kefir grains (1), Raspberries (1)

## E. Out of model

- **Noma shoyus** (e.g. the book's dryad-saddle mushroom shoyu; Forager Chef's pheasant-back adaptation, https://foragerchef.com/pheasant-back-fermented-soy-sauce/, 200 g koji rice, 1000 g water, 250 g salt): soy-sauce style, no profile.
- **Noma black fruits and vegetables** (black garlic, black apples; book chapter named in the publisher description): Maillard ageing, not a fermentation profile.
- **Peaso tamari** (Noma: 1 part peaso to 2 parts water, ice-clarified and reduced to ~65 °Bx; NomaProjects tamari dispatch): a reduction of a finished miso.
- **Noma Whisky Vinegar and Wild Rose Vinegar** (Noma Projects products): blends of finished vinegars with whisky or rose infusion (Wild Rose: apple cider vinegar, apple juice, 20 % rose petals, 5 % acidity), not fermentations.
- **Katz's favourite homemade cheese** (Fermentation Journeys excerpt, https://www.chelseagreen.com/blog/lets-get-cheesy-sandor-katz-favorite-homemade-cheese/: 4 L milk brought to a slow boil, ~60 mL sauerkraut juice or citrus/vinegar, salt, drained ≥ 6 h): heat-and-acid coagulation, not the `cheese` profile's culture acidification.
- **Katz's persimmon pickling medium** (250 g vegetables, 1-2 Tbsp coarse salt, ~500 g persimmon-vinegar pulp, 2-3 days): a pickling bed in an acetic mash, neither a lacto ferment nor a vinegar.
- **Katz's tepache** (100 g sugar per ~1 L, pineapple peel, 2-5 days), **mauby** (40 g bark, 400 g sugar, 4 L, 3 days-1 week), **spontaneous fruit wine** and **rice beer** (Chelsea Green excerpts), **kisiel** (Splendid Table) and **yogurt** (Art of Fermentation excerpt): alcoholic or cereal or yogurt ferments with no profile.
- **EZ amazake** (wildfermentation.com guest post): koji saccharification of cooked rice overnight, no profile.
- **Mushroom-pulp "ryeso"** and **Cep Tamari** (Noma Projects Flavor Box): no quantities, and tamari is a by-product.

## F. Unverified leads and dead ends

- **Noma book recipes seen only in search snippets or reviews**: Beef Garum (the chicken-wing recipe names it as the template; Forager Chef reports the book's 140 °F / 70-day hold), Squid and Grasshopper garums, Pearl Barley Koji, Peaso (book recipe), Lacto Green Gooseberries, Rose / Chamomile / Elderflower / Saffron / Cherry / Carrot / Asparagus kombuchas (named in GR-noma-highlights without quantities), Whiskey Vinegar, Apple Balsamic. No opened page states their quantities.
- **Gastronomixs "Yellow pea miso"** (search snippet: 1 kg yellow split peas, 1300 g pearl-barley koji, 130 g salt, 4 % brine, yields 3300 g): not opened, and not attributed to Noma in the snippet.
- **Katz's Wild Fermentation kimchi brine (4 cups water, 4 Tbsp salt)**: corroborated only by permies.com forum posts (leads); the row katz_kimchi_brine_soaked rests on a seed-company adaptation.
- **Katz's first-edition sauerkraut (5 lb cabbage, 3 Tbsp sea salt, 1-4 weeks per gallon)**: only a Smoking Meat Forums repost; the Rachael Ray page that excerpted it now redirects to cbs.com.
- **Brandeis "Krautsourcing" kraut** (https://www.brandeis.edu/wsrc/kniznick-gallery/exhibitions/krautsourcing-nash/recipe.html: 28-30 oz cabbage, 0.6 oz / ~1 Tbsp sea salt = 2 %, 1-quart jar, refers to Katz's site): no time or temperature; corroborates the 17 g/Tbsp and ~2 % of katz_sauerkraut_basic, not added as a row.
- **Katz milk kefir grain dose**: only index pages opened (1-3 days, 24 h); no grain-to-milk ratio found from Katz. No Noma kefir exists in the opened material. Kefir remains the thinnest type.
- **Esalen napa cabbage kimchi** (https://www.esalen.org/post/napa-cabbage-and-scallion-kimchi): only recommends Katz's book; not his recipe.
- **Forager Chef maple sap vinegar** (120 g vodka, 60 g raw cider vinegar, 700 g sap, 80 g syrup, ~21 days): the Noma link appears only in a comment reply, so it is not an explicit Noma method; left out.
- **Favero Greenforest raw black-eyed pea miso** (wildfermentation.com: raw soaked peas, raw barley koji grown 48 h at 85 °F, half of 7.2 oz salt, 14 months): an uncooked-bean experiment, left out on safety grounds.
- **Tyler Zielinski, lacto-fermented gooseberry cordial** (Substack, after the Noma book): page returned 404.
- **Revolution Fermentation plums** (400 g plums, 10 g salt): not Noma; lead only.
- **burg-halle.de "NoGF.pdf"** surfaced in search: appears to be a full copy of the book on a university server; not opened (probable unauthorised copy).
- **Blocked or failed fetches**: KCRW and MR PORTER block plain fetches (opened in a browser instead); the Wayback Machine returned 429; the Google Books API had no quota; wildfermentation.com's REST API is closed (sitemaps used instead); Diamond Crystal's kosher-salt page 404s (only Morton's conversion used); Noma Projects' "Fermentation Kit 2" page 404s.
- **Privacy**: no request carried any personal identifier; no service asking for one (e.g. Unpaywall) was used.
