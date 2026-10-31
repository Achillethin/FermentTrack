# Besoins des boulangers au levain et module FermentTrack : état des lieux et plan de restructuration

**Date :** 2026-10-31
**Périmètre :** module boulanger/levain de FermentTrack (moteur `prediction/sourdough.py` + `prediction/bake.py`, routes `/sourdough/*`, intégration aux batches, écran `#/levain`).
**Objectif du propriétaire :** savoir si le module répond aux vrais besoins, puis le scinder en deux parties :
- **(A) Faire et entretenir mon levain** : création, types, entretien, amélioration, diagnostic, conversions.
- **(B) Projection / planification de la fournée** : quand rafraîchir, pétrir, façonner et cuire, avec un planning heure par heure.

---

## 0. Verdict en une page

**Ce que veulent les boulangers.** La douleur n°1, de loin, c'est le **timing**. Un boulanger cherche à caser une fournée de 24 à 36 h entre son travail et son sommeil. Il veut aussi savoir pourquoi son levain est lent, trop acide, ou couvert de « hooch ». Côté outils, il attend :
- un **planning à rebours** (« je veux cuire samedi à 18 h ») ;
- des **fenêtres** plutôt que des heures exactes, et le **froid comme tampon** ;
- un **calculateur de pourcentages** qui compte le levain dans la farine ;
- un **journal de rafraîchis** avec rappels ;
- des **critères visuels fiables** : bocal témoin (aliquot), pourcentage de pousse selon la température de pâte, poke test. Le test de flottaison, lui, est jugé peu fiable.

Les apps du marché (une quinzaine sur iOS) font presque toutes du planning à rebours **par règles fixes**. Aucune n'a de vrai modèle de fermentation.

**Ce que fait le module.** Il possède le moteur scientifique le plus sérieux que j'aie vu dans ce domaine :
- cinétique multi-espèces, physique du gaz, acidité (pH, TTA, quotient lactique/acétique) ;
- 11 styles et 9 farines (T-numbers) ;
- **apprentissage bayésien par levain, par boulanger et par type**.

