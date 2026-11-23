# Calendrier « Rappels Spirituels YOM » — mode d'emploi

Calendrier iCalendar suivi par abonnement (iPhone / Google Agenda) via l'URL :
`https://raw.githubusercontent.com/jpfolly/yom-calendrier/main/rappels-spirituels-yom.ics`


**Interdits absolus** : renommer le dépôt, le fichier .ics ou la branche `main` ; donner un
lien contenant un hash de commit ; changer l'`id` (UID) d'un événement existant (doublons
chez les abonnés) ; committer un jeton ou un mot de passe.

## Fichiers
- `events.yaml` : source de vérité. **Ne jamais éditer le .ics à la main.**
- `build.py` : génère `rappels-spirituels-yom.ics` (CRLF, UTF-8, pliage 75 octets, VTIMEZONE).
- `tests/test_calendar.py` : validation + non-régression contre `reference/rappels-spirituels-yom-v8.ics`.

## Commandes (Windows, Python via uv)
```
uv run --no-project --python 3.12 --with icalendar --with pyyaml --with pytest python build.py
uv run --no-project --python 3.12 --with icalendar --with pyyaml --with pytest pytest -q
```
`gh` est dans `C:\Program Files\GitHub CLI\gh.exe` si absent du PATH.

## Format d'un événement (events.yaml)
```yaml
- id: evt-AAAAMMJJ-sujet@etudes.local   # unique, jamais modifié ensuite
  titre: 'Tadabbur : Sourate Al-Fatiha'
  categorie: Tadabbur Coran
  debut: 2026-09-14 20:00               # heure de Paris
  fin: 2026-09-14 21:00
  alerte: veille 18:00                  # ou "jour_meme 09:00" ou "2026-09-13 18:00"
  alerte_texte: '...'                   # optionnel, défaut « Rappel : <titre> »
  description: '...'                    # optionnel
  dtstamp: 20260914T000000Z             # mettre l'heure UTC actuelle à chaque création/modif
# Journée entière : journee_entiere: true, du: 'AAAA-MM-JJ', au: 'AAAA-MM-JJ' (dernier jour INCLUS),
# l'alerte se calcule depuis 00:00 heure de Paris du premier jour.
```
build.py convertit l'alerte en TRIGGER relatif en heures/minutes uniquement (ex. `-PT26H`,
`PT9H`), en tenant compte de l'heure d'été. Jamais de TRIGGER absolu ni avec jours : les
alertes ne sonnaient pas sur iPhone.

## Workflow quand l'utilisateur demande d'ajouter / modifier / supprimer (en français)
1. S'il manque une info (date, heure, durée, journée entière ou non, alerte), **poser la question avant**.
2. Modifier `events.yaml` (nouvel `id` unique pour un ajout ; garder l'`id` pour une modif ;
   mettre `dtstamp` à maintenant). Si un événement de la référence v8 est modifié ou
   supprimé volontairement, ajouter son UID à `EXPECTED_CHANGES` dans le test.
3. Lancer le build puis les tests ; tout doit passer.
4. Montrer un résumé avant/après à l'utilisateur.
5. Commit au message clair en français, `git push origin main`, puis vérifier l'URL raw
   (HTTP 200 + contenu à jour ; le cache GitHub peut prendre ~5 minutes).
6. Rappeler : les téléphones se resynchronisent seuls sous quelques heures à 24 h ; sur
   iPhone, tirer l'écran vers le bas dans l'app Calendrier pour forcer.

Limite connue, à ne pas corriger : Google Agenda ignore les alertes des agendas abonnés par URL.
