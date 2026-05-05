# 🛠️ Artifacts MMO - Python Async OOP Bot

## 📂 PHASE 1 : Infrastructure & API
- [ ] **1.1 Async API Client (`api/client.py`)**
    - [ ] Setup `httpx.AsyncClient` pour les requêtes non-bloquantes.
    - [ ] Décorateur `@auto_cooldown` : utilise `await asyncio.sleep(data.cooldown)`.
    - [ ] Gestion d'erreurs globale : Retry sur 5xx (serveur) et Logging sur 4xx (client).
- [ ] **1.2 Intelligence du Monde (`models/world.py`)**
    - [ ] Classe `WorldMap` : Stockage des tiles dans un dictionnaire `{(x, y): Tile}`.
    - [ ] Indexation auto : Listes dédiées pour `banks`, `monsters` et `resources`.
    - [ ] Méthode `get_nearest(start_pos, type, code)` : Calcul via Distance de Manhattan.
- [ ] **1.3 Modèles de Données (`models/data.py`)**
    - [ ] Dataclasses : `Item`, `Equipment`, `Skill`, `Bank`.
    - [ ] Classe `Inventory` : Méthode `update()`, propriété `@property is_full`.

---

## 🧱 PHASE 2 : Classe Character & Actions Modulaires
- [ ] **2.1 Le Conteneur Character (`models/character.py`)**
    - [ ] Hydratation complète des stats, skills et équipement depuis l'API.
    - [ ] **Composition** : Initialiser les modules d'actions (`self.mover`, `self.fighter`, etc.).
- [ ] **2.2 Modules d'Actions (`models/actions.py`)**
    - [ ] **Classe `BaseAction`** : Parent injectant `char`, `client` et `logger`.
    - [ ] **`MoveAction`** : `move(x, y)`, `move_to_map(id)`, `transition()`.
    - [ ] **`FightAction`** : `fight(monster_code)`, `get_result()`.
    - [ ] **`GatherAction`** : `gather()`, vérification des outils requis.
    - [ ] **`BankAction`** : `deposit_items()`, `withdraw_items()`, gestion de l'or.
    - [ ] **`GEAction`** : `buy()`, `sell()`, création d'ordres de bourse.
    - [ ] **`ManagementAction`** : `use_item()`, `equip()`, `change_skin()`.

---

## 🧠 PHASE 3 : Stratégies & Automatisation (`strategies/`)
- [ ] **3.1 Classe de base `BaseStrategy`** : Interface asynchrone `execute()`.
- [ ] **3.2 `AutoBattleStrategy`** : Cycle combat + surveillance HP + repos automatique.
- [ ] **3.3 `AutoGatherStrategy`** : Cycle récolte + détection sac plein + trajet banque.
- [ ] **3.4 `AutoCraftStrategy`** : Check inventaire/banque pour composants + craft.
- [ ] **3.5 `AutoTaskStrategy`** : Acceptation, exécution et rendu des quêtes de monstres/items.

---

## 🏎️ PHASE 4 : Orchestration Multi-Persos
- [ ] **4.1 Classe `Account` (`models/account.py`)** : Gestion du compte et banque partagée.
- [ ] **4.2 `AccountManager` (`core/manager.py`)**
    - [ ] Chargement de la configuration (YAML/JSON).
    - [ ] Orchestration : Lancement des 5 personnages via `asyncio.gather()`.
    - [ ] Gestion du "Throttling" (limite globale de requêtes par seconde).

---

## 📊 PHASE 5 : Monitoring & Persistence
- [ ] **5.1 Logging (`utils/logger.py`)** : Logs asynchrones isolés par nom de personnage.
- [ ] **5.2 Statistics Tracker** : Tracking en temps réel (XP/h, Gold/h, Loot/h).
- [ ] **5.3 Persistence (`utils/storage.py`)** : Sauvegarde SQLite pour l'historique des drops et stats.

---

## 🚀 PHASE 6 : Optimisations Avancées
- [ ] **6.1 `SmartInventoryManager`** : Comparaison de stats et auto-équipement du meilleur gear.
- [ ] **6.2 `GrandExchangeTrader`** : Analyse des tendances du marché et trading auto.
- [ ] **6.3 `WorkflowExecutor`** : Chaînes de tâches complexes (ex: Miner Fer -> Forger Lingots -> Vendre).