Il tourne : 81 tests passent, 5 xfail attendus, et les deux scripts `node *.check.mjs` sont OK. Mais **il répond surtout à la question « si je fais ça, que se passe-t-il ? »** (calcul vers l'avant), pas à **« que dois-je faire, et quand ? »** (calcul à rebours sous contraintes).

**Couverture actuelle des besoins (§ 4) :**
- **Partie A :** quasi absente. Il y a un catalogue de styles en une ligne chacun, mais rien sur la création, l'entretien ou le diagnostic, ni journal de rafraîchis.
- **Partie B :** partielle, avec trois « faux-amis » qui trompent l'utilisateur :
  - le tableau « prêt pour » ne fait varier que le ratio, à heure de nourrissage fixe ;
  - la cible de pousse est fixée à 75 % quelle que soit la température ;
  - les rappels d'un batch suivi utilisent des durées génériques (pointage 8 h, retard 16 h) au lieu du plan.

À cela s'ajoutent :
- **une calibration lente**, reconnue par la spec : 1:1:1 à 24 °C donne un pic médian à 11,4 h, contre 4 à 8 h chez les boulangers ;
- **un bug d'affichage confirmé** : le bloc « au pic du levain » lit la pâte au moment du mélange (rise 0 %, pH 5,8).

**Recommandation.** Garder le moteur. Construire au-dessus :
1. **(A)**, une couche éditoriale et un journal de levain : peu de code, beaucoup de contenu.
2. **(B)**, un **solveur à rebours sous contraintes** qui réutilise le calcul empilé du tableau de rafraîchi. Il doit présenter des **fenêtres** et un **planning d'actions** : rafraîchi, autolyse, rabats, façonnage, retard, préchauffage, enfournement, repos.

Le Top 8 des actions est au § 6.5.

---

## 1. Méthode et limites

- **Recherche web.** J'ai fait une vingtaine de requêtes WebSearch : forums (The Fresh Loaf, r/Sourdough, r/SourdoughStarter, en passant par des miroirs), fiches d'apps de l'App Store, blogs techniques (The Sourdough Journey, The Perfect Loaf, King Arthur) et littérature scientifique (Landis 2021, Gänzle & Zheng 2018, revues sur les types I/II/III, Puratos Sourdough Library). **WebFetch était bloqué** par le réseau de la session (`thesourdoughjourney.com` et les miroirs Reddit ne résolvent pas). Je me suis donc appuyé sur les extraits renvoyés par la recherche, sans lire les pages en entier. Les chiffres tirés de forums et de fiches d'apps sont des **déclarations** (de développeurs ou d'amateurs), pas des mesures. Je n'ai pas eu accès au texte des livres (Calvel, Hamelman, Forkish, Tartine, Ginsberg) : ce que j'en rapporte passe par les citations de lecteurs sur The Fresh Loaf, et je le signale à chaque fois.
- **Code.** J'ai lu `docs/SOURDOUGH_GUIDE.md`, la spec `2026-09-28-sourdough-engine-design.md`, `sourdough.py`, `bake.py`, `routers/sourdough.py`, les passages sourdough de `routers/prediction.py` et `routers/batches.py`, `schemas.py` (plan, feeding chart), `stages.py`, `reminders.py`, `models.py` et `frontend/src/sourdough/*`. J'ai aussi relu le passage levain de la critique du 2026-10-26.
- **Exécution, sans aucune modification du dépôt :**
  - `pytest -q -k "sourdough or bake"` : **81 passed, 5 xfailed** (dont l'xfail strict `test_home_starter_median_peak_matches_baker_timing`, `tests/test_sourdough_engine.py:222`) ;
  - `node plan.check.mjs` et `node share.check.mjs` : OK ;
  - une sonde Python lancée hors du dépôt (`python -I -B`) a appelé `bake.forecast` (résultats au § 3.2).

---

## 2. Ce que veulent les boulangers

### 2.1 Trois profils

| Profil | Ce qu'il fait | Ce qu'il attend d'un outil |
|---|---|---|
| **Débutant** (premier levain, souvent après une vidéo) | Crée un levain, rate les premiers jours, cuit le week-end | « Mon levain est-il mort ? », un pas-à-pas jour par jour, un diagnostic en photos, un planning simple pour le week-end |
| **Amateur confirmé** (The Fresh Loaf, r/Sourdough) | Cuit 1 à 3 fois par semaine autour du travail, joue sur l'hydratation et les farines, mesure la température de pâte, utilise un bocal témoin | Un planning à rebours avec contraintes, un pourcentage de pousse selon la température, un journal, l'adaptation aux saisons, la conversion de recettes |
| **Artisan / pro** | Levain chef → levain tout point, 2 ou 3 rafraîchis par jour, pousse contrôlée, plusieurs pâtes | Plusieurs étapes, une température de pâte de base (eau à utiliser), mise à l'échelle, TTA/pH, régularité d'une fournée à l'autre |

### 2.2 Questions qui reviennent sans cesse

1. **« Mon levain de 5 jours ne monte plus, il est mort ? »** C'est la première question du wiki r/SourdoughStarter. Un démarrage avec beaucoup de bulles les jours 1 à 3, suivi d'un calme plat, est normal. Debra Wink l'explique : des bactéries productrices de gaz (*Leuconostoc*) dominent au début, s'arrêtent vers pH 4,5, et les levures ne prennent le relais qu'à pH plus bas. Son remède : du jus d'ananas à la place de l'eau ([TFL, Pineapple Juice Solution](https://www.thefreshloaf.com/node/10901), [r/SourdoughStarter wiki](https://reddit.birdcat.cafe/r/SourdoughStarter/comments/1j6b6ob/read_before_posting_questions)).
2. **« Quand est-il prêt ? Il doit doubler ? flotter ? »** Le test de flottaison donne des faux positifs (un levain jeune flotte aussi) et des faux négatifs (un levain liquide remué coule). King Arthur conclut qu'il ne permet pas de juger ([King Arthur, float test](https://www.kingarthurbaking.com/blog/2019/01/02/the-float-test-for-yeast-dough-and-sourdough-starter), [You Knead Sourdough](https://www.youkneadsourdough.com.au/blogs/faq/is-the-float-test-reliable)). La pratique recommandée : marquer le niveau sur le bocal (élastique) et suivre la montée.
3. **« Liquide gris dessus (hooch), odeur d'acétone : que faire ? »** C'est la faim. Les avis divergent : le reverser (plus acide) ou le jeter (moins acide) ([Pantry Mama, hooch](https://pantrymama.com/sourdough-starter-liquid-how-to-deal-with-sourdough-hooch/)).
4. **« Moisissure ? Traînées roses ou orange ? »** Un consensus fort : on jette (King Arthur, Pantry Mama). Une pellicule blanche (kahm) ou une teinte rose due au sel ou au seigle ne doivent pas être confondues avec la moisissure ([Pantry Mama, moldy starter](https://pantrymama.com/moldy-sourdough-starter/), [King Arthur troubleshooting](https://www.kingarthurbaking.com/blog/2018/03/09/sourdough-starter-troubleshooting-2)).
5. **« Comment caser ça avec un travail de 9 h à 17 h ? »** Le schéma récurrent : levain le matin, pâte le soir, pointage la nuit ou au froid, façonnage le matin, frigo, cuisson le soir. Le frigo sert de « pause » ([TFL Sourdough Schedule](https://www.thefreshloaf.com/comment/421358), [TFL Friday evening bake, 9-5](https://www.thefreshloaf.com/node/55520/help-sourdough-timings-friday-evening-bake-i-work-95), [TFL work schedule](https://thefreshloaf.com/comment/338468), [The Perfect Loaf weekday](https://www.theperfectloaf.com/simple-weekday-sourdough-bread/comment-page-2/)).
6. **« Quand arrêter le pointage ? »** La « méthode à deux facteurs » (The Sourdough Journey) associe la température de pâte à un pourcentage de pousse cible : environ 30 % à 27 °C (style Tartine) et 75 à 100 % à 21 °C. Le temps n'est qu'un « prédicteur faible » ([The Sourdough Journey, percentage rise](https://thesourdoughjourney.com/the-mystery-of-percentage-rise-in-bulk-fermentation/), [dough temping](https://thesourdoughjourney.com/dough-temping-for-perfect-sourdough-fermentation/), [timetables PDF](https://thesourdoughjourney.com/wp-content/uploads/2023/01/Bulk-Fermentation-Timetables-V1.0.pdf)). Le bocal témoin est l'outil standard, avec une réserve : les rabats ne s'y reproduisent pas ([TFL Calculating Rise Percentage](https://www.thefreshloaf.com/comment/545502)).
7. **« Mon pain est trop acide, ou pas assez. »** Pour plus d'acidité acétique : plus ferme et plus froid. Pour un goût plus doux et lactique : plus liquide et plus chaud, avec un levain jeune. **Attention à la nuance :** un levain ferme accumule l'acide plus lentement. Il est plus « piquant » mais pas forcément plus acide au total ([TFL Two levains, why is one more sour](https://www.thefreshloaf.com/node/28219), [TFL warmer = more sour?](https://www.thefreshloaf.com/node/17562/warmer-fermentation-more-sour-flavour), [TFL too sour](https://www.thefreshloaf.com/node/71331/too-sour)).
8. **« Comment passer mon levain liquide en levain dur, ou en lievito madre ? »** Il faut 2 ou 3 rafraîchis, et environ une semaine pour que le microbiote d'un lievito madre se stabilise. Le ratio de conversion pour une recette est discuté ([TFL Lievito Madre](https://www.thefreshloaf.com/node/73311/another-lievito-madre-thread), [TFL Panettone conversion](https://www.thefreshloaf.com/comment/478034)). Hamelman donne une table de conversion liquide ↔ ferme, en annexe selon des lecteurs ([TFL Hamelman 125 %](https://www.thefreshloaf.com/print/67229)).
9. **« Quelle eau utiliser pour obtenir une pâte à 25 °C ? »** C'est la température de base (Desired Dough Temperature) : eau = n × T° visée − T° air − T° farine − T° levain − échauffement dû au pétrissage ([King Arthur DDT](https://www.kingarthurbaking.com/blog/2018/05/29/desired-dough-temperature), [TFL friction factor](https://www.thefreshloaf.com/comment/415747)).
10. **« Comment compter le levain dans les pourcentages de boulanger ? »** C'est une source de confusion fréquente ([TFL Levain calculation](https://thefreshloaf.com/node/64600/levain-calculation), [The Perfect Loaf calculator](https://www.theperfectloaf.com/starter-and-levain-calculator/), [sourdough.co.uk](https://www.sourdough.co.uk/?p=3080)).
11. **« Je pars une semaine, comment le garder ? »** Frigo, levain plus ferme, rafraîchi avant départ. Pour le seigle, Ginsberg indique un entretien au frigo 1 ou 2 fois par semaine, puis un rafraîchi moins de 36 h avant l'usage, selon des lecteurs ([TFL Rye Baker maintenance](https://www.thefreshloaf.com/comment/483312), [TFL Feeding Rye Sour](https://www.thefreshloaf.com/node/71142/feeding-rye-sour)).
12. **« Levain jeune ou levain au pic ? »** Tartine utilise un levain *jeune* de quelques heures. Un levain resté toute la nuit au chaud s'épuise et donne un pain dense ([TFL Tartine](https://www.thefreshloaf.com/node/71870)).

### 2.3 Les douleurs, par ordre de fréquence

1. **Le timing autour du travail et du sommeil.** Les étapes tombent à 2 h du matin ou en pleine réunion. Le frigo est le levier de flexibilité.
2. **Un levain imprévisible.** Le même ratio prend 5 h l'été et 12 h l'hiver. Un levain sortant du frigo démarre lentement. D'un levain à l'autre, la vitesse de montée varie d'environ 15 fois (Landis 2021, 40 levains mesurés) ([eLife/PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7837699), [NCSU](https://news.ncsu.edu/2021/01/the-sourdough-map/)).
3. **Les saisons et la température de la cuisine.** Nuit plus froide que le jour, cuisine chauffée ou non : une seule température par étape ne rend pas compte de la réalité.
4. **Les farines.** Complète et seigle accélèrent et acidifient. Une farine faible ne retient pas le gaz.
5. **L'hydratation.** Le passage de 70 % à 80 % change la manipulation et la pousse.
6. **Juger la fin du pointage et de l'apprêt** (poke test, bocal témoin).
7. **La « peur de mal faire »** pendant la création : moisissure, mort supposée.

### 2.4 Ce que proposent les apps existantes (fonctionnalités, sans rien recopier)

| Fonction | Exemples (fiches App Store / web) | Fréquence |
|---|---|---|
| **Planning à rebours depuis l'heure de cuisson** | Bulk Planner ([mergeek](https://mergeek.com/latest/K5lYgAMB0DwW1wx2)), Dough Timer ([App Store](https://apps.apple.com/app/id6755980237)), Sourdough Timeline, LoafLab ([mwm](https://mwm.ai/apps/loaflab-sourdough-planner/6762065648)), Sourdough Schedule ([appshunter](https://appshunter.io/ios/app/sourdough-schedule-bake-timer/id6771680688)), S.D Timer ([App Store](https://apps.apple.com/il/app/s-d-timer-pro/id6760554281)), Timeline Generator web ([granarchist](https://granarchist.pages.dev/timeline)) | Très fréquente : c'est la fonction phare |
| **Re-planification quand ça dérive** | CrumbKeeper ([App Store](https://apps.apple.com/app/id6795631667)) | Rare |
| **Courbe de montée du levain et « time to peak »** | Crumb ([App Store](https://apps.apple.com/us/app/id6777510093)), BakeReady (score de maturité, fenêtre de pic) ([App Store](https://apps.apple.com/app/id6785357199)) | En hausse |
| **Rappels de nourrissage selon l'état** (comptoir 12 h, frigo hebdo) | Sourdough Starter Tracker ([App Store](https://apps.apple.com/app/id6755709217)), BakeIt! (« temps depuis le dernier repas ») ([App Store](https://apps.apple.com/app/id6792235598)) | Fréquente |
| **Plusieurs levains, photos, historique** | Levain ([App Store](https://apps.apple.com/app/id6780496763)), The Daily Crumb ([App Store](https://apps.apple.com/app/id6759510215)) | Fréquente |
| **Calculateur % boulanger et hydratation (levain compris)** | Crumb, Sour & Dough ([App Store](https://apps.apple.com/app/id6462694910)) | Quasi universelle |
| **Apprentissage des pics** | Bulk Planner (« logs starter peaks and bake results to refine future estimates ») | Rare, et sans modèle |
| **Hors ligne, sans compte** | LoafLab, Bulk Planner | Argument de vente fréquent |

**Lecture.** Ces apps planifient avec des **durées fixes ou des règles empiriques** (par exemple, la vitesse double tous les 8 °C environ, selon un calculateur web cité par la recherche). La précision n'est jamais annoncée. Ce marché est saturé ([docs/IDEATION_CONTEXT.md:19-27](../IDEATION_CONTEXT.md) le note déjà). **L'avantage différenciant de FermentTrack**, un vrai modèle qui apprend *ton* levain, n'a de valeur que si les deux briques banales existent aussi : planning à rebours et journal. Pour l'instant, il manque les deux.

### 2.5 Vocabulaire FR / EN à utiliser dans l'interface

| Français (boulangerie) | Anglais (forums) | Définition courte |
|---|---|---|
| Levain chef / levain mère | Mother / starter / chef | La culture entretenue |
| Levain tout point | Levain (build), final build | Le levain construit pour la fournée, prêt à l'emploi |
| Rafraîchi / rafraîchissement | Feed / refresh / build | Ajout de farine et d'eau ; « ratio 1:5:5 » = levain : farine : eau |
| Levain liquide / levain dur (ferme) | Liquid levain / stiff levain | Environ 100–125 % / 50–65 % d'hydratation |
| Pâte mère (lievito madre), *rinfresco*, *bagnetto* | Lievito madre, refresh, bath | Levain ferme italien ; bain d'eau sucrée avant rafraîchi |
| Autolyse | Autolyse | Farine + eau au repos avant le levain et le sel |
| Pétrissage / frasage | Mix / knead | — |
| Rabats / étirements-rabats | Stretch & folds, coil folds | Pendant le pointage |
| Pointage (première fermentation) | Bulk fermentation | De la fin du pétrissage au façonnage |
| Préfaçonnage, détente | Pre-shape, bench rest | — |
| Façonnage | Shaping | — |
| Apprêt (seconde fermentation) | Proof / final proof | — |
| Pousse contrôlée / retard au froid / blocage | Cold retard | Apprêt ou pointage au frigo (3–5 °C) |
| Bocal témoin | Aliquot jar | Échantillon de pâte pour lire le % de pousse |
| Test du doigt | Poke test | Fin d'apprêt |
| Test de flottaison | Float test | Peu fiable |
| Hooch | Hooch | Liquide alcoolisé : signe de faim |
| Température de base | Desired dough temperature (DDT) | Calcul de la température de l'eau |
| Acidité titrable (TTA), quotient fermentaire (QF) | TTA, FQ | Lactique/acétique |
| TA (Teigausbeute, allemand) | Dough yield (DY) | 100 + hydratation % ; TA 200 = 100 % |
| Grundsauer / Vollsauer (Détmold) | Basic sour / full sour | Étapes des levains de seigle allemands |

Termes officiels FR : la boulangerie française distingue *levain chef* et *levain tout point* ([The Good Life France](https://thegoodlifefrance.com/?p=114274)). Les fiches techniques meunières donnent pointage, apprêt et blocage à 4 °C pendant 10 à 15 h ([Grands Moulins de Paris, fiche](https://www.grandsmoulinsdeparis.com/media/fiche_technique/00422.pdf), [Condifa, baguette au levain](https://pp.condifa.fr/fr/recettes/baguette-au-levain/?print=pdf)). **Le décret pain n° 93-1074 du 13 septembre 1993** réserve l'appellation « pain au levain » à un pH ≤ 4,3 et à au moins 900 ppm d'acide acétique endogène (chiffres repris par un site secondaire : à vérifier sur Légifrance). C'est une donnée intéressante pour une fiche « levain français » et pour le mode Pro (TTA et quotient fermentaire).

### 2.6 Ce que dit la littérature (pour la partie A)

- **Types I/II/III** (Böcker, De Vuyst & Neysens 2005, Gänzle) :
  - **Type I** : artisanal, rafraîchi en continu (back-slopping), température ambiante. Il est dominé par des lactobacilles « adaptés aux insectes », surtout *Fructilactobacillus sanfranciscensis*, et par une ou deux levures.
  - **Type II** : industriel, liquide, chaud (30–40 °C). Il porte des lactobacilles des groupes *L. delbrueckii* et *Limosilactobacillus reuteri*. Il **ne lève pas** : il faut ajouter de la levure.
  - **Type III** : séché, inactif, il sert d'acidifiant et d'arôme.
  - **Type 0** : terme parfois donné aux pré-ferments à levure (poolish, biga).
  - Sources : Gänzle & Zheng 2018, *Int J Food Microbiol*, [doi:10.1016/j.ijfoodmicro.2018.08.019](https://doi.org/10.1016/j.ijfoodmicro.2018.08.019) ; revue [Frontiers in Microbiology 2019](https://www.frontiersin.org/journals/microbiology/articles/10.3389/fmicb.2019.00201) ; [De Vero et al. 2021](https://iris.unimore.it/bitstream/11380/1243353/1/De%20Vero%20et%20al%202021%20Review%20Functional%20and%20healthy%20feautures%20of%20sourdoughs.pdf) ; *Handbook on Sourdough Biotechnology*, 2ᵉ éd. 2023 ([fiche](https://www.betterread.com.au/book/handbook-on-sourdough-biotechnology-book-9783031230868.do)).
- **Levains domestiques** (Landis et al. 2021, 500 levains) : *S. cerevisiae* est la levure la plus fréquente. Les bactéries acétiques, quand elles sont présentes, **ralentissent la montée** et donnent une odeur de vinaigre. La géographie n'explique presque rien : ce sont les pratiques et la farine qui comptent ([PMC7837699](https://pmc.ncbi.nlm.nih.gov/articles/PMC7837699)).
- **Puratos Sourdough Library** (Saint-Vith, Belgique) : plus de 100 levains conservés, analysés avec l'Université de Bari (Gobbetti). Plus de 700 levures et plus de 1 500 bactéries lactiques ont été isolées ([Bakerpedia](https://bakerpedia.com/exploring-the-sourdough-library/), [Baking Business](https://bakingbusiness.com/articles/23991-world-heritage-sourdough-library-opens)). C'est un bon argument éditorial : un levain est un écosystème propre à un lieu et à une pratique.
- **Seigle, méthode de Détmold** : Anfrischsauer (TA 220–250, 25–26 °C, 5–6 h, étape « levure »), puis Grundsauer (TA 160–170, 23–27 °C, 9–24 h, étape « arôme »), puis Vollsauer (TA 190, 28–30 °C, 3 h, étape « acidité ») ([Pistor](https://www.pistor.ch/sites/default/files/2019-04/Sauerteig_Pistor.pdf), [Yumda](https://www.yumda.com/de/lexikon/Sauerteigf%C3%BChrung.html)). C'est le cas d'école d'une **construction en plusieurs étapes, où la température change les arômes**.
- **Hamelman** (via lecteurs) : levain liquide à 125 % (20 % de levain, 12–16 h à 21 °C) et levain ferme à 60 %, qu'il décrit comme plus doux. Calvel (via lecteurs) utilise des levains intermédiaires pour **diluer l'acidité** du chef ([TFL Calvel](https://www.thefreshloaf.com/node/4006/100-sourdough-bread-taste-bread-r-calvel), [TFL stiff levain](https://www.thefreshloaf.com/node/12979/pain-au-levain-stiff-levain)).
- **Eau de fruits (yeast water)** : surtout des levures, peu acide. Elle s'utilise en levain (eau de fruits + farine à 1:1) ou à la place de l'eau. Les forums déconseillent de la mélanger au levain chef ([TFL Researching Yeast Water](https://www.thefreshloaf.com/node/74400/researching-yeast-water), [TFL fruit yeast water](https://www.thefreshloaf.com/node/56762/fruit-yeast-waterhelp-please)). Les données publiées sur son microbiote sont minces : à présenter comme « pratique d'amateurs ».
- **Taxonomie** : depuis Zheng et al. 2020 (*IJSEM* 70:2782, [doi:10.1099/ijsem.0.004107](https://doi.org/10.1099/ijsem.0.004107)) :
  - *Fructilactobacillus sanfranciscensis* ;
  - *Lactiplantibacillus plantarum* ;
  - *Levilactobacillus brevis* ;
  - *Limosilactobacillus reuteri* ;
  - *Kazachstania humilis* (anciennement *Candida milleri* / *C. humilis*).

---

## 3. Le module actuel

### 3.1 Ce qui existe

| Brique | Où | Ce qu'elle fait |
|---|---|---|
| Catalogue de 11 styles | `src/fermenttrack/prediction/sourdough.py:136-214` | Microbiote, populations au mûrissement, acides, hydratation, ratio, température et farine par défaut, une à deux lignes de description, sources |
| 9 farines | `sourdough.py:73-91` | Cendres, protéines, sucres, facteur gluten (plafond de montée), amylases |
| Plan → phases chaînées | `sourdough.py:254-291` (Build/Dough/Proof/Plan), `484-591` (`compile_plan`) | Levain → pâte (dilution, sel, levure) → apprêt ou retard |
| Physique | `sourdough.py:612-628` | Part acétique selon hydratation et température (`PHI_REF`, `HYDRATION_EXPONENT`), plafond de montée, fuite de gaz liée à l'acidité |
| Prévision | `prediction/bake.py:257-360` (`_run_chain`) | Jalons : levain doublé, levain au pic, fin de pointage à X % de pousse ; bandes 5–95 % |
| Tableau de rafraîchi | `bake.py:673-737` | Pic par ratio en un seul calcul empilé (mêmes tirages aléatoires pour chaque ratio) |
| Apprentissage | spec § 6 ; `routers/sourdough.py:77-95` | Hiérarchie croisée global → type → boulanger → levain |
| API | `routers/sourdough.py:39-139` | `GET /sourdough/catalog`, `POST /sourdough/plan`, `POST /sourdough/feeding-chart` |
| Batch suivi | `routers/prediction.py:105-146`, `routers/batches.py:105-110` | Plan stocké sur le batch ; mélange et façonnage placés selon les changements d'étape |
| Écran planificateur | `frontend/src/sourdough/Planner.jsx`, `PlanForm.jsx`, `plan.js` | Formulaire en % boulanger, résultats (pic, fin de pointage, enfournement), frise, graphiques, mode Pro, tableau de rafraîchi |
| Partage et calendrier | `frontend/src/sourdough/share.js:15-165` | Lien de partage (plan dans le hash), export .ics avec alarme 15 min avant chaque événement |
| Carte plan d'un batch | `frontend/src/sourdough/PlanCard.jsx` | Affiche et modifie `sourdough_plan` |

### 3.2 Vérifications exécutées

- Tests : **81 passed, 5 xfailed** (`pytest -q -k "sourdough or bake"`, 24 s). `plan.js ok`, `share.js ok`.
- Sonde du moteur (prior seul, aucun levain appris, médiane [p05–p95]) :

| Cas | Pic du levain | Repère boulanger |
|---|---|---|
| Levain maison 1:1:1, 24 °C | **11,4 h** [7,6–23,5] | 4–8 h (spec § 5, King Arthur) |
| Levain maison 1:5:5, 22 °C | 18,3 h [11,4–30,2] | environ 12 h à 1:4:4 (spec) |
| Levain maison 1:5:5, 27 °C | 13,3 h [8,6–22,2] | — |
| Levain liquide 1:3:3, 26 °C | 13,1 h [7,6–23,7] | Hamelman : 125 %, 1:5 environ, 12–16 h à **21 °C** ; donc nettement plus court à 26 °C |
| Plan complet : 1:5:5 à 24 °C, pâte 1 kg de farine, 20 % de levain, 25 °C, retard 14 h à 4 °C | pic 16,1 h ; **pointage 9,8 h** (jusqu'à +75 %) | À confronter aux tables de The Sourdough Journey. Les recettes courantes visent 4–6 h à 25 °C pour 20 % de levain, et une pousse plus faible à cette température |

- **Bug confirmé** : autour du pic, la série `rise` passe de 115,6 % à **0,0 %** et le `ph` de 4,38 à **5,80** à t = 16,1 h, c'est-à-dire au moment du mélange. Le bloc Pro « At the levain peak » lit cet instant (`Planner.jsx:244-256`, `valueAt(s.t_h, s.p50, peakH)`). Il affiche donc la pâte fraîchement mélangée, comme l'avait observé la critique (`docs/reviews/2026-10-26-site-critique.md:124`).

---

## 4. Matrice besoins × couverture actuelle

Légende : **C** = couvert · **P** = partiel · **A** = absent · **FA** = faux-ami (présent mais trompeur).

### Partie A : faire et entretenir mon levain

| ID | Besoin | Statut | Preuve (fichier:ligne) | Commentaire |
|---|---|---|---|---|
| A1 | Créer un levain de zéro, jour par jour (farines, températures, faux départ, jus d'ananas) | **A** | `docs/SOURDOUGH_GUIDE.md:1-55` (rien) ; `sourdough.py:113-125` (le modèle part toujours d'un levain *mûr*) | C'est la question n°1 des débutants |
| A2 | Catalogue des types avec fiche (hydratation, ratio, T°, profil, usages) | **P** | `sourdough.py:136-214` (une à deux lignes par style) ; `PlanForm.jsx:106-160` (StyleCard) | Les données existent mais sont trop maigres pour un humain ; aucune page « fiche » |
| A3 | Microbiote typique par type | **P** | `sourdough.py:129-134` (noms antérieurs à 2020), `143-191` | Juste pour le modèle ; taxonomie à mettre à jour (critique : `site-critique.md:198`) |
| A4 | Routines d'entretien (comptoir quotidien, frigo hebdomadaire, vacances, séchage) | **A** | Seul un choix binaire `starter: ripe | refrigerated` : `sourdough.py:291`, `371` ; `PlanForm.jsx:242-251` | La critique réclamait déjà « passé son pic » et « paresseux » (`site-critique.md:226`) |
| A5 | Journal des rafraîchis et rappels de nourrissage par levain | **A** | `models.py:30-50` (Culture sans champ de dernier rafraîchi) ; `models.py:125-141` (Reminder rattaché à un batch, pas à un levain) | Le champ `repeat_interval` existe et peut servir |
| A6 | Diagnostic : trop acide, lent, acétone, hooch, odeur de vomi au début, viscosité | **A** | Aucun contenu (grep hooch/acétone/moisissure : 0 résultat dans `frontend/src/sourdough`, `prediction/`) | — |
| A7 | Orienter le profil (plus ou moins acide, lactique ou acétique) | **P** | Physique : `sourdough.py:612-613` ; quotient fermentaire en mode Pro : `Planner.jsx:244-256`, `bake.py:85` | Le modèle sait le calculer, mais l'app ne **conseille** rien |
| A8 | Conversion entre types et hydratations (liquide ↔ dur ↔ lievito madre, recette) | **P** | Grammes personnalisés : `PlanForm.jsx:289-295` ; `scaleBuild` : `plan.js:180-192` ; la pâte recalcule l'eau selon l'hydratation du levain : `plan.js:141-146` | Pas d'assistant de conversion ni de transition sur plusieurs rafraîchis |
| A9 | Moisissure et sécurité (le seul vrai cas de sécurité) | **A** | Hors périmètre de la spec : `2026-09-28-sourdough-engine-design.md:11` | Une fiche « quand jeter » suffit |
| A10 | Critères de maturité : bocal et % de montée | **C** | `SOURDOUGH_GUIDE.md:31` ; `bake.py:93-94` (`READING_KEYS`) ; `frontend/src/BatchView.jsx:250-256` | Bien pensé |
| A10b | Test de flottaison expliqué (et ses limites) | **A** | — | Il faut l'expliquer, ne serait-ce que pour le **déconseiller** |
| A11 | Apprendre *mon* levain | **C** | spec § 6 ; `routers/sourdough.py:77-95` ; `routers/prediction.py:146` | Exige des batches terminés avec relevés et étapes saisies : rien ne guide l'utilisateur vers ce « premier relevé » |
| A12 | Farines (T-numbers, seigle, complète, mélanges) | **C** | `sourdough.py:73-91` ; `PlanForm.jsx:162-178`, `323-352` | — |
| A13 | Vocabulaire et interface en français | **A/P** | Interface en anglais (`Planner.jsx`, `PlanForm.jsx`) ; `native_name` seulement : `sourdough.py:109` | Public francophone visé par le propriétaire |
| A14 | Photos du levain et de la mie | **A** | Aucun modèle d'image (`models.py`) | Classique chez les concurrents ; priorité basse |
| A15 | Plusieurs levains (blé, seigle, eau de fruits) avec lignée | **P** | `Culture.style`, `born_from` : `models.py:36-43` ; `routers/cultures.py:25-27` | Pas de type « eau de fruits » dans `STYLES` |

### Partie B : planifier la fournée

| ID | Besoin | Statut | Preuve (fichier:ligne) | Commentaire |
|---|---|---|---|---|
| B1 | Quand mon levain sera-t-il au pic ? | **P** (calibration) | Jalons : `bake.py:303-312` ; xfail : `tests/test_sourdough_engine.py:222` ; spec § 5 « Known calibration gap » | Médiane environ 1,5 à 2 fois trop lente ; bande de 16 h |
| B2 | Fenêtre d'utilisation du levain (de « doublé » à « juste après le pic ») | **P** | `bake.py:306-312` (deux points) | Présenter une **fenêtre**, pas deux heures |
| B2b | Lecture « au pic » (pH, TTA, montée) | **FA (bug)** | `Planner.jsx:244-256` ; sonde § 3.2 | Lit la pâte au mélange |
| B3 | Quel ratio pour être prêt à H ? | **FA** | `Planner.jsx:357-418` ; `plan.js:326-345` (`hoursUntil`, `closestRow`) | Heure de nourrissage figée ; propose 1:10:10 au lieu de « nourris à 15 h en 1:5:5 » (`site-critique.md:119-120`) |
| B4 | Planning à rebours : « je veux cuire à 18 h » | **A** | Tout part de t = 0 au rafraîchi (`share.js:97-115`, spec Appendice A « All times are hours from the levain feed ») | Fonction phare de tout le marché |
| B5 | Contraintes de sommeil et de travail (pas d'action entre 23 h et 7 h, ni de 9 h à 18 h) | **A** | Fix proposé, non fait : `site-critique.md:132` | — |
| B6 | Calculateur % boulanger (levain inclus dans la farine totale) | **C** | `plan.js:136-166` ; `PlanForm.jsx:394-441` | Bon, mais en anglais et au 0,1 g près |
| B7 | Température de base (eau à utiliser) | **A** | La température de pâte est une entrée : `PlanForm.jsx:406` | Calcul trivial, très demandé par les confirmés |
| B8 | Durée de pointage selon T°, % de levain, farine, sel | **P** | `bake.py:313-322` ; `sourdough.py:528-576` | À valider face aux tables publiées (sonde : 9,8 h à 25 °C) |
| B9 | Cible de pousse selon la température de pâte (méthode à deux facteurs) | **FA** | 75 % fixe : `sourdough.py:276`, `plan.js:64`, `PlanForm.jsx:405` | À 26–27 °C, viser 75 % mène au sur-pointage selon The Sourdough Journey |
| B10 | Bocal témoin : comment faire, quoi lire | **P** | Note « shape now (aliquot jar) » : `bake.py:321` ; relevé `rise` | Pas de mode d'emploi ; pas de saisie rapide « bocal à +40 % » depuis le planning |
| B11 | Fin d'apprêt (poke test) ou critère d'apprêt | **A** | Apprêt à durée fixe : `sourdough.py:279-282`, `schemas.py:683-685` | Le modèle simule l'apprêt mais ne propose aucune heure « prête » |
| B12 | Retard au froid comme **tampon** (fenêtre de 8 à 48 h) | **P** | `RAMP_H` : `sourdough.py:372` ; libellé : `sourdough.py:583` ; durée fixe | Le levier n°1 de flexibilité n'est pas exploité comme une plage |
| B13 | Préchauffage, cuisson, refroidissement | **P** | « Into the oven around » = fin de l'apprêt : `Planner.jsx:227-235` ; `share.js:113` | Il manque préchauffage (45–60 min), cuisson et repos avant coupe |
| B14 | Planning heure par heure (autolyse, rabats, préfaçonnage, façonnage) | **P** | Frise à 3 phases : `Planner.jsx:148-181` | Il manque les actions |
| B15 | Rappels et alarmes | **P / FA** | ICS : `share.js:98-115`, `144-165` (bon). Batch suivi : `stages.py:83-125` et `reminders.py:11-27` (durées fixes : « watch for peak » **1 h** après le rafraîchi, pointage 8 h, retard 16 h) | Les rappels du batch contredisent la prévision du même batch |
| B16 | Re-planifier quand le levain est en retard ou en avance | **P** | Batch : `routers/prediction.py:86-104`, `bake.py:559-578` (étapes saisies) ; le planificateur n'a pas de « maintenant » (`Planner.jsx:285`) | Il manque « mon levain a doublé à 14 h 10 → recalcule la suite » |
| B17 | Températures variables (nuit plus froide, saisons) | **P** | Une température par phase : `sourdough.py:254-282` ; moyenne mesurée par phase : `bake.py:194-205` | Le moteur accepte un `TemperatureSchedule` (`model.py`) : à exposer |
| B18 | Constructions en plusieurs étapes (chef → tout point, Détmold, 3 rafraîchis de lievito madre) | **A** | Un seul `Build` : `sourdough.py:285-291` ; promis aux pros : spec ligne 9 | — |
| B19 | Levure en complément (hybride) | **C** | `sourdough.py:272-273` ; `PlanForm.jsx:407-421` | — |
| B20 | Partager un plan | **C** | `share.js:15-93` | — |
| B21 | Honnêteté des prévisions | **C** (fond) / **P** (forme) | `bake.py:80-83` (avertissement) ; `Planner.jsx:262-265` | Bandes de 16 h affichées en gros sans guide d'usage (`site-critique.md:121`) |
| B22 | Mise à l'échelle et plusieurs pâtons (artisan) | **P** | `scaleBuild` : `plan.js:180-192` | Pas de multi-pâtes |
| B23 | Accès : le planificateur est dans la navigation | **P** | `frontend/src/App.jsx:78` (« Planner ») ; la page levain sort de la navigation (`site-critique.md:168`) | — |

**Bilan.**
- **Partie A (16 lignes) :** 3 C, 5 P, 7 A, 1 A/P (A13).
- **Partie B (24 lignes) :** 3 C, 11 P, 5 A, 3 faux-amis (B2b, B3, B9), plus 2 lignes mixtes : B15 (P/FA) et B21 (C/P).

Le moteur couvre bien ce qui se *calcule*. Le produit couvre mal ce qui se *décide*.

---

## 5. Faux-amis et défauts à traiter en premier

1. **La lecture « au pic » affiche la pâte** (`Planner.jsx:244-256`). Correctif : lire la valeur juste *avant* le début de la phase `bulk`, ou mieux, faire calculer ces valeurs par le serveur (pH, TTA et montée au pic, comme `ph_at_peak` dans `bake.py:731`).
2. **Le tableau « prêt pour »** cherche seulement le ratio, à heure de nourrissage fixe (`Planner.jsx:376-418`). Correctif rapide : faire glisser l'heure de nourrissage *dans une plage autorisée* et garder le couple (heure, ratio) le plus robuste. Toutes les données sont déjà dans les `rows` (le décalage horaire est exact, le pic ne dépendant pas de l'heure à température constante).
3. **La cible de pousse est fixée à 75 %** (`sourdough.py:276`). Correctif : valeur par défaut tirée d'une table « T° de pâte → % de pousse », d'après The Sourdough Journey, de la forme 21 °C → 75–100 %, 24 °C → 50–75 %, 27 °C → 30–50 %. Ces valeurs sont **à reprendre de la source primaire** : je n'ai pas pu lire le PDF.
4. **Les rappels des batches suivis** utilisent `stages.py:83-125` (rappel « watch for peak » une heure après le rafraîchi, pointage fixe de 8 h). Correctif : pour un batch avec `sourdough_plan`, fixer `due_at` au p05 du jalon prévu (« vérifie le bocal »), puis au p50.
5. **Les types II et III sont proposés au même niveau qu'un levain maison** (`PlanForm.jsx:132-160`). Ce sont des procédés industriels : un amateur qui choisit « Type II » à 37 °C ne fera pas de pain levé sans levure. Les ranger dans une section « Comprendre / industrie », hors du choix par défaut.
6. **Le choix binaire « mûr / sortant du frigo »** (`PlanForm.jsx:242-251`, facteur de latence ×3 : `sourdough.py:371`, `738`) ignore l'état réel (« nourri il y a 12 h », « au pic », « retombé », « au frigo depuis 6 jours »). Or c'est **là** que le modèle se trompe le plus (`site-critique.md:226`).
7. **Le message « ready to use for most breads » au doublement** (`bake.py:308`) est correct mais incomplet. Selon le style, levain jeune (Tartine) ou levain au pic : la fiche de style devrait fixer la fenêtre recommandée.
8. **La calibration** : la médiane reste lente tant qu'aucune donnée n'existe (xfail strict). Tant que ce n'est pas corrigé, afficher le repère empirique et **demander un relevé de bocal** pour calibrer (`site-critique.md:129`).

---

## 6. Plan d'amélioration : séparation (A) / (B)

### 6.1 Arborescence proposée (routes hash, cohérentes avec `App.jsx:83-88`)

```
#/levain                     Accueil boulanger : deux grandes cartes, (A) « Mon levain » et (B) « Planifier une fournée »
│
├─ (A) Mon levain
│  ├─ #/levain/mes-levains           Mes levains : état (nourri il y a 9 h, au pic vers 15 h 40), prochain rafraîchi, journal, courbe
│  │   └─ #/levain/mes-levains/:id   Fiche de MON levain : historique des rafraîchis, vitesse apprise (« ~1,4× plus rapide que la moyenne »), lignée
│  ├─ #/levain/creer                 Créer un levain : parcours jour 1 à 14, avec suivi (chaque jour = un rafraîchi saisi)
│  ├─ #/levain/types                 Les types de levain (catalogue)
│  │   └─ #/levain/types/:key        Fiche de type (§ 6.2)
│  ├─ #/levain/entretien             Routines : comptoir, frigo, vacances, séchage, réveil après le frigo
│  ├─ #/levain/diagnostic            « Mon levain… » : arbre de diagnostic
│  └─ #/levain/convertir             Convertir : liquide ↔ dur ↔ lievito madre ↔ seigle ; adapter une recette
│
└─ (B) Fournée
   ├─ #/fournee/nouvelle             Assistant : (1) recette (2) quand ? « cuire à » OU « je commence à » (3) mes contraintes (4) mon levain maintenant
   ├─ #/fournee/:batchId             Planning heure par heure en direct (batch suivi) ; « c'est fait » à chaque étape → re-planification
   ├─ #/fournee/rafraichi            Tableau de rafraîchi (l'actuel FeedingChart, en outil autonome)
   └─ #/fournee/calculs              Calculateurs : % boulanger, température de base (eau), conversion levain ↔ levure
```

Rediriger `#/levain?p=…` (liens déjà partagés) vers `#/fournee/nouvelle?p=…`. Garder la navigation principale sur ces pages (`site-critique.md:168-176`).

**API (existante, à étendre) :**
- garder `GET /sourdough/catalog`, avec des champs éditoriaux par style (voir le modèle de fiche ci-dessous) ;
- garder `POST /sourdough/plan` (vers l'avant) et `POST /sourdough/feeding-chart` ;
- **nouveau** `POST /sourdough/schedule` : solveur à rebours (§ 6.3) ;
- **nouveau** `POST /cultures/{id}/feedings`, `GET /cultures/{id}/feedings` : journal de rafraîchis ;
- **nouveau** `GET /cultures/{id}/state` : état prédit du levain maintenant (temps depuis le rafraîchi, pic attendu, « au frigo depuis »).

### 6.2 Partie (A) : contenus éditoriaux à écrire

**Modèle de fiche de type**, stocké en données (champs ajoutés à `LevainStyle` ou fichier `levain_guides_v1.json` servi par le catalogue), en français et en anglais :

```
nom FR / EN / natif · famille (Type I…) · en une phrase
microbiote typique (noms à jour, avec source) · hydratation (plage) · TA
ratio de rafraîchi habituel · température · durée jusqu'au pic (plage empirique)
profil aromatique : lactique / acétique (curseur), notes
usages : quels pains · fenêtre d'utilisation (jeune / au pic / mûr)
entretien : fréquence au comptoir / au frigo · robustesse
faire évoluer vers… : liens vers les conversions
erreurs fréquentes · sources
```

**Fiches à rédiger.** Les valeurs ci-dessous sont des ordres de grandeur issus des sources du § 2. Les cellules « (est.) » sont à revérifier avant publication.

| Type | Microbiote typique | Hydratation | Rafraîchi habituel | T° | Profil | Usages | Évoluer vers… |
|---|---|---|---|---|---|---|---|
| **Levain maison de blé** (« starter ») | Très variable. *S. cerevisiae* (levure la plus fréquente), *Lactiplantibacillus plantarum*, *Levilactobacillus brevis*, souvent *F. sanfranciscensis* ; parfois des bactéries acétiques (montée lente, vinaigre) (Landis 2021) | 100 % | 1:1:1 à 1:5:5, une ou deux fois par jour au comptoir, ou chaque semaine au frigo | 22–26 °C | Variable ; lactique si jeune et chaud | Pains de campagne, miches, pain de mie au levain | Levain liquide (augmenter le ratio et l'eau), levain dur (2 ou 3 rafraîchis à 50–60 %) |
| **Levain liquide** (boulangerie française) | *F. sanfranciscensis* dominant, avec *S. cerevisiae* | 100–125 % (Hamelman 125 %) | 1:2 à 1:5 ; 2 ou 3 rafraîchis par jour en boulangerie, ou conservation au froid en fermenteur | 24–28 °C (12–16 h à 21 °C chez Hamelman) | Doux, lactique, « crémeux » | Pain de tradition au levain, baguette, viennoiserie au levain | Levain dur : diminuer l'eau sur 2 ou 3 rafraîchis |
| **Levain dur (ferme)**, chef → tout point (Calvel) | *F. sanfranciscensis*, *K. humilis*, *S. cerevisiae* | 50–65 % | Chef → tout point en 1 à 3 rafraîchis | 22–26 °C | **Part** acétique plus forte (plus « piquant »), mais acidité totale qui monte plus lentement : la nuance est à expliquer | Pain de campagne, miche, longues conservations | Lievito madre (plus ferme, plus chaud, rafraîchis rapprochés) |
| **Lievito madre** (pasta madre) | *F. sanfranciscensis* et *K. humilis* | 45–50 % | 1:1 (à 1:2), toutes les 3–4 h avant un panettone (3 rinfreschi) ; *bagnetto* (bain d'eau tiède légèrement sucrée) ; conservation *legato* (ficelé) | 26–28 °C | Très peu acide, très levant | Panettone, pandoro, colomba, brioches | Il faut environ une semaine de rafraîchis rapprochés pour stabiliser le microbiote (forums) |
| **San Francisco** | *F. sanfranciscensis* (nommée d'après lui) et *K. humilis* (Kline & Sugihara 1971) | 50–60 % (levain-éponge) | Reconstruit environ toutes les 8 h | environ 27 °C | Très acide, acétique | Sourdough de San Francisco | — |
| **Levain de seigle** (Roggensauerteig ; FR « levain de seigle ») | *F. sanfranciscensis*, *Lb. brevis*, *Limosilactobacillus pontis/panis*, *K. humilis*, *S. cerevisiae* (Brandt 2004) | TA 180–200 (80–100 %), ou méthode de Détmold (§ 2.6) | 1:5 à 1:10, longues durées ; au frigo une ou deux fois par semaine (Ginsberg) | 25–30 °C selon l'étape | Acidité élevée, recherchée : **l'acide est nécessaire au seigle** (il freine les amylases, sinon la mie colle) | Pains de seigle, Vollkornbrot, pumpernickel ; aussi base robuste pour levains de blé | Blé : 2 ou 3 rafraîchis à la farine blanche (TFL) |
| **Eau de fruits** (« yeast water ») | Surtout des levures, peu de bactéries lactiques (données publiées minces) | Liquide, puis levain à 100 % | Fruit + eau (+ sucre) pendant 3 à 7 jours, puis levain eau de fruits + farine à 1:1 | 24–28 °C | Peu acide, fruité | Pains doux, brioches ; mélange possible avec un levain de blé | Ne pas l'ajouter au levain chef (forums) ; pomme : risque de viscosité |
| **Type II** (à titre d'information) | *L. reuteri*, *L. delbrueckii* et apparentés | 150–200 % | Fermenteur industriel, 1:10 | 30–40 °C | Très acide ; **ne lève pas** | Acidifiant industriel, aide à la panification avec levure | — |
| **Type III** (à titre d'information) | Aucun microbe vivant | Poudre | — | — | Acide et arômes | Pain à la levure « goût levain » | — |
| **Poolish, biga** (comparaison, Type 0) | *S. cerevisiae* (levure du commerce) | 100 % / 45–55 % | 0,1 % / 0,3–0,5 % de levure | 18–20 °C, 12–20 h | Arômes, peu acide | Baguette, pizza, ciabatta | Comparer avec un levain liquide ou dur : même rôle technologique, mais ni bactéries ni acidité |

**Parcours « Créer mon levain »** (contenu et suivi) :
- **J1–J2 :** farine complète ou de seigle + eau à 1:1 (50 g + 50 g), à 24–26 °C. Chlore dans l'eau : avis partagés.
- **J2–J3 :** bulles franches et odeur parfois désagréable (fromage, vomi) : c'est normal.
- **J3–J6 :** calme plat, le **faux départ** expliqué par Wink. Continuer une fois par 24 h ; option jus d'ananas. Ne pas jeter.
- **J5–J10 :** retour d'une montée régulière, odeur de yaourt ou de pomme : passer à 2 rafraîchis par jour à 1:2:2, puis 1:5:5.
- **« Prêt » :** il double en 4 à 8 h à 24–26 °C, trois jours de suite. Le **critère se lit au bocal**, pas au test de flottaison.

Chaque jour correspond à un rafraîchi saisi dans le journal (A5). Le modèle ne simule pas la création (elle est hors périmètre) : c'est un parcours éditorial avec suivi, pas une prévision.

**Arbre « Mon levain… »** (diagnostic) :

| Symptôme | Causes probables | Que faire | Gravité |
|---|---|---|---|
| Ne monte plus (jours 3 à 6) | Faux départ | Continuer, garder au chaud ; jus d'ananas | Normal |
| Monte peu ou lentement (levain établi) | Froid, ratio trop dilué, farine pauvre, sortie du frigo, bactéries acétiques | 2 rafraîchis par jour au chaud pendant 2 ou 3 jours, un peu de complète ou de seigle, ratio 1:2:2 | Bénin |
| Hooch (liquide gris) | Faim | Rafraîchir plus souvent ou plus ferme ; reverser (plus acide) ou jeter (plus doux) | Bénin |
| Odeur d'acétone ou de vernis | Faim (esters) | Rafraîchir, augmenter le ratio | Bénin |
| Pain trop acide | Levain trop mûr, peu rafraîchi, ferme et froid, retard long | Levain plus jeune, plus liquide et plus chaud, moins de levain ou retard plus court | Goût |
| Pas assez acide | L'inverse | Plus ferme, plus froid, levain plus mûr, complète, retard plus long | Goût |
| Pâte qui colle et s'effondre | Levain trop mûr (protéolyse), sur-pointage, farine faible | Utiliser le levain au pic, viser une pousse adaptée à la température | Technique |
| Pellicule blanche plate | Levure de surface (kahm) | Gratter, rafraîchir | Bénin |
| **Duvet (toute couleur), traînées roses ou orange** | Moisissure, *Serratia* | **Jeter et recommencer** (garder éventuellement un levain séché de secours) | **Sécurité** |

**Calculateur « Convertir »** :
- **Changer l'hydratation** : à partir de *m* g de levain à *h₁* %, cible *h₂* %, nouveau rafraîchi de *F* g de farine. Eau à ajouter W = h₂·(F + m/(1+h₁)) − m·h₁/(1+h₁). Le calculateur affiche que 2 ou 3 rafraîchis sont nécessaires pour que le microbiote suive.
- **Substitution dans une recette** : garder la farine et l'eau *totales* constantes. Le calcul existe déjà dans `plan.js:141-146` et peut être réutilisé.
- **Levain ↔ levure** : repère de forum, environ 5 à 7 g de levure fraîche pour 100 g de levain liquide. À présenter comme un ordre de grandeur.

### 6.3 Partie (B) : fonctionnalités

**B-1. Planning à rebours sous contraintes (`POST /sourdough/schedule`).**
- *Entrées :*
  - recette (comme le plan actuel) ;
  - **cible** : soit « sortir du four à 18 h samedi », soit « commencer à » ;
  - **contraintes** : plages interdites (sommeil 23 h–7 h, travail) et plages libres ;
  - températures : jour, nuit, frigo ;
  - **état du levain** : dernier rafraîchi et température, ou « au frigo depuis N jours » ;
  - préférences : retard au froid autorisé (min et max), levain jeune ou au pic.
- *Leviers :* heure du rafraîchi, ratio (1:1 à 1:10), éventuellement % de levain, durée du retard au froid (le **tampon**).
- *Méthode :*
  - recherche sur grille (heure de rafraîchi par pas de 30 min × ratios × durées de retard) ;
  - **réutiliser le calcul empilé** du tableau de rafraîchi (`bake.py:673-737`) pour la phase levain ;
  - pour le pointage, résoudre une fois par (ratio, % de levain, T°) : l'heure de départ ne change pas la cinétique à température constante. Avec des températures jour/nuit, il faut faire un calcul par décalage, ce qui demande un cache ;
  - critère : probabilité que chaque **action** (rafraîchir, pétrir, façonner, mettre au frigo, enfourner) tombe dans une plage autorisée, en intégrant la bande des membres de l'ensemble, plus un bonus de marge (minutes de tampon avant une plage interdite).
- *Sorties :*
  - **liste d'actions** horodatées avec fenêtres, par exemple : « Rafraîchir 1:5:5 vendredi 21 h 40 (levain prêt entre 7 h 30 et 10 h) », « Pétrir à 8 h 30 », « Rabats à 9 h, 9 h 30, 10 h, 10 h 30 », « Fin du pointage quand le bocal atteint +50 % (vers 13 h, 12 h–15 h) », « Façonner », « Frigo de 14 h à 16 h 30 samedi (marge de 0 à 20 h) », « Préchauffer à 16 h 45 », « Enfourner à 17 h 30 », « Sortir à 18 h 15 », « Couper après 19 h 30 » ;
  - les actions nocturnes sont signalées ;
  - le **plan B** est indiqué : « si le levain n'est pas prêt à 8 h 30, attendre jusqu'à 10 h ; au-delà, raccourcir le frigo ».

**B-2. Des fenêtres plutôt que des points.** Le levain se présente comme « utilisable de [doublé] à [pic + ~1 h] ». Le pointage s'arrête à une cible de pousse selon la température (B9) : on vise un % de bocal, pas une heure. Le retard au froid devient une plage de 8 à 48 h, avec un avertissement de sur-apprêt si le frigo dépasse 5 °C : le verre d'eau témoin sur l'étagère, selon les forums ([TFL Tartine](https://www.thefreshloaf.com/node/71870)).

**B-3. Apprêt et cuisson modélisés.**
- Apprêt à température ambiante : critère de pousse (par exemple +25–40 % de l'aliquot après façonnage, valeur estimée) + **poke test** expliqué.
- Retard au froid : durée flexible.
- Préchauffage (45–60 min, cocotte), cuisson (40–50 min), repos (1 à 2 h) : ce ne sont que des constantes de recette à ajouter à `Proof` (ou à une nouvelle phase `bake`).

**B-4. Re-planification en direct.** Dans un batch suivi, des boutons rapides : « levain doublé maintenant », « bocal à +40 % », « pâte au frigo ».
- Chaque saisie est un relevé ou un changement d'étape. Le moteur conditionne déjà dessus (`bake.py:1-9`, `routers/prediction.py:86-104`) et les actions suivantes se décalent.
- C'est là que l'apprentissage du levain se montre : « ton levain est environ 30 % plus rapide que prévu ; la suite est avancée de 50 min ».

**B-5. Alertes.**
- Aligner les rappels du batch sur la prévision (§ 5 point 4).
- Ré-émettre le `.ics` (même UID → mise à jour : `share.js:142-143`) après chaque re-planification.
- Ensuite, Web Push pour la PWA (rien n'existe aujourd'hui côté service worker ou notifications).

**B-6. Températures variables.** Saisir « cuisine le jour / la nuit » et « frigo ». Le moteur gère déjà `TemperatureSchedule` (`prediction/model.py`) : à brancher dans `compile_plan` pour chaque phase.

**B-7. Calculateurs.**
- % boulanger (l'existant, en français, arrondi au gramme près ; précision au 0,1 g en mode Pro).
- **Température de base** : eau = k × T° visée − (T° air + T° farine + T° levain + échauffement), avec k = 3 sans préferment et 4 avec. Échauffement réglable : 6–8 °F à la main selon King Arthur, mesuré pour un pétrin. Comme la page de King Arthur est en °F, il faut convertir proprement en °C.

**B-8. Plusieurs étapes (Pro).** `Plan.levain` devient une liste de `Build`, ce qui permet de modéliser chef → tout point, les 3 rafraîchis du lievito madre et les étapes Détmold. La spec prévoit déjà un `simulate` par phase avec `y0` : il suffit d'enchaîner N phases de levain.

### 6.4 Données et modèle : réutiliser / ajouter

| Réutiliser tel quel | Ajouter |
|---|---|
| `STYLES`, `FLOURS`, `compile_plan`, `SourdoughModel`, `forecast`, `feeding_chart` (calcul empilé) | Champs éditoriaux par style (fiche § 6.2), en français et en anglais ; noms d'espèces à jour (avec les anciens noms en alias pour `ORGANISM_KINETICS`) |
| Hiérarchie d'apprentissage (spec § 6), table `batch_evidence` | **Rafraîchis de maintenance en tant que relevés** : un « batch de maintenance » léger, ou une table `culture_feedings` (heure, ratio, farine, T°, montée observée facultative). Chaque rafraîchi avec une montée relevée nourrit l'apprentissage **sans fournée**, ce qui est le meilleur moyen d'obtenir assez de données pour l'apprentissage |
| Relevés `rise` / `tta` / `ph`, changements d'étape | État du levain : `last_fed_at`, `stored: counter | fridge`, `fridge_since` sur `Culture` (ou dérivé du journal) |
| Partage et `.ics` | `Plan.levain: list[Build]` ; `Proof` avec critère de pousse ou fenêtre ; phase `bake` (préchauffage, cuisson, repos) |
| `Reminder.repeat_interval` (`models.py:134`) | Rappels de maintenance par levain (comptoir 12 h, frigo hebdomadaire), rattachés au levain et non au batch |
| `TemperatureSchedule` | Contraintes (plages interdites) et solveur à rebours ; cache par (style, ratio, T°) |
| — | Table « T° de pâte → % de pousse cible » (méthode à deux facteurs), en données sourcées |
| — | Contenu de diagnostic et de création en données (JSON) pour l'interface et un éventuel mode hors ligne |

**Calibration** (prérequis à l'honnêteté de la partie B) : ajuster les quatre paramètres de montée (`PHI_REF`, `RISE_MAX`, `LEAK0`, `LEAK_ACID`) et `WEAK_PH`/`DAMAGE_HALF_H` sur des courbes publiées : Landis 2021 (données Dryad : [doi:10.5061/dryad.0p2ngf1z1](https://datadryad.org/dataset/doi:10.5061/dryad.0p2ngf1z1)) et Romano 2007, comme le prévoit la spec § 5. Valider aussi la durée de pointage face aux tables de The Sourdough Journey. Le test xfail strict sert de garde-fou.

### 6.5 Priorisation

**Top 8, dans l'ordre :**

| # | Action | Partie | Gain | Effort |
|---|---|---|---|---|
| 1 | **Corriger les faux-amis visibles** : lecture « au pic » (`Planner.jsx:244-256`) ; « prêt pour » qui fait aussi glisser l'heure de nourrissage dans une plage (`Planner.jsx:357-418`) ; signalement des actions nocturnes ; rappels du batch alignés sur la prévision (`stages.py`/`reminders.py`) | B | Confiance au premier essai | S–M |
| 2 | **Calibrer le pic du levain et le pointage** (faire passer l'xfail ; table de pousse cible selon la T° à la place des 75 % fixes) ; en attendant, afficher le repère empirique et demander un relevé de bocal | B | Le chiffre que le boulanger vérifie en premier | M |
| 3 | **Solveur à rebours « cuire à… » sous contraintes** (`POST /sourdough/schedule`) avec liste d'actions horodatées, fenêtres, frigo comme tampon, préchauffage, cuisson et repos | B | La fonction phare de tout le marché, plus un vrai modèle derrière | M–L |
| 4 | **Accueil `#/levain` en deux parties** (A / B) + interface en français (vocabulaire du § 2.5) + garder la navigation ; « Pro » renommé « Voir la science » | A+B | Lisibilité, public francophone | S–M |
| 5 | **Journal de rafraîchis et état du levain** (« nourri il y a 9 h, pic vers 15 h 40 »), rappels de maintenance par levain, choix de l'état réel du levain à la place de mûr / frigo | A (et B) | Fidélisation quotidienne ; données d'apprentissage sans fournée | M |
| 6 | **Contenus de la partie A** : 9 fiches de type + parcours de création J1–J14 + arbre de diagnostic + « quand jeter » + explication du bocal (et pourquoi ne pas se fier au test de flottaison) | A | Répond aux questions n°1 à 4 des débutants | M (rédaction), S (code) |
| 7 | **Re-planification en direct** dans le batch suivi (boutons « levain doublé », « bocal à +X % », « au frigo ») + `.ics` mis à jour | B | Le « plan B » quand ça dérive | M |
| 8 | **Calculateurs et Pro** : température de base, convertisseur d'hydratation et de type, constructions en plusieurs étapes (chef → tout point, Détmold, lievito madre), températures jour/nuit ; types II/III rangés en « industrie » ; noms d'espèces à jour | A+B | Confirmés et artisans | M |

**Quick wins** (≤ ½ journée chacun) :
- bug « au pic » ;
- avertissement d'action nocturne ;
- renommage « Pro » ;
- arrondi au gramme ;
- types II/III déplacés ;
- repère empirique à côté de la médiane ;
- calculateur de température de base ;
- fiche « quand jeter » ;
- explication du bocal témoin ;
- rappels du batch aux p05 et p50 prévus.

**Gros chantiers :**
- calibration du sous-modèle de montée ;
- solveur à rebours avec cache et températures variables ;
- journal de levain et apprentissage depuis la maintenance ;
- constructions en plusieurs étapes ;
- Web Push ;
- traduction complète en français.

### 6.6 Risques

- **Honnêteté des prévisions.** Le calcul à rebours **amplifie** l'incertitude : une bande de 16 h sur le pic rend la plupart des plannings « infaisables ». Deux règles s'imposent :
  1. optimiser la **robustesse** (actions dans les plages autorisées pour 80–90 % des membres), pas la médiane, et toujours afficher la fenêtre et le plan B ;
  2. tant que le levain n'est pas appris, **dire** que c'est un levain « typique » et proposer un relevé de calibration dès le premier rafraîchi.
- **Ne pas sur-promettre l'apprentissage.** Il faut plusieurs batches terminés avec relevés et étapes saisies (spec § 6.1). Les rafraîchis de maintenance (action 5) sont le moyen réaliste d'y arriver.
- **Vérité scientifique et vulgarisation.** Le slogan « ferme et froid = plus acide » est faux s'il est pris au premier degré : la part acétique monte, mais l'acidité totale peut baisser. Le texte doit refléter le modèle.
- **Sécurité alimentaire.**
  - Le pH d'un levain n'est **pas** un critère de sécurité, et la spec a raison de l'exclure (spec ligne 11).
  - Le seul cas à traiter est **moisissure et traînées roses ou orange** : on jette.
  - Mention utile : ne pas goûter de pâte crue (la farine crue peut porter des pathogènes).
  - Ne pas faire tourner le moteur de règles de sécurité des lacto-fermentations sur le levain, pour éviter de reproduire le « bandeau toujours vert » de la critique.
- **Coût de calcul** sur l'instance gratuite : le solveur à rebours multiplie les calculs. Il faut des résultats empilés, un cache par (style, ratio, T°) et peut-être un substitut tabulé hors ligne, sinon le temps de réponse rend l'outil inutilisable sur mobile.
- **Marché saturé.** Sans planning à rebours ni journal, l'avantage scientifique ne se voit pas. Avec eux, FermentTrack serait la seule app qui *prévoit* au lieu d'appliquer des durées fixes.
- **Sources secondaires.** Plusieurs chiffres de ce rapport viennent de forums ou de fiches d'apps. Avant publication des fiches, revenir aux sources primaires : livres de Hamelman, Calvel et Ginsberg ; PDF de The Sourdough Journey ; Légifrance pour le décret de 1993.

---

## 7. Sources

**Forums et communautés.**
- The Fresh Loaf :
  - [Sourdough Schedule](https://www.thefreshloaf.com/comment/421358) ;
  - [Friday evening bake, 9-5](https://www.thefreshloaf.com/node/55520/help-sourdough-timings-friday-evening-bake-i-work-95) ;
  - [work schedule](https://thefreshloaf.com/comment/338468) ;
  - [Pineapple Juice Solution pt 2](https://www.thefreshloaf.com/node/10901) ;
  - [Calculating Rise Percentage](https://www.thefreshloaf.com/comment/545502) ;
  - [Two levains, why is one more sour](https://www.thefreshloaf.com/node/28219) ;
  - [warmer = more sour?](https://www.thefreshloaf.com/node/17562/warmer-fermentation-more-sour-flavour) ;
  - [too sour](https://www.thefreshloaf.com/node/71331/too-sour) ;
  - [Another Lievito Madre thread](https://www.thefreshloaf.com/node/73311/another-lievito-madre-thread) ;
  - [Panettone conversion](https://www.thefreshloaf.com/comment/478034) ;
  - [Hamelman 125 % liquid levain](https://www.thefreshloaf.com/print/67229) ;
  - [Pain au levain, stiff levain](https://www.thefreshloaf.com/node/12979/pain-au-levain-stiff-levain) ;
  - [Calvel, Taste of Bread](https://www.thefreshloaf.com/node/4006/100-sourdough-bread-taste-bread-r-calvel) ;
  - [Rye Baker maintenance](https://www.thefreshloaf.com/comment/483312) ;
  - [Feeding Rye Sour](https://www.thefreshloaf.com/node/71142/feeding-rye-sour) ;
  - [Full sour Detmolder](https://thefreshloaf.com/node/30624) ;
  - [Researching Yeast Water](https://www.thefreshloaf.com/node/74400/researching-yeast-water) ;
  - [Fruit yeast water help](https://www.thefreshloaf.com/node/56762/fruit-yeast-waterhelp-please) ;
  - [Tartine proofing](https://www.thefreshloaf.com/node/71870) ;
  - [Levain calculation](https://thefreshloaf.com/node/64600/levain-calculation) ;
  - [Friction factor](https://www.thefreshloaf.com/comment/415747).
- Reddit, via miroirs : [r/SourdoughStarter, read before posting](https://reddit.birdcat.cafe/r/SourdoughStarter/comments/1j6b6ob/read_before_posting_questions) ; r/Sourdough wiki « starter_help » (`reddit.com/r/Sourdough/wiki/starter_help`, contenu vu uniquement en extrait).

**Guides techniques.**
- King Arthur :
  - [float test](https://www.kingarthurbaking.com/blog/2019/01/02/the-float-test-for-yeast-dough-and-sourdough-starter) ;
  - [starter troubleshooting](https://www.kingarthurbaking.com/blog/2018/03/09/sourdough-starter-troubleshooting-2) ;
  - [desired dough temperature](https://www.kingarthurbaking.com/blog/2018/05/29/desired-dough-temperature) ;
  - [rye starter](https://www.kingarthurbaking.com/recipes/rye-sourdough-starter-recipe).
- The Sourdough Journey : [percentage rise](https://thesourdoughjourney.com/the-mystery-of-percentage-rise-in-bulk-fermentation/) · [dough temping](https://thesourdoughjourney.com/dough-temping-for-perfect-sourdough-fermentation/) · [timetables PDF](https://thesourdoughjourney.com/wp-content/uploads/2023/01/Bulk-Fermentation-Timetables-V1.0.pdf).
- The Perfect Loaf : [weekday sourdough](https://www.theperfectloaf.com/simple-weekday-sourdough-bread/comment-page-2/) · [starter & levain calculator](https://www.theperfectloaf.com/starter-and-levain-calculator/).
- Autres :
  - [Weekend Bakery, temperature equation](https://www.weekendbakery.com/posts/the-temperature-equation-timing-your-fermentation/) ;
  - [sourdough.co.uk calculator](https://www.sourdough.co.uk/?p=3080) ;
  - [Wordloaf DDT](https://wordloaf.substack.com/p/class-time-desired-dough-temperature) ;
  - [Amy Bakes Bread, timeline](https://amybakesbread.com/sourdough-timeline-for-beginners-how-to-fit-it-into-your-day) ;
  - Pantry Mama : [troubleshooting](https://pantrymama.com/troubleshooting-your-sourdough-starter/), [hooch](https://pantrymama.com/sourdough-starter-liquid-how-to-deal-with-sourdough-hooch/), [moldy starter](https://pantrymama.com/moldy-sourdough-starter/) ;
  - [You Knead Sourdough, float test](https://www.youkneadsourdough.com.au/blogs/faq/is-the-float-test-reliable) ;
  - [Dissapore, rinfrescare il lievito madre](https://www.dissapore.com/cucina/lievito-madre-come-rinfrescarlo/).
- France : [The Good Life France, levain chef / tout point](https://thegoodlifefrance.com/?p=114274) · [Grands Moulins de Paris, fiche technique](https://www.grandsmoulinsdeparis.com/media/fiche_technique/00422.pdf) · [Condifa, baguette au levain](https://pp.condifa.fr/fr/recettes/baguette-au-levain/?print=pdf) · Décret n° 93-1074 du 13 septembre 1993 (Légifrance ; chiffres pH ≤ 4,3 et 900 ppm d'acide acétique à vérifier).
- Allemagne (seigle) : [Pistor, Sauerteig](https://www.pistor.ch/sites/default/files/2019-04/Sauerteig_Pistor.pdf) · [Yumda, Sauerteigführung](https://www.yumda.com/de/lexikon/Sauerteigf%C3%BChrung.html).

**Science.**
- Landis et al. 2021 *eLife* 10:e61644 : [PMC7837699](https://pmc.ncbi.nlm.nih.gov/articles/PMC7837699) · [données Dryad](https://datadryad.org/dataset/doi:10.5061/dryad.0p2ngf1z1) · [NCSU](https://news.ncsu.edu/2021/01/the-sourdough-map/).
- Gänzle & Zheng 2018 *Int J Food Microbiol* : [doi:10.1016/j.ijfoodmicro.2018.08.019](https://doi.org/10.1016/j.ijfoodmicro.2018.08.019).
- [Revue Frontiers in Microbiology 2019](https://www.frontiersin.org/journals/microbiology/articles/10.3389/fmicb.2019.00201).
- [De Vero et al. 2021](https://iris.unimore.it/bitstream/11380/1243353/1/De%20Vero%20et%20al%202021%20Review%20Functional%20and%20healthy%20feautures%20of%20sourdoughs.pdf).
- *Handbook on Sourdough Biotechnology*, 2023 ([fiche](https://www.betterread.com.au/book/handbook-on-sourdough-biotechnology-book-9783031230868.do)).
- Zheng et al. 2020 *IJSEM* 70:2782 : [doi:10.1099/ijsem.0.004107](https://doi.org/10.1099/ijsem.0.004107).
- Puratos Sourdough Library : [Bakerpedia](https://bakerpedia.com/exploring-the-sourdough-library/) · [Baking Business](https://bakingbusiness.com/articles/23991-world-heritage-sourdough-library-opens) · [Puratos Center for Bread Flavour](https://www.puratos.us/en/services/center-for-bread-flavour).
- Références déjà citées par la spec (Gänzle 1998, Brandt 2004, Carbonetto 2020, Minervini 2012/2014, Kline & Sugihara 1971, De Vuyst & Neysens 2005, Romano 2007).

**Apps** (fiches éditeur : déclarations, pas mesures).
- Planning : [Bulk Planner](https://mergeek.com/latest/K5lYgAMB0DwW1wx2) · [Dough Timer](https://apps.apple.com/app/id6755980237) · [LoafLab](https://mwm.ai/apps/loaflab-sourdough-planner/6762065648) · [CrumbKeeper](https://apps.apple.com/app/id6795631667) · [Sour & Dough](https://apps.apple.com/app/id6462694910) · [Sourdough Schedule](https://appshunter.io/ios/app/sourdough-schedule-bake-timer/id6771680688) · [S.D Timer](https://apps.apple.com/il/app/s-d-timer-pro/id6760554281) · [Sourdough Timeline Generator (web)](https://granarchist.pages.dev/timeline).
- Suivi de levain : [Levain](https://apps.apple.com/app/id6780496763) · [Crumb](https://apps.apple.com/us/app/id6777510093) · [BakeReady](https://apps.apple.com/app/id6785357199) · [Sourdough Starter Tracker](https://apps.apple.com/app/id6755709217) · [The Daily Crumb](https://apps.apple.com/app/id6759510215) · [BakeIt!](https://apps.apple.com/app/id6792235598).
