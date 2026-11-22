# Fiches des modèles

Les modèles classent des éléments selon un signal de préférence observé ou explicite. Les scores sont normalisés par requête et servent à ordonner les résultats. Un score de 0,8 ne représente pas une probabilité d’appréciation.

| Modèle | Entraînement et usage prévu | Limites et biais |
| --- | --- | --- |
| Aléatoire | Graine stable, utile comme contrôle. | Ignore les goûts et les métadonnées. |
| Popularité | Rang par nombre de profils positifs, compression logarithmique. Adapté à une session sans profil initial. | Favorise les éléments déjà exposés. Peu informatif pour les nouveautés. |
| Contenu TF-IDF | Uni-grammes et bi-grammes sur titres, textes et tags. Cosinus avec le profil des favoris. | Lexique et langues différents réduisent le recouvrement. Dépend de la qualité rédactionnelle et de la richesse du catalogue. |
| Voisins item-item | Cosinus entre colonnes de la matrice utilisateur–élément, pondérées par le signal positif. | Voisins instables sur la longue traîne. Une équipe doit vérifier la densité du domaine. |
| SVD | Factorisation tronquée, rang piloté par YAML. Les favoris construisent un profil latent pour un nouvel utilisateur. | Les signaux rares disparaissent dans les facteurs dominants. |
| ALS | Factorisation implicite avec `implicit`, confiance positive et régularisation. | Sensible à la régularisation et à la popularité. Les interactions absentes sont des inconnues. |
| Hybride | Somme de scores normalisés de contenu et collaboratifs. Le poids du contenu est configurable. | Les distributions changent selon le domaine. Un poids appris sur la démo peut moins bien fonctionner sur une autre population. |
| Contenu sémantique | Sentence Transformers multilingue sur les textes, puis cosinus via FAISS. | Le modèle fixe peut mal représenter les titres rares, noms propres ou vocabulaires très techniques. |
| Hybride sémantique | Remplace le score TF-IDF de l’hybride par la proximité sémantique. | Hérite des biais du corpus du modèle d’embeddings et du catalogue local. |

Les explications montrent le favori le plus proche selon le contenu et mentionnent des tags communs lorsque disponibles. Pour une méthode collaborative, elles fournissent un repère descriptif. La diversification pénalise ensuite la répétition des mêmes tags avec une distance de Jaccard.

Le modèle sémantique par défaut est le suivant. [paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
