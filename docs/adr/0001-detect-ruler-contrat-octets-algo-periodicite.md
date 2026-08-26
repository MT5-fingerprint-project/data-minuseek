# ADR-0001 — `POST /data/api/detect-ruler` : contrat par octets, détection classique par périodicité des graduations

- **Statut** : proposé
- **Date** : 2026-08-26
- **Décideurs** : équipe data-minuseek

## Contexte

Spec **BIO-38** : une trace sans règle millimétrée n'est pas exploitable (aucune
échelle, donc aucun rapport 1:1). Le back doit refuser ces photos à l'upload
(`422 RULER_NOT_DETECTED`), indépendamment du contrôle client (défense en
profondeur). L'ADR-0010 §7 du back tranche le point d'insertion : **synchrone à
l'upload, sur les octets en clair, avant toute écriture** — ni objet GCS, ni ligne
en base tant que la règle n'est pas détectée.

Deux contraintes en découlent pour ce service :

1. **Le contrat « par IDs » de l'ADR-0007 du back ne peut pas s'appliquer** : au
   moment de l'appel, la trace n'existe nulle part — pas de `trace_id`, pas
   d'objet à relire dans le bucket.
2. **Le faux positif dangereux est l'empreinte elle-même** : une trace papillaire
   est un motif périodique quasi rectiligne par endroits. Une détection fondée
   sur la seule périodicité (Hough + FFT, pistes du ticket) la confond avec une
   règle dans ~100 % des cas sur nos scènes synthétiques.

Le ticket suivant (**D2**, calibration DPI) a besoin de l'espacement des
graduations en pixels.

## Décision

1. **Contrat par octets.** `POST /data/api/detect-ruler` reçoit l'image en
   `multipart/form-data` (champ `image`, PNG/JPEG/TIFF, ≤ 20 Mo comme le back) et un
   champ optionnel `roi` (JSON `{x, y, width, height}` normalisé : la bande de pose
   de la règle du viseur mobile, analysée en premier à résolution native).
   La variante « URL signée + grant » (ADR-0010 §6 du back) n'est **pas** exposée
   tant qu'aucune relecture depuis le bucket n'en a besoin.
2. **Data rend un verdict brut, jamais un 422.** Réponse `200` :
   `{ present, confidence, threshold, engine_version, details }`. Refuser la trace,
   accepter un override (BIO-39) ou tracer l'audit appartient au back — même
   partage des responsabilités que pour `compare` (ADR-0007). Le **seuil** vit
   côté data car il est intrinsèque à l'algorithme et à sa calibration.
3. **Algorithme classique, déterministe** (`src/services/ruler_detection.py`) :
   droites candidates (Canny + Hough) → rotation → bandes → profil 1-D → période
   et run de graduations alignées (autocorrélation) → **rapport cyclique** (traits
   fins ≠ crêtes ≈ 50 %) → **hiérarchie 1/5/10 mm** (proéminence de
   l'autocorrélation des longueurs de traits aux lags 5/10) → confiance. Les
   `details` (période, angle, nombre de traits, cohérence, rapport cyclique,
   hiérarchie) sont renvoyés pour qu'un expert puisse lire le verdict, et pour D2
   (`dpi = period_px × 25,4`).
4. **Version et calibration explicites.** `RULER_DETECTOR_VERSION`
   (`ruler-periodicity-1.0+cal.N`) suit la logique d'`ENGINE_VERSION` : elle change
   quand l'algorithme ou le seuil change. `cal.0` = seuil provisoire (0,4) issu du
   jeu synthétique ; **le passage à `cal.1` exige une calibration sur photos
   réelles** avec `scripts/evaluate_ruler_detector.py` (jeu hors repo : données
   biométriques).

## Conséquences

- ✅ Aucune écriture avant validation, aucun orphelin possible ; le contrat est
  indépendant du stockage et du chiffrement à venir.
- ✅ Verdict explicable et reproductible (pas de modèle binaire à conserver),
  ~0,3-0,6 s par photo 12 MP sur CPU, ~210 Mo de dépendances (`numpy`,
  `opencv-python-headless`), aucune lib système supplémentaire.
- ✅ La période mesurée est directement la base de D2.
- ⚠️ Le seuil 0,4 est **provisoire** (`cal.0`). Mesures : population synthétique
  adverse (règles variées / empreintes / rayures) TPR 0,90, FPR 0 ; 35 photos
  réelles Wikimedia Commons (jeu hors repo, cf. README du jeu) : 11/11 règles
  exploitables détectées, 0/15 faux positifs (empreintes révélées à la poudre,
  vitres, claviers, murs, bois), 9 cas limites rapportés à part. Tant que `cal.0`
  est en vigueur, le back doit rester en **mode ombre** (détecter et auditer sans
  refuser).
- ⚠️ Limites connues, mesurées sur photos réelles : (1) **échelles à polarité
  alternée** (traits blancs sur noir tous les cm, échelles photomacrographiques)
  et règles blanc-sur-noir — le profil de noirceur s'inverse ; correctif prévu :
  profil en magnitude de gradient, invariant à la polarité ; (2) 1 mm < 3 px
  après réduction (photo < 1536 px ou règle < 5 % de l'image sans `roi`) ;
  (3) perspective forte ou rasante, règle transparente sur fond texturé.
- ⚠️ Règles atypiques (sans hiérarchie 5/10, graduations très épaisses) et photos
  très dégradées peuvent échapper à l'approche ; un détecteur appris (YOLO/ONNX)
  reste l'option de repli, en amont (« localiser ») de cet algorithme (« mesurer »).
- ⚠️ Divergence assumée de l'ADR-0007 du back (contrat par IDs) pour cette route.

## Alternatives écartées

- **Contrat par IDs (`case_id`, `trace_id`) comme `compare`** — impossible avant
  persistance ; imposerait un statut `PENDING` et un nettoyage d'orphelins que
  l'ADR-0010 du back rejette explicitement.
- **Data renvoie directement `422 RULER_NOT_DETECTED`** — mélange verdict
  technique et règle métier ; l'override BIO-39 et l'audit sont des décisions du
  back.
- **Détecteur appris (YOLOv8n fine-tuné, ONNX Runtime)** — plus robuste aux
  variations d'apparence mais exige un jeu annoté (boîtes) contenant des
  empreintes réelles, un artefact binaire à versionner, `onnxruntime` figé en
  1.19 sous Python 3.9, et ne fournit pas l'échelle nécessaire à D2.
- **Règle à marqueur fiduciaire (ArUco)** — détection triviale et DPI offert, mais
  impose un témoin métrique spécifique aux enquêteurs : décision produit, pas
  technique.
