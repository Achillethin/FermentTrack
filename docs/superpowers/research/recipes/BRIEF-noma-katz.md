# Recipe round 2: Noma and Sandor Katz (brief for the research agent)

**Owner's ask (2026-10-25):** "loads of recipes from Noma and Noma inspiration, or Sandor Katz, for
the recipe recommender". You are a fermentation chef and curator: you know *The Noma Guide to
Fermentation* (René Redzepi & David Zilber, 2018) and Sandor Ellix Katz's *Wild Fermentation*
and *The Art of Fermentation*, and you turn their recipes into structured, sourced library rows.

**Read first:** `docs/superpowers/research/recipes/BRIEF.md`. Its rules 1-9 apply unchanged
(every number from a source you opened; never reconstruct a citation; copy facts, not prose;
units normalised; report the spread; **public sources only and never put any personal
identifier, such as an email address, a name or an account id, into a web request**; write as
you go). Also read `01-lacto-kombucha.md` for the expected depth of a recipe entry.

## Sources

- **Noma:** recipes from *The Noma Guide to Fermentation* where a page you can open states
  them (publisher excerpts, magazine and newspaper reprints, interviews with the quantities,
  Noma's own channels). Noma's lacto rule (salt = 2 % of the total weight) counts as a stated
  fact only where a page you opened states it.
- **Noma-inspired:** recipes by other chefs or publications that explicitly follow a Noma
  method, cited to the page that says so.
- **Sandor Katz:** wildfermentation.com, his published book excerpts, interviews and
  extension-style write-ups that state his quantities.
- Never paste method text. Summarise each method in one line of your own words.
- New provenance value for this round: `chef_published` (a recognised practitioner's
  published recipe). Use `peer_reviewed` or `institutional_tested` only where those apply.

## Fit the model

`fermentation_type` must be one of `lacto_ferment`, `kombucha`, `vinegar`, `koji`, `miso`,
`garum`, `kefir`, `cheese` (`src/fermenttrack/prediction/profiles.py`: read each profile's
temperature range, horizon and typical recipe). Shoyu, black garlic and similar fit no profile:
list them under "Out of model" with one line each.

Aim for **40+ recipes**:
- `lacto_ferment` 20+: Noma's fruit and vegetable lacto-ferments (plums, blueberries,
  gooseberries, mushrooms, tomatoes, asparagus, etc.) and Katz's krauts, curtido, sour
  pickles and hot sauces;
- `vinegar` 4-6, `kombucha` 4-6, `koji` and `miso` (including Noma's peasos) 4-6,
  `garum` 3-5 (Noma's koji garums: in the model a garum is protein + koji + salt), and a
  few `kefir`.

## The catalogue (`src/fermenttrack/seed_data.py`)

Current names, with role and the types each is tagged for:

Anchovies [base: garum]; Apple [flavoring: kombucha,kefir]; Basil [flavoring: kombucha,kefir];
Black tea leaves [base: kombucha]; Cabbage [base: lacto_ferment]; Calcium chloride [additive:
cheese]; Cane sugar [base: kombucha,kefir]; Caraway seeds [flavoring: lacto_ferment];
Cardamom [flavoring: kombucha,kefir]; Carrot [base: lacto_ferment]; Chilies [base:
lacto_ferment]; Cinnamon [flavoring: kombucha,kefir]; Cucumber [base: lacto_ferment]; Dill
[flavoring: lacto_ferment]; Fresh ginger [flavoring: kombucha,kefir]; Garlic [flavoring:
lacto_ferment]; Green tea leaves [base: kombucha]; Hard cider [base: vinegar]; Kefir grains
[starter: kefir]; Koji spores (A. oryzae) [starter: koji,miso]; Lemon [flavoring:
kombucha,kefir]; Lemongrass [flavoring: kombucha,kefir,lacto_ferment]; Mackerel [base:
garum]; Milk [base: cheese,kefir]; Mint [flavoring: kombucha,kefir]; Mother of vinegar
(Acetobacter) [starter: vinegar]; Napa cabbage [base: lacto_ferment]; Onion [flavoring:
lacto_ferment]; Pearl barley [base: koji,miso]; Radish [base: lacto_ferment]; Raspberries
[flavoring: kombucha,kefir]; Red wine [base: vinegar]; Rennet [starter: cheese]; SCOBY /
starter liquid [starter: kombucha]; Salt [additive]; Soybeans [base: koji,miso];
Strawberries [flavoring: kombucha,kefir]; Turmeric [flavoring: kombucha,kefir]; Water;
White rice [base: koji,miso]; White wine [base: vinegar].

- Reuse these names exactly. `catalogue_status`: `existing` when the name is in the list,
  `new` otherwise. Note in `notes` when an existing name needs a new type tag (e.g.
  Raspberries in a lacto ferment).
- **Catalogue proposals:** a table of every `new` ingredient, with how many recipes need it
  and its best USDA FoodData Central match, found **offline** in the bundled snapshot
  `src/fermenttrack/fdc_catalog_v1.csv.gz` (columns include fdc_id and description; read it
  with Python's gzip and csv, do not fetch the USDA site): fdc_id, description, data type.

## Output (write only these; do not commit, do not touch `src/`)

- `docs/superpowers/research/recipes/02-noma-katz.md`: sources opened, one entry per
  recipe (sources, facts copied, derivations, one-line method, notes), catalogue proposals,
  out of model, unverified leads.
- `docs/superpowers/research/recipes/candidates_v0.noma-katz.csv`: the recipes, the header
  of `recipes_draft_v0.lacto-kombucha.csv` exactly.
- `docs/superpowers/research/recipes/candidate_ingredients_v0.noma-katz.csv`: their rows,
  the header of `recipe_ingredients_draft_v0.lacto-kombucha.csv` exactly.

(Not `recipes_draft_v0.*`: the library build reads that pattern and would fail on uncurated
keys. The orchestrator curates these candidates into the library.)

Your final reply: at most 250 words with counts per type, how many use only existing
catalogue names, the strongest sources, and the biggest gaps.
