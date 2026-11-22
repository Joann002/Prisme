# Ajouter un domaine

1. Crée `src/reco_platform/domains/exemple.py` avec un adaptateur héritant de `DomainAdapter`.
2. Ajoute `src/reco_platform/configs/exemple.yaml`, avec `slug`, `label`, `singular`, `icon`, `adapter`, `source` et la liste `models`. Reprends les seuils et paramètres d’un domaine voisin puis ajuste `positive` à l’échelle du signal.
3. Prépare les sources dans `data/raw/exemple` et lance `uv run --no-sync reco-platform ingest exemple data/raw/exemple`.
4. Relance l’API, la démo et le benchmark. La configuration est découverte au démarrage. `RECO_CONFIG_DIR` permet également d’utiliser un répertoire de YAML externe.

```python
from reco_platform.domains.base import Dataset, DomainAdapter, csv

class ExempleAdapter(DomainAdapter):
    def read(self, root):
        items = csv(root, "catalogue.csv", dtype={"item_id": str})
        events = csv(root, "interactions.csv", dtype={"item_id": str, "user_id": str})
        return Dataset(self.items(items), events)
```

Le catalogue contient `item_id, titre, description, tags, domaine`. Les tags sont séparés par des virgules. Une année et une URL d’image HTTPS peuvent être fournies. Les interactions contiennent `user_id, item_id, timestamp, feedback`. Utilise des dates ISO ou des dates Unix. Lorsque la source fournit uniquement des agrégats sans date, renvoie `Dataset(..., temporal=False)` et documente l’absence de dates.

Utilise `RECO_SHARED_USERS=1` uniquement si une convention de clés commune a été établie entre tous les imports et si leur traitement est autorisé. Par défaut les jeux externes restent indépendants. L’espace de contenu partagé est disponible quelle que soit la source.
