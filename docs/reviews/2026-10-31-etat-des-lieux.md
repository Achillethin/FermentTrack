# FermentTrack — état des lieux et plan, 31 octobre 2026

**Périmètre.** Le site partagé avec les collègues est **FermentTrack** : une PWA (React/Vite, GitHub Pages) qui appelle une API FastAPI hébergée sur Render, avec la base Postgres et l'authentification anonyme chez Supabase. Le dépôt `fermentation` est le jumeau numérique de recherche. FermentTrack n'en a copié que le moteur de règles de sécurité ; son dernier commit date du 9 septembre et il n'intervient pas dans la mise à jour du site.

**Méthode.**
- Lecture du code et des specs.
- Suite de tests lancée en local.
- App lancée en local (API sur SQLite + front Vite avec un jeton de dev), parcourue en 390 px et en 1366 px, en locale fr-FR. Les captures sont dans `docs/reviews/shots-2026-10-31/`.
- Requêtes réelles sur le moteur Ideas.
- Une sous-session dédiée a étudié les besoins des boulangers au levain. Son rapport complet : `docs/reviews/2026-10-31-besoins-boulangers-levain.md`, résumé en § 4.

Effort : **S** < ½ j · **M** 1–3 j · **L** > 3 j.

---

## 0. En une page

| Domaine | État | À retenir |
|---|---|---|
| Mise en prod | ✅ fonctionne | Un push sur `master` déploie le front ; Render redéploie l'API et applique les migrations au démarrage. **Aucun test ne tourne avant le déploiement.** |
| Qualité du code | ✅ solide | Backend : **1 305 tests OK**, 64 xfail « honnêtes » (écarts connus et documentés), 1 test de grille trop strict (écart de 1e-15) ; les 9 checks front passent. |
| Modèle prédictif | 🟡 sérieux, pas validé | Les courbes de pH lacto sont recalées sur la littérature (35 points sur 37 dans la bande de 90 %). Le **levain reste 1,5 à 2× trop lent**. Aucune validation sur de vraies fournées. |
| Front / UX | 🟡 bien amélioré depuis la critique du 26/10 | Les correctifs P0 1 à 6 sont livrés. Restent la navigation (7 onglets), le jargon, l'empilement d'avertissements, des pages très longues sur mobile, une app 100 % en anglais et le planificateur de levain. |
| Levain / boulanger | 🔴 la page phare est la moins juste | Voir § 4 : séparer « Mon levain » et « Ma fournée ». La planification à rebours (« cuire à 18 h ») manque. |
| Recettes / arômes | 🟡 mécanique riche, contenu mince | 60 ingrédients en anglais seulement, 37 recettes actives (30 brouillons en attente de ta relecture), aucune recette de *pain*. Les requêtes d'arômes renvoient des résultats peu intuitifs. |

---

## 1. Comment mettre à jour le site

### 1.1 Le circuit actuel

```
git push master ─┬─► GitHub Actions « Deploy frontend »  (seulement si frontend/** a changé)
                 │     npm ci → vite build (VITE_API_URL, VITE_SUPABASE_*) → GitHub Pages
                 └─► Render (blueprint render.yaml, auto-deploy du dépôt)
                       pip install -e . → alembic upgrade head → uvicorn
GitHub Actions « Ping backend health » : curl /health (cron toutes les 10 min, en théorie)
```

État vérifié aujourd'hui :
- `master` local = `origin/master` (0e9b889, 27/10).
- Aucune PR ouverte.
- Dernier déploiement front réussi le 27/10.
- Health checks verts.

### 1.2 Checklist d'une mise à jour, aujourd'hui

