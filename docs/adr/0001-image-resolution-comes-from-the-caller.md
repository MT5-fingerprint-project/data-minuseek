# ADR-0001 — La résolution des images vient de l'appelant

- **Statut** : accepté
- **Date** : 2026-09-01

## Contexte

`search()` déclarait `dpi: int = 500` pour toutes les images. SourceAFIS travaille en interne à
500 points par pouce et redimensionne l'entrée d'un facteur 500/dpi : déclarer 500 sur une
photographie macro revient à lui dire qu'une image de 6000 × 4000 est une empreinte de trente
centimètres de large. Il ne réduit rien et cherche des crêtes à une échelle cinq fois trop grande.

Mesuré sur les images du dossier `62342af6` : l'extraction d'une empreinte de 10,9 Mpx prend 14,2 s
à 500 dpi déclarés, 0,6 s à sa résolution réelle, pour un template rigoureusement identique de
1,3 ko. Les quatre comparaisons enregistrées le 28 août ont pris entre 50 et 60 secondes, contre un
proxy Cloudflare qui coupe à cent.

Les deux images de ce dossier ne sont pas à la même échelle, à un facteur 2,6 près : aucune
constante unique ne peut être juste pour les deux. Le back mesure déjà cette valeur image par image
depuis L5-4 et la persiste dans `Trace.resolutionDpi` et `ReferencePrint.resolutionDpi`.

## Décision

`POST /data/api/compare` exige une résolution pour la trace et une pour chaque empreinte de
référence, bornées entre 50 et 10 000 comme le VO `ImageResolution` du back. La valeur descend
jusqu'à `FingerprintImageOptions.dpi()` dans le même tuple que les octets de l'image. Le service
n'a plus de valeur de repli : une résolution absente est un 422.

`ENGINE_PARAMETERIZATION` passe de `"1"` à `"2"`, donc `ENGINE_VERSION` vaut désormais
`sourceafis-3.17.1+minuseek.2`.

## Conséquences

- ✅ Une comparaison sur un dossier réel passe de cinquante secondes à quelques secondes, sans rien
  perdre : le template extrait est identique.
- ✅ Un score est produit à l'échelle réelle des images, donc il veut dire quelque chose.
- ⚠️ Les scores produits sous `+minuseek.1` ne sont pas comparables aux suivants. Les `Matching`
  déjà en base sont purgés plutôt que rendus compatibles : aucun tenant réel n'existe.
- ⚠️ Le contrat de la route change sans période de recouvrement. Entre le déploiement de data et
  celui du back, l'analyse répond 422 et le front affiche « Le service de comparaison est
  indisponible » — les deux se fusionnent le même jour.
- ⚠️ `MATCH_THRESHOLD = 40`, côté back, n'est calibré contre rien et l'est encore moins maintenant
  que la distribution des scores se déplace. À instruire séparément.

## Alternatives écartées

- **Déduire la résolution de l'image elle-même** (métadonnées EXIF, détection de la règle
  millimétrée) — les photographies de scène ne portent pas de résolution fiable, et la détection
  automatique de la règle est un chantier à part. L'opérateur mesure, l'outil existe depuis L5-4.
- **Garder 500 comme repli quand la résolution manque** — un repli produit un score plausible et
  faux, qu'un rapport citerait. L'absence doit être un refus.
- **Redimensionner les images stockées à une résolution unique** — l'image est la pièce, elle ne se
  réécrit pas. Déclarer sa résolution produit exactement le même redimensionnement, en mémoire.
