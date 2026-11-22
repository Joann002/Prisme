# Analyse du benchmark Prisme

Les chiffres de la démo proviennent de 98 titres et de 150 profils synthétiques. Le NDCG@5 est moyenné par profil dans chaque domaine et par paire pour le transfert. Les résultats mélangent des tâches de difficulté différente uniquement quand la moyenne est explicitement indiquée.

## Quel modèle selon le scénario ?

| Domaine | Modèle avec historique | NDCG@5 | Meilleur modèle observé avec trois favoris | NDCG@5 |
| --- | --- | ---: | --- | ---: |
| Films | KNN item-item | 0,443 | KNN item-item | 0,347 |
| Livres | KNN item-item | 0,520 | SVD | 0,331 |
| Jeux | KNN item-item | 0,468 | SVD | 0,266 |
| Musique | KNN item-item | 0,457 | KNN item-item | 0,332 |
| Recettes | KNN item-item | 0,444 | KNN item-item | 0,339 |

Ces choix concernent le profil léger. Les profils simulés ont des thèmes dominants et couvrent une grande part d’un petit catalogue. Le KNN bénéficie de voisinages denses, surtout dans le livre. Le gain de la SVD sur les livres à trois favoris est de l’ordre de 0,001 par rapport à l’hybride. Le volume d’environ 30 utilisateurs réservés par domaine rend cet écart trop faible pour décider seul d’un déploiement. L’hybride léger est utilisé pour la démo avec favoris afin de présenter un parcours commun qui dispose de contenu même sans voisins collaboratifs.

La popularité sans historique atteint 0,159 en moyenne. Avec trois favoris, KNN atteint 0,303 contre 0,210 pour la popularité sur le même sous-ensemble. Pour les nouveaux items, TF-IDF atteint 0,015 en moyenne contre 0,000 pour la popularité. La faible valeur absolue signale que le contenu seul doit être amélioré pour faire remonter une nouveauté parmi des éléments déjà connus. Le scénario sans historique regroupe aussi des profils dont on ne dispose pas de trois favoris antérieurs. Les deux chiffres de popularité répondent donc à des questions différentes.

## Texte et transfert

Sur les paires directionnelles de domaines, la moyenne du NDCG@5 thématique passe de 0,695 avec TF-IDF à 0,790 avec l’ajout du signal collaboratif. Films → livres passe de 0,790 à 0,897 et films → musique de 0,799 à 0,927. Musique → recettes reste plus difficile, à 0,546 avec le modèle hybride. Le vocabulaire commun entre une ambiance musicale et un plat est plus ponctuel. Les adaptations et liens exacts obtiennent une moyenne de 0,969 avec les deux variantes. Des titres identiques comme Dune et Persuasion facilitent la tâche.

La correspondance des profils entre domaines est construite par la simulation. Ce gain ne peut pas être extrapolé à des corpus externes dont les identités ne sont pas alignées. Par défaut, ces corpus utilisent le contenu seul dans la recommandation entre domaines. Les thèmes de référence recoupent aussi le vocabulaire des tags rédigés pour la démo, ce qui facilite leur prédiction à partir du contenu.

## Ablations et erreurs

Sans tags, la moyenne du NDCG@5 avec historique baisse de 0,336 à 0,255 pour TF-IDF et de 0,377 à 0,358 pour l’hybride. Les catalogues de jeux, de musique et de recettes portent des genres et contextes distincts dans leurs tags. Les perdre réduit notamment les rapprochements entre fiches de formats différents. Le changement avec ou sans réordonnancement est faible en NDCG moyen, 0,377 contre 0,375 pour l’hybride. Vérifier la diversité et la part d’exposition du top 20 % permet de voir ce que la seule pertinence ne montre pas.

Une adaptation peut apparaître au milieu d’une liste quand les favoris supportent plusieurs thèmes. Un tag général comme « Voyage » rapproche parfois un trajet spatial et un déplacement familial. Entre films et recettes, les profils thématiques positifs pour les récits spatiaux peuvent produire des gâteaux ou boissons simplement nommés d’après un décor. La démo présente les tags communs pour permettre à chacun d’évaluer ce genre de proximité. De meilleurs résultats exigeraient des annotations indépendantes, des profils réels volontaires et des requêtes de référence qui distinguent adaptation, ambiance et sujet.

Optuna a réalisé dix essais sur une validation temporelle imbriquée pour les films. Le meilleur essai atteint 0,427 en validation. Les réglages de cet essai sont consignés dans le JSON et les résultats du tableau restent établis avec la configuration initiale.

- [Rapport complet du profil léger](benchmark.csv)
- [Courbes NDCG@5](ndcg.svg)
- [Résultat de la recherche Optuna](tuning-movies.json)

## Ce que changent les embeddings multilingues

Sur l’ensemble synthétique, Sentence Transformers donne un NDCG@5 moyen de 0,336, comme TF-IDF. L’hybride sémantique atteint 0,366 en moyenne contre 0,377 pour son équivalent TF-IDF. En transfert thématique, le modèle sémantique seul atteint 0,619, puis 0,739 avec les signaux collaboratifs. L’hybride TF-IDF s’en sort mieux à 0,790. Les titres et tags rédigés en français partagent souvent les mêmes mots entre domaines, ce qui aide TF-IDF. Ces résultats ne couvrent pas un transfert entre deux langues avec des vocabulaires indépendants.

Le modèle sémantique testé est paraphrase-multilingual-MiniLM-L12-v2. L’artefact de démo contient 98 vecteurs de dimension 384. Il permet de reconstruire l’index FAISS sur le catalogue correspondant. [Rapport sémantique complet](semantic/benchmark.csv) · [Courbes](semantic/ndcg.svg) · [Vecteurs de la démo](semantic/vectors.npz)

## Première mesure sur MovieLens

L’import de MovieLens Latest Small contient 9 742 films et 100 836 notes, avec 607 profils éligibles au split temporel. ALS obtient le meilleur NDCG@5 avec historique à 0,037, devant la SVD à 0,032, KNN à 0,027 et la popularité à 0,022. L’hybride TF-IDF tombe à 0,005. Les résultats sont calculés sur la totalité du catalogue éligible sans sous-échantillonnage des candidats. Le catalogue est beaucoup plus grand et plus clairsemé que la démo. Les textes de cet import sont surtout des genres et des tags communautaires. Sans enrichissement descriptif, le poids de contenu choisi pour la démo dégrade le classement réel.

Les données sont fournies par GroupLens. Référence de citation, F. Maxwell Harper et Joseph A. Konstan, *The MovieLens Datasets: History and Context*, ACM TiiS, 2015. [Source MovieLens](https://grouplens.org/datasets/movielens/) · [Résultats agrégés](movielens/benchmark.csv) · [Courbes](movielens/ndcg.svg)

## Charge locale de l’API

Le résumé final de Locust compte 381 requêtes avec 12 utilisateurs simulés en 22 secondes, un p95 agrégé de 13 ms et aucune erreur. Le dernier instantané CSV couvre les 372 requêtes enregistrées avant l’arrêt. [Statistiques Locust](charge-locust.csv)