1. Travailler sur une branche, puis lancer `python -m pytest -q` et `node frontend/src/**/*.check.mjs`.
2. Si le modèle ou le catalogue a changé, regénérer la grille : `python scripts/build_recommender_grid.py --workers 4`. Le test `test_recommender_grid` le signale.
3. Si le schéma a changé, écrire une migration Alembic. Elle est appliquée au démarrage de Render : **une migration qui échoue = API down**.
4. Merger dans `master`. Le front et l'API se déploient **séparément** : pendant 1 à 3 min, un nouveau front peut parler à l'ancienne API. Pour un changement de contrat d'API, déployer l'API d'abord, ou garder la rétrocompatibilité.
5. Vérifier `/health` et faire un parcours rapide sur mobile.

### 1.3 Risques constatés et actions

| # | Constat | Pourquoi c'est important maintenant que des collègues l'utilisent | Action | Effort |
|---|---|---|---|---|
| D1 | **Pas de workflow de CI pour les tests.** Les seuls workflows sont le déploiement et le ping. | Un push cassé part directement en prod. | Ajouter `.github/workflows/ci.yml` (pytest + checks front + ruff + `vite build`) sur PR et sur `master`, et rendre le déploiement front dépendant de la CI. | S |
| D2 | `test_a_rebuilt_entry_matches_the_committed_one[lactic_fresh_cheese_curd]` échoue en Python 3.13 sur un écart de 3,5e-15. Il compare avec une égalité exacte. | La CI de D1 serait rouge pour rien, ou masquerait une vraie dérive. | Utiliser `assert_allclose(rtol=1e-12)`. Épingler Python 3.11 en CI, comme Render. | S |
| D3 | Le ping « toutes les 10 min » tourne en réalité **toutes les 4 à 6 h**. GitHub espace fortement les crons des dépôts peu actifs. | Le premier collègue qui ouvre l'app attend environ 50 s de démarrage à froid. | Un pinger externe gratuit (UptimeRobot, cron-job.org) toutes les 10 min, ou Render payant (~7 $/mois) si l'usage se confirme. Afficher un message « réveil du serveur… » côté front. | S |
| D4 | Free tier Supabase : le projet est **mis en pause après environ 7 jours sans activité**. Pas de sauvegarde automatique sur le plan gratuit. | Données des collègues. | Le ping D3 garde aussi la base active. Ajouter un `pg_dump` hebdomadaire en GitHub Action vers un artefact privé. | S |
| D5 | Pas d'environnement de préproduction : chaque merge va en prod. | Changements risqués (migrations, grille). | Render « preview environments », ou un second service gratuit + une base Supabase de staging, déclenché sur une branche `staging`. | M |
| D6 | **Aucun canal de retour, aucun suivi d'erreurs** (ni Sentry, ni analytics, ni bouton « Signaler »). | Tu ne sauras pas ce qui casse chez tes collègues. | Un bouton « Un souci ? Une idée ? » (lien vers un Google Form ou un `mailto`, avec l'URL et la version) + Sentry gratuit côté front et API. Une analytics respectueuse (Plausible/Umami) si tu veux mesurer l'usage. | S |
| D7 | Rien n'annonce les nouveautés aux utilisateurs. | Les collègues ne voient pas ce qui a changé. | Une page « Quoi de neuf » (CHANGELOG lu par le front) et le numéro de version dans Compte. | S |
| D8 | README périmé : il annonce « 20 active recipes, 7 sourdough » alors qu'il y en a 37 actives et 30 brouillons. Le manifeste PWA dit « for serious fermenters ». | Crédibilité. | Mettre le README à jour. Nouveau slogan du manifeste, par exemple « Quoi fermenter, quand c'est prêt, et que c'est sûr ». | S |
| D9 | Branches distantes périmées (`feat/ui-redesign`, `feat/product-track-v1`, `feat/recommender-spec`), au contenu déjà intégré par d'autres merges. | Confusion. | Les supprimer après vérification. | S |
| D10 | Le compte « invité » est anonyme. Si un collègue vide son navigateur, il perd ses fournées, sauf s'il a ajouté un email. | Perte de données perçue comme un bug. | Après la 2ᵉ fournée, une bannière « Sauvegarder avec mon email ». Le composant `SaveAccount.jsx` existe déjà. | S |

