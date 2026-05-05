# Explication de l'IA Ultimate Tic-Tac-Toe

Ce document explique le raisonnement derriere l'IA utilisee dans `ultimate_tictactoe.py`.

## 1. Probleme a resoudre

L'Ultimate Tic-Tac-Toe est plus complexe qu'un morpion normal.

Dans un morpion classique, on joue sur une seule grille 3x3. Ici, on joue sur une grande grille 9x9 composee de 9 petits morpions. Quand un joueur joue dans une case locale, il envoie l'adversaire dans le morpion correspondant.

Exemple : si je joue dans la case locale en haut a droite d'un petit morpion, l'adversaire devra jouer dans le morpion en haut a droite de la grande grille.

Donc un coup a deux effets :

- il avance dans un morpion local ;
- il controle aussi le prochain endroit ou l'adversaire devra jouer.

C'est cette deuxieme partie qui rend le jeu beaucoup plus strategique.

## 2. Idee generale de l'IA

L'IA utilise un algorithme `minimax`.

Le principe est simple :

- l'IA teste ses coups possibles ;
- pour chaque coup, elle imagine la meilleure reponse de l'adversaire ;
- puis elle imagine sa reponse, etc. ;
- a la fin, elle choisit le coup qui donne le meilleur resultat dans le pire cas.

En gros, l'IA suppose que l'adversaire va jouer correctement.

La fonction principale est :

```python
minimax(board, depth, alpha, beta, maximizing, ai_player, next_macro, macro, h)
```

`depth` indique combien de coups l'IA regarde en avance. Plus la profondeur est grande, plus l'IA est forte, mais plus le calcul est long.

## 3. Pourquoi on ne peut pas tout calculer

La complexite de minimax est exponentielle.

Si on note :

- `b` = nombre moyen de coups possibles ;
- `d` = profondeur de recherche ;

alors la complexite brute est environ :

```text
O(b^d)
```

Au debut d'une partie, il peut y avoir beaucoup de coups possibles. Donc chercher toute la partie jusqu'a la fin serait trop lent.

C'est pour ca que l'IA utilise plusieurs optimisations.

## 4. Alpha-beta pruning

L'elagage alpha-beta permet d'eviter de calculer des branches inutiles.

Si l'IA voit qu'un coup est deja moins bon qu'un autre coup trouve avant, elle arrete d'explorer cette branche.

Cela ne change pas le resultat theorique du minimax, mais ca accelere beaucoup la recherche quand les bons coups sont testes en premier.

Dans le meilleur cas, alpha-beta peut se rapprocher de :

```text
O(b^(d/2))
```

Mais dans le pire cas, ca reste exponentiel.

## 5. Limite de temps et iterative deepening

L'IA ne cherche pas avec une profondeur fixe uniquement.

Elle utilise une limite de temps :

```python
TIME_LIMIT = 3.0
```

Et elle fait de l'`iterative deepening` :

1. elle cherche a profondeur 1 ;
2. puis profondeur 2 ;
3. puis profondeur 3 ;
4. etc. jusqu'a la limite de temps.

Avantage : l'IA a toujours un coup valide a jouer, meme si le temps est depasse avant une recherche plus profonde.

## 6. Evaluation d'une position

Quand la recherche arrive a la profondeur maximale, l'IA ne connait pas encore forcement le gagnant final. Elle doit donc estimer si la position est bonne ou mauvaise.

C'est le role de :

```python
evaluate(board, player, macro, next_macro, current_player)
```

Le score est positif si la position est bonne pour l'IA, negatif si elle est bonne pour l'adversaire.

L'evaluation regarde plusieurs choses.

## 7. Strategie macro

Le plus important est le plateau macro, c'est-a-dire les 9 morpions locaux vus comme une grille 3x3.

L'IA donne beaucoup de points a :

- deux morpions gagnes dans une meme ligne ;
- une menace de victoire globale ;
- le centre macro ;
- les coins macro.

Elle retire beaucoup de points si l'adversaire a une menace similaire.

Cette partie est importante parce que gagner un petit morpion ne sert vraiment que si cela aide a gagner la grande grille.

## 8. Strategie locale

L'IA evalue aussi chaque petit morpion.

Elle regarde :

