# Ultimate Tic Tac Toe : Affrontement entre IA

## 1 Les r`egles du jeu

L’ultimate Tic Tac Toe est une variation combinatoire autour du jeu de Morpion d ́ej`a abord ́e en
TP. C’est un jeu `a deux joueurs en tour par tour (joueur1 avec les croix, joueur2 avec les ronds).

Il est compos ́e d’une grille de 3x3 morpions. Le vainqueur est le premier `a r ́eussir `a gagner 3 grilles
de morpions classiques elles-mˆemes align ́ees (en ligne, colonne ou en diagonale). Les d ́etails des
r`egles de l’Ultimate TicTacToe.
Le jeu est donc compos ́e d’une grille comptant 9 colonnes et 9 lignes. Si aucun des deux joueurs
n’a r ́ealis ́e un tel alignement et que tous les morpions sont complets, la partie est d ́eclar ́ee nulle.

## 2 Contraintes sur les mod`eles

Les IA devront reposer sur un Minimax avec id ́ealement un ́elagage Alpha-Beta. Vous partirez de
vos IA d ́evelopp ́ees pour le Morpion en travaux pratiques. Il est interdit d’utiliser des dictionnaires
de coups. Toute d ́ecision devra ˆetre calcul ́ee `a la vol ́ee. Pour parvenir `a am ́eliorer les IA, il n’est
pas recommand ́e de calculer tout l’arbre mais de d ́evelopper votre propre heuristique permettant
d’ ́evaluer l’int ́erˆet d’explorer une branche de l’arbre et ́eviter aussi d’explorer des branches jusqu’aux
feuilles.

### 1


## 3 Combats entre IA

Votre programme doit permettre `a un joueur d’affronter l’IA. Un affichage de la grille de jeu en
mode texte est suffisant. Pour se rep ́erer, on num ́erotera les colonnes et les lignes de 1 `a 9. Par
convention on annoncera la colonne d’abord et la ligne ensuite. Au commencement, il doit ˆetre
possible de choisir qui commence: l’IA ou le joueur. Lorsque c’est le tour du joueur, celui-ci doit
indiquer la colonne et la ligne de son choix. Lorsque c’est le tour de l’IA, celle-ci doit lancer son
mod`ele. Ensuite, la grille est mise `a jour avec le nouveau pion positionn ́e. Pour faciliter la lecture
du jeu, le choix de l’IA ou du joueur est affich ́e en plus de la grille. De cette fa ̧con, on pourra faire
s’affronter deux IA sur diff ́erentes machines (par humains interpos ́es afin de renseigner les coups de
l’autre IA).

## 4 Modalit ́es des combats

Les IA sont `a d ́evelopper par groupe de 4 ou 3 (au sein du mˆeme groupe de TP). Votre IA devra
affronter les autres IA de votre groupe de TP lors de votre derni`ere s ́eance de TP. Votre IA devra
tourner sur Google Colab^1 , il s’agit d’un environnement de d ́eveloppement dans le cloud (n ́ecessite
d’avoir une adresse gmail).
Un combat entre deux IA sera compos ́e de deux parties. Chaque IA commencera une partie `a
tour de rˆole. Une partie est finie lorsqu’une IA a r ́eussi `a aligner 3 morpions ou que la grille est
remplie. Dans le cas d’un match nul, c’est le joueur avec le plus de morpions gagn ́e qui remporte
la partie. Les parties seront chronom ́etr ́ees pour chacun des coups des IA^2. Ce point pr ́ecis n’est
pas un d ́etail. En effet, vous aurez `a g ́erer un compromis entre la qualit ́e de votre strat ́egie et
sa rapidit ́e. Il serait tentant d’adopter une strat ́egie purement d ́efensive (car il est plus facile de
pousser au nul), mais la distribution des points ci-dessous devrait vous en dissuader:

Issue d’une partie le plus rapide points r ́ecolt ́es
Victoire X 4
Victoire 7 3
Nul X 1
Nul 7 0
D ́efaite X 1
D ́efaite 7 0
A l’issue de votre derni`ere s ́eance, un compte-rendu expliquant vos choix et d ́etaillant votre
impl ́ementation ainsi que votre code seront `a d ́eposer sur DVO la veille de votre derni`ere s ́eance
de TP. L’ ́evaluation d ́ependra principalement de l’impl ́ementation du Minimax avec ́elagage Alpha-
Beta ainsi que d’un fonctionnement correct (possibilit ́e de jouer plusieurs parties sans bug) et enfin
des points r ́ecolt ́es.

```
Bon courage `a tous
```
“Que l’on me donne six heures pour couper un arbre, j’en passerai quatre `a pr ́eparer ma hache.”
Chuck Norris^3

(^1) https://colab.research.google.com
(^2) https://www.online-stopwatch.com/french/chess-timer
(^3) Citation apocryphe

### 2