---

## 2. Le modèle prédictif : comment il marche, ce qu'il vaut

### 2.1 En clair

Pour chaque fournée, l'API (`prediction/service.py` → `engine.py` → `inference.py`) :

1. **Part de la recette.**
   - Composition : quantités × valeurs USDA (sucres, amidon, sel → activité de l'eau).
   - Micro-organismes du type de ferment : *L. plantarum*, *Leuconostoc*, *L. sakei* pour le lacto ; levures et LAB pour le levain, etc.
   - Température prévue.
2. **Simule 160 versions plausibles** (« ensemble ») d'un modèle cinétique mécaniste :
   - croissance de Monod ;
   - effets de la température (CTMI), du pH (CPM), des acides non dissociés, du sel et de l'éthanol ;
   - production d'acides lactique, acétique et gluconique, d'éthanol et de CO₂ ;
   - **pH calculé par bilan de charges** avec le pouvoir tampon de la matrice.

   Chaque paramètre est tiré dans une fourchette publiée (sources dans `organisms.py`).
3. **Se recale sur tes mesures.** Les pH, densités, Brix et hausses de levain que tu enregistres repondèrent les 160 versions par échantillonnage d'importance adaptatif (AMIS), ce qui resserre les bandes. Une mesure aberrante est signalée, pas absorbée.
4. **Rend** :
   - des bandes de 90 % ;
   - des jalons (« pH < 4,6 dans ~2,5 j ») ;
   - un curseur « et si à 18 °C ? ».

   Par-dessus viennent les **arômes** (`aroma.py`) : 86 composés traceurs produits par les micro-organismes ou apportés par les ingrédients, comparés à leurs seuils de perception et regroupés en 16 familles.

Pour le levain, `sourdough.py` + `bake.py` enchaînent les phases rafraîchi → pétrissage → pointage → (frigo) → apprêt. Ils modélisent la hausse (gaz produit, gluten affaibli par l'acide), le pH, la TTA et le quotient lactique/acétique. Un modèle bayésien hiérarchique apprend à trois niveaux : type de levain → boulanger → levain individuel.

C'est **le bon choix** vu l'absence totale de données d'entraînement. Le PINN et le GNN ont été écartés à juste titre et documentés avec leurs conditions de déclenchement.

### 2.2 Ce qui est démontré, et ce qui ne l'est pas

| | État |
|---|---|
| Auto-cohérence (vérité synthétique) | Couverture de la bande de 90 % : choucroute 0,93–0,96, kombucha 1,00, fromage 0,88, kéfir 1,00, **levain 0,77–0,84** (bandes trop étroites). |
| Courbes publiées, lacto | 35 points sur 37 dans la bande (Kristek, kimchi…) après l'ajout de *L. sakei* le 26/10. |
| Courbes publiées, levain | **Écart connu, en xfail strict** : le pic médian est 1,5 à 2× plus lent que la règle des boulangers. Mesuré aujourd'hui : un 1:1:1 à 24 °C culmine **12 h** après le rafraîchi, contre 4–6 h attendues ; la bande « probable » couvre 17 h. |
| Arômes | Plusieurs xfails stricts par type (lacto, vinaigre, kombucha, miso/garum). Les familles « vinaigré », « poisson » et « phénolique » sont « basse résolution » (1 à 2 composés). |
| Vraies fournées | **Aucune validation.** `model.validated = false`. Le critère est écrit : prévision des mesures futures à partir des passées, couverture de 85–95 % et CRPS meilleur qu'une courbe moyenne. Il n'a jamais tourné, faute de données. |
| Calibration des scores d'arômes | Porte fermée : 0 fournée goûtée sur les 30 requises. |
| Règle VEG-001 vs modèle | Ouvert (curation § 9). Le modèle donne 27 % de chances qu'une choucroute nature passe pH < 5,0 en 48 h à 20 °C (6 % à 16 °C), ce qui concorde avec Kristek. **La règle de sécurité fait donc échouer une choucroute fraîche normale.** Décision à prendre avec une source. |

### 2.3 Recommandations sur le modèle

1. **Recaler le levain en priorité (M–L).** C'est la prédiction que les boulangers vérifient tout de suite. Recaler μmax et la latence des levures et LAB du levain sur des courbes de hausse publiées (et sur tes propres fournées) jusqu'à ce que le xfail passe. En attendant, afficher la règle empirique à côté du modèle. Détail en § 4.
2. **Lancer la boucle de validation réelle, même petite (M).**
   - Script `scripts/validate_on_batches.py` : sur toute fournée terminée avec ≥ 3 mesures, prévoir les dernières à partir des premières.
   - Calculer couverture et CRPS par type ; rapport hebdomadaire (comme la porte de calibration).
   - Avec 5 à 10 collègues actifs, quelques dizaines de fournées suffisent pour un premier signal.
3. **Trancher VEG-001 (S, décision).** Garder « < 5,0 en 48 h » en citant la source (ANSES/NCHFP), ou reformuler pour les légumes salés à ≥ 2 %. Sinon, l'app dit de jeter des bocaux normaux.
4. **Le « goût » comme mesure (release 3 de la spec v2).** Exploiter « trop doux / juste / trop acide » comme observation ordinale de l'acidité. Tout le monde n'a pas de pH-mètre ; c'est la façon la plus réaliste d'avoir des données.
5. **Plus de membres pour le levain.** Le rapport le pointe : ~100 membres effectifs, d'où des queues sous-couvertes. À arbitrer contre le CPU de Render, par exemple 256 membres uniquement pour `sourdough`, mis en cache.
6. **Ne pas** ajouter de ML tant que les déclencheurs de la spec (§ 9) ne sont pas atteints. C'est déjà bien écrit.

---

## 3. Front et UI/UX

### 3.1 Ce qui a été corrigé depuis la critique du 26/10 (vérifié)

- ✅ Bannière de sécurité honnête : « No safety rule flagged by your readings so far » au lieu d'un faux vert.
- ✅ Saisie du pH : « 5,8 » est bien lu 5,8, plage contrôlée, mesures supprimables, **bandeau « Log pH » en un geste** sur la fournée et dans Today.
- ✅ Ideas : « Made from what you have » en tête. Chou + carotte + ail renvoie « Brined cabbage and carrot with garlic, nothing to buy ».
- ✅ Une seule chronologie entre la carte et la fournée ; « 48 h : likely / maybe / unlikely ».
- ✅ « Jeter cette fournée… » avec une raison ; confirmation avant Repeat.
- ✅ Bouton « Supprimer mes données » (RGPD).

### 3.2 Ce qui reste (captures dans `docs/reviews/shots-2026-10-31/`)

| # | Constat | Fix | Prio · effort |
|---|---|---|---|
| U1 | **Navigation à 7 onglets + Export CSV**, sur 2 lignes et environ 150 px en mobile (`m-today.png`). « Planner » ne dit pas que c'est du pain. | 4 onglets en barre basse fixe sur mobile : **Aujourd'hui · Fournées · Idées · Levain**. Comparer et le journal passent dans Fournées, Export dans Compte. | P1 · S |
| U2 | **Premier lancement** : une seule porte, « Start a batch in 30 seconds ». | Trois portes : « Que faire avec ce que j'ai ? » → Idées ; « Quand nourrir mon levain ? » → Levain ; « Suivre un bocal déjà lancé » → Fournées. | P1 · S |
| U3 | **App 100 % anglaise** (`<html lang="en">`), alors que les dates s'affichent en français (« dim. 08:50 ») et que tes collègues sont francophones. Le champ de date du levain sort en format US (« 10/31/2026, 04:45 PM »). | Internationalisation FR/EN : un fichier de chaînes, détection de `navigator.language`, noms d'ingrédients et de recettes traduits. **Le plus gros levier d'adoption** auprès de tes collègues. | P1 · M–L |
| U4 | **Pages très longues sur mobile** : la page Ideas avec résultats fait **8 164 px** pour 5 cartes, chaque carte affichant recette, sécurité, chronologie, curseur, cibles et provenance (`m-ideas-results.png`). Le planificateur fait 3 774 px. | Cartes repliées : titre, « utilise : … », « prêt dans ~3 sem. », bouton. Le détail s'ouvre au tap. | P1 · M |
| U5 | Enums bruts : « Prep And Salt », « Lacto Ferment », « LOW RES », « P90 ». | Une fonction `humanize()` centrale, en casse de phrase. | P1 · S |
| U6 | **Avertissements empilés** : sur la fournée, « Not calibrated yet » + paragraphe encadré + « model estimate » ×2. Sur chaque carte, un encadré Sécurité + « model estimate ». | Un seul avertissement par page et une puce « Fiabilité ? » qui ouvre le détail. Garder la ligne de sécurité *différenciée*, pas le paragraphe générique. | P1 · S |
| U7 | L'onglet Biochemistry (KEGG, EC) est au même niveau que Log. | Le déplacer sous Prévision → « La science derrière ». | P2 · S |
| U8 | Taxonomie : on lit *L. plantarum* et *L. brevis*. | *Lactiplantibacillus plantarum*, *Levilactobacillus brevis* (Zheng 2020). | P2 · S |
| U9 | `document.title` reste « FermentTrack » sur toutes les pages. | Un titre par route. | P2 · S |
| U10 | Aucun bouton « + Nouvelle fournée » sur Today une fois une fournée créée. | Bouton flottant. | P2 · S |

**Design system.** La palette chaude, l'en-tête façon étiquette de bocal et les cibles de 44 px sont bien réalisés. La priorité n'est pas un nouveau design : c'est **la hiérarchie** (une action principale par écran, le reste replié) et **la langue**.

---

## 4. Module boulanger / levain : plan en deux parties

> Synthèse de la sous-session. Matrice besoins × couverture, sources et détail : `docs/reviews/2026-10-31-besoins-boulangers-levain.md`.

### 4.1 Ce que veulent les boulangers

La recherche a porté sur les forums (The Fresh Loaf, r/Sourdough, r/Breadit), une quinzaine d'apps et la littérature (Calvel, Hamelman, Ginsberg, Landis 2021, Gänzle).

1. **Le timing** passe avant tout. Il faut caser 24 à 36 h de process autour du travail et du sommeil, et **le frigo sert de tampon**. On veut un planning **à rebours** (« je veux cuire samedi à 18 h ») présenté en **fenêtres**, pas en heures exactes.
2. **Un levain imprévisible** : les saisons, la sortie du frigo, « nourri il y a 12 h ».
3. **La peur de rater la création** : le « faux départ » des jours 3 à 6, quand tout s'arrête et que les débutants jettent leur levain.
4. **Le diagnostic** : hooch, acétone, pellicule, moisissure ; pain trop ou pas assez acide.
5. **Des outils** : bocal témoin avec cible de pousse *selon la température* (le test de flottaison est jugé peu fiable), % boulanger, température de l'eau, journal de rafraîchis avec rappels.

**Marché.** Une quinzaine d'apps font du planning à rebours, toutes avec des **durées fixes**. Aucune n'a de vrai modèle. C'est l'avantage de FermentTrack, mais il n'est visible qu'avec le planning à rebours et le journal.

### 4.2 Verdict sur le module actuel

Le moteur est solide et tourne (81 tests levain OK, 5 xfail attendus). Mais **il répond à « que se passe-t-il si… », pas à « que dois-je faire, et quand »**.

- **Partie A (mon levain)** : quasi absente. Seulement des descriptions de style d'une ligne : rien sur la création, l'entretien ou le diagnostic, pas de journal du levain.
- **Partie B (ma fournée)** : partielle, avec des « faux-amis » :
  - le bloc « au pic du levain » affiche la **pâte** au moment du mélange (pousse 0 %, pH 5,8) — bug confirmé ;
  - « Prêt pour » ne fait varier que le ratio, **à heure de nourrissage fixe** ;
  - la cible de pousse du pointage est **fixée à 75 %**, quelle que soit la température ;
  - les rappels d'une fournée suivie utilisent des durées génériques, pas le plan ;
  - les Types II et III (procédés industriels) sont proposés au même niveau qu'un levain maison ;
  - l'état du levain se réduit à « mûr » ou « sorti du frigo » ;
  - **le pic est 2× trop lent** : 11–12 h pour du 1:1:1 à 24 °C, contre 4–8 h en réalité.

### 4.3 Plan : séparer « Mon levain » (A) et « Ma fournée » (B)

```
#/levain                    Accueil boulanger : 2 grandes cartes
├─ (A) Mon levain
│  ├─ mes-levains[/:id]     état (« nourri il y a 9 h, pic vers 15 h 40 »), journal des rafraîchis, vitesse apprise
│  ├─ creer                 parcours J1→J14 avec suivi (le faux départ expliqué)
│  ├─ types[/:key]          fiches : levain maison, liquide, dur, lievito madre, San Francisco, seigle,
│  │                        eau de fruits ; Types II/III et poolish/biga « pour comprendre »
│  ├─ entretien             comptoir, frigo, vacances, séchage, réveil après le frigo
│  ├─ diagnostic            arbre « Mon levain… » (hooch, acétone, trop acide… ; moisissure = jeter)
│  └─ convertir             liquide ↔ dur ↔ madre ↔ seigle ; adapter une recette
└─ (B) Ma fournée
   ├─ fournee/nouvelle      assistant : recette → « cuire à » ou « commencer à » → contraintes → état du levain
   ├─ fournee/:id           planning heure par heure en direct, « c'est fait » → re-planification
   ├─ fournee/rafraichi     tableau de rafraîchi (l'actuel, en outil autonome)
   └─ fournee/calculs       % boulanger, température de l'eau, levain ↔ levure
```

**Chaque fiche de type** contient :
- le microbiote typique, avec les noms à jour ;
- l'hydratation, le ratio et la température ;
- la durée jusqu'au pic (empirique) ;
- un curseur lactique ↔ acétique ;
- les usages (quels pains) et la fenêtre d'utilisation (jeune / au pic / mûr) ;
- l'entretien ;
- « faire évoluer vers… » ;
- les erreurs fréquentes et les sources.

Le tableau des fiches pré-rempli est dans le rapport détaillé (§ 6.2). Une nuance scientifique est à bien expliquer : un levain **dur et froid** a une **part acétique** plus forte, mais pas forcément une **acidité totale** plus forte.

**Fonction phare de B : le solveur à rebours** (`POST /sourdough/schedule`).
- **Leviers** : heure du rafraîchi, ratio, durée du frigo.
- **Contraintes** : sommeil, travail, températures jour/nuit.
- **Méthode** : recherche sur grille, en réutilisant le calcul empilé du tableau de rafraîchi. Elle optimise la **robustesse** (80–90 % des simulations tombent dans des plages autorisées), pas la médiane.
- **Sortie** : une liste d'actions horodatées avec leurs fenêtres, les nuits signalées et un **plan B** (« si le levain n'est pas prêt à 8 h 30, attendre jusqu'à 10 h ; au-delà, raccourcir le frigo »). Préchauffage, cuisson et repos sont inclus.

**Données qui débloquent l'apprentissage** : un **journal de rafraîchis** (table `culture_feedings`). Chaque rafraîchi d'entretien avec une montée relevée apprend la vitesse de *ton* levain **sans attendre une fournée**. C'est le moyen le plus réaliste d'obtenir des données de calibration.

### 4.4 Priorités pour le levain

| # | Action | Partie | Effort |
|---|---|---|---|
| 1 | Corriger les faux-amis : lecture « au pic », « prêt pour » qui fait aussi glisser l'heure de nourrissage, nuits signalées, rappels alignés sur la prévision | B | S–M |
| 2 | Recaler le pic et le pointage (faire passer le xfail ; données Landis 2021 sur Dryad) ; table « T° de pâte → % de pousse » ; en attendant, afficher la règle empirique et demander un relevé de bocal | B | M |
| 3 | Solveur à rebours « cuire à… » sous contraintes | B | M–L |
| 4 | Accueil `#/levain` en deux parties, en français, avec la navigation conservée ; « Pro » renommé « Voir la science » | A+B | S–M |
| 5 | Journal de rafraîchis, état réel du levain, rappels d'entretien par levain | A | M |
| 6 | Contenus : 9 fiches, parcours de création, arbre de diagnostic, « quand jeter », bocal témoin | A | M (rédaction) |
| 7 | Re-planification en direct dans la fournée suivie (« levain doublé », « bocal à +40 % », « au frigo ») + `.ics` mis à jour | B | M |
| 8 | Calculateurs (température de l'eau, conversions), levains en plusieurs étapes, températures jour/nuit, Types II/III rangés à part | A+B | M |

**Risques.**
- Le calcul à rebours **amplifie l'incertitude** : avec une bande de 16 h, tout planning est « infaisable ». Le recalage (#2) est donc un prérequis du solveur (#3).
- Côté sécurité, seule la **moisissure (duvet, traînées roses ou orange) → jeter** est pertinente. Ne pas brancher les règles de pH des lacto-fermentations sur le levain.
- Plusieurs chiffres viennent de forums : **à revérifier sur Hamelman, Calvel et Ginsberg avant de publier les fiches**. La sous-session n'avait accès qu'aux extraits de recherche.

---

## 5. Suggestions de recettes et d'arômes : prochaines étapes

### 5.1 Ce que j'ai observé en interrogeant le moteur

| Requête | Résultat | Lecture |
|---|---|---|
| Chou, carotte, ail | ✅ « Brined cabbage and carrot with garlic » puis « Brined carrot with garlic », rien à acheter | Le composeur lacto fonctionne. |
| « Carrots », « Beets », « Ginger root » | ❌ « No proven recipe uses… » | Le catalogue ne reconnaît que les noms exacts. Il compte **60 ingrédients, en anglais** : ni betterave, ni poivron, ni chou-fleur, ni piment frais distinct. |
| Arôme « fruity » | Kéfir de lait, faisselle, kéfir 5 % ; puis kombucha au café | Défendable chimiquement (esters, diacétyle), mais contre-intuitif pour un humain qui pense kombucha aux fruits ou cidre. |
| « sour » + « malty » | Kombucha au café, vinaigre Orléans, kombucha verveine | **Aucun pain.** Les 7 recettes « sourdough » sont des *levains*, pas des pains : la question la plus naturelle d'un boulanger (« un pain acide et malté ») n'a pas de réponse. |

### 5.2 Prochaines étapes, par ordre de valeur

1. **Élargir et franciser le catalogue d'ingrédients (M, contenu).**
   - Passer de 60 à environ 150 ingrédients courants, en priorité les légumes de lacto-fermentation : betterave, poivron, chou-fleur, haricot vert, céleri, fenouil, piments, citron confit, oignon rouge…
   - Ajouter des **synonymes et pluriels** et les **noms FR** : « carottes », « betterave », « gingembre »…
   - Le guide `docs/ADDING_AN_INGREDIENT.md` existe déjà. C'est un travail idéal pour une sous-session de curation, que tu relis ensuite.
2. **Relire les 30 recettes en brouillon (S côté toi, décision).** C'est le goulot actuel : 13 lacto, 4 garum, 4 vinaigre, 4 miso, 3 koji… Chaque recette validée enrichit immédiatement toutes les requêtes.
3. **Ajouter une famille « Pains au levain » (M).** Recettes de pains (campagne, seigle 100 %, complet, pain de mie au levain, focaccia, pizza) reliées à un style de levain et à un profil d'arômes. Le levain liquide donne plus de lactique, crème et yaourt ; le levain dur plus d'acétique et de céréale grillée ; le seigle plus de malt et d'épices. C'est le pont entre Idées et la partie B du § 4.
4. **Un vocabulaire d'arômes « humain » (S–M).**
   - Prévu dans la spec v2 (V14 : « funky », « avoid »).
   - Ajouter des **descripteurs concrets** sous chaque famille : fruity → « pomme, poire, banane » ; buttery → « beurre, yaourt » ; malty → « céréale, pain grillé ».
   - Afficher **2 ou 3 composés clés** avec leur odeur (« acétate d'éthyle : bonbon anglais »).
   - Le moteur sait déjà le faire (`aroma_data.py`).
5. **Classer d'abord par pertinence de type, puis par arôme (S).** Quand l'utilisateur ne précise aucun ingrédient, montrer d'abord une carte par grande famille (lacto / boisson / pain / produit laitier), au lieu de trois kéfirs. Diversité imposée dans le top 3.
6. **Boucle personnelle (release 3 de la spec, M–L).**
   - Question « acidité par rapport à ce que tu voulais » dans la dégustation.
   - **« La prochaine fois : arrête 2 jours plus tôt, ou à 18 °C »** sur Repeat.
   - « Bocaux côte à côte » (1 base, 2–3 variantes, dégustation par paires).

   C'est ce qui rendra les suggestions *personnelles* avec < 20 utilisateurs, bien avant que la calibration globale (30 fournées) ne s'ouvre.
7. **Accords et usages (S, contenu).** Sur chaque carte, une ligne « Avec quoi ? » (choucroute → saucisses, sandwich Reuben ; levain dur → pain de garde). C'est très demandé par les débutants et ça ne coûte que de la curation.
8. **Plus tard : ferments mixtes** (release 6 : koji + lacto, sauce piquante au koji) et **badge « cette expérience nous apprendrait quelque chose »** (EIG, release 5). Ils ne prennent du sens qu'une fois la boucle de dégustation alimentée.

---

## 6. Feuille de route proposée

| Sprint (≈ 1 semaine) | Contenu | Pourquoi d'abord |
|---|---|---|
| **S0 — Filet de sécurité** | D1 CI, D2 test flottant, D3/D4 ping externe + sauvegarde, D6 bouton retour + Sentry, D8 README | Des collègues utilisent déjà l'app : ne rien casser, et entendre ce qu'ils disent. |
| **S1 — Levain partie B, quick wins** | « Prêt pour » à rebours (feed × ratio), règle empirique affichée, cohérence entre titre et graphique, nuits signalées, recalage du pic du levain | La page la plus visible et la moins juste. |
| **S2 — Navigation + FR** | U1 à U6 (4 onglets, 3 portes, `humanize`, un seul avertissement, cartes repliées), début de l'i18n FR | Adoption par des collègues francophones. |
| **S3 — Levain partie A** | Pages « Mon levain » : créer, types, entretien, diagnostic, conversion ; journal du levain | Le contenu éditorial différencie l'app des calculateurs. |
| **S4 — Catalogue et recettes** | Ingrédients ×2,5 avec noms FR, revue des 30 brouillons, famille « Pains », descripteurs d'arômes | Les suggestions deviennent utiles au-delà de la choucroute. |
| **S5 — Boucle d'apprentissage** | Dégustation « acidité vs souhait », « La prochaine fois… », script de validation sur vraies fournées | Les données des collègues commencent à améliorer le modèle. |

**Décisions qui t'appartiennent** :
- VEG-001 (§ 2.3.3) ;
- passer Render en payant ou non (D3) ;
- FR seul ou FR + EN (U3) ;
- validation des 30 brouillons ;
- garder koji/miso/garum en « exploratoire » ou les masquer.