- les lignes avec deux symboles et une case vide ;
- les lignes avec un symbole et deux cases vides ;
- les centres ;
- les coins ;
- les coups qui gagnent localement ;
- les forks, c'est-a-dire les positions avec plusieurs menaces en meme temps.

Mais le score local est pondere selon l'importance du morpion dans la macro.

Par exemple, un morpion qui peut donner la victoire globale vaut beaucoup plus qu'un morpion isole.

## 9. Gestion des coups dangereux

Un point tres important dans Ultimate Tic-Tac-Toe est l'endroit ou on envoie l'adversaire.

Un coup peut sembler bon localement, mais etre mauvais s'il envoie l'adversaire dans un morpion ou il peut gagner la partie.

Le code verifie donc certains risques :

- est-ce que mon coup donne une victoire macro immediate a l'adversaire ?
- est-ce que j'envoie l'adversaire dans un morpion tres dangereux ?
- est-ce que je peux forcer l'adversaire dans un morpion avantageux pour moi ?

C'est ce qui rend l'IA meilleure qu'une IA qui regarde seulement le petit morpion actuel.

## 10. Coups forces

Avant de lancer minimax, l'IA cherche certains coups evidents :

- gagner directement la partie ;
- bloquer une victoire globale adverse ;
- gagner un morpion important sans donner une reponse immediate trop dangereuse.

Ces cas sont traites a part parce qu'il n'est pas utile de passer beaucoup de temps a chercher si un coup gagne immediatement.

## 11. Ordre des coups

Alpha-beta est plus efficace si les bons coups sont testes en premier.

La fonction :

```python
_move_priority(...)
```

sert a trier les coups avant la recherche.

Elle met en avant :

- les coups qui gagnent un morpion important ;
- les coups qui bloquent une menace ;
- les coups qui creent une fork ;
- les coups qui envoient l'adversaire dans un mauvais morpion.

Ce tri ne change pas les regles du jeu, mais il aide l'IA a couper plus de branches.

## 12. Table de transposition

Pendant la recherche, l'IA peut retomber plusieurs fois sur la meme position par des ordres de coups differents.

Pour eviter de recalculer, elle utilise une table de transposition :

```python
_tt
```

Chaque plateau est identifie par un hash Zobrist. Ce hash permet de stocker rapidement :

- la profondeur deja calculee ;
- le score obtenu ;
- le meilleur coup trouve.

Cela accelere la recherche, surtout dans les positions ou plusieurs sequences menent au meme etat.

## 13. Killer moves

Les `killer moves` sont une petite optimisation supplementaire.

Si un coup provoque une coupure alpha-beta a une certaine profondeur, on le memorise. La prochaine fois qu'on arrive a la meme profondeur, on teste ce coup plus tot.

L'idee est qu'un coup fort dans une branche peut souvent etre fort dans une autre branche similaire.

## 14. Ce qui a ete ajoute par rapport a un minimax simple

Par rapport a une IA minimax basique, cette version ajoute :

- alpha-beta ;
- limite de temps ;
- iterative deepening ;
- table de transposition ;
- killer moves ;
- tri des coups ;
- heuristique locale ;
- heuristique macro ;
- detection de coups forces ;
- detection des coups qui donnent une grosse opportunite a l'adversaire.

Donc ce n'est pas juste un minimax simple. C'est un minimax optimise pour que le jeu reste jouable en console.

## 15. Limites de l'IA

L'IA n'est pas parfaite.

Ses limites principales :

- elle ne peut pas explorer toute la partie ;
- les valeurs de l'heuristique sont choisies a la main ;
- certains coups tres profonds peuvent lui echapper ;
- elle recopie encore beaucoup le plateau, donc elle pourrait etre plus rapide.

Mais pour un projet de jeu console, elle est deja assez solide : elle tient compte des menaces locales, des objectifs macro et de l'endroit ou elle envoie l'adversaire.

## 16. Resume court pour la revue de code

L'IA utilise minimax pour simuler les coups futurs. Comme le jeu est trop grand pour tout calculer, on limite la recherche avec un budget temps. Alpha-beta coupe les branches inutiles. L'evaluation donne un score a une position en regardant les menaces locales, les menaces globales et le morpion impose au prochain joueur. La table de transposition et les killer moves servent a accelerer la recherche. Le but est d'avoir une IA assez forte sans bloquer la console pendant trop longtemps.
