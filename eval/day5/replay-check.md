# Vérification du replay déployé (RPL-T9)

Date : 4 nov. 2026. URL : https://wondrous-tiramisu-404f0a.netlify.app/ (hébergement : `RPL-D8`).

## Contrôles automatiques, sans connexion

- `replay/deploy_check.py` sur le dossier publié : « site publiable ».
- 23 fichiers en ligne, en HTTP 200. Les 4 vidéos répondent aussi par morceaux (HTTP 206, `video/mp4`).
- 21 fichiers identiques octet par octet au dossier contrôlé. `index.html` et `replay.html` ne diffèrent que par ce
  que Netlify y ajoute : un commentaire HTML et son script de badge (« Powered by Netlify »).
- Page ouverte dans Edge sans fenêtre : bandeau, sessions, contours, courbe et frise chargés. La vidéo y reste noire :
  ce contrôle ne prouve donc pas sa lecture.

## Dernier dépôt (4 nov., vers 14 h 50)

Même contrôle sur la version finale : session A en premier, voix corrigée (`RPL-T12`), lien de la vidéo. 21 fichiers
identiques au dossier contrôlé, `index.html` et `replay.html` modifiés par Netlify seulement, 4 vidéos servies par morceaux
(HTTP 206). L'écoute de la voix corrigée reste à l'auteur.

## Essai de l'auteur, sur la version précédente

Lecture sur ordinateur en navigation privée et sur téléphone en 4G, sur les 4 sessions : vidéo, contours et refus
vers 10 s de la session « C'est fait » refusé. Résultat donné par l'auteur : « Tout est bon ».

## Non mesuré

- Temps d'affichage de la première image (`RPL-R1.2`, cible de moins de 5 s) : non noté.
- Navigateurs utilisés : non précisés. Chrome, Firefox et Safari (`RPL-R1.3`) ne sont donc pas établis un par un.
