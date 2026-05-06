# Compte rendu - Ultimate Tic-Tac-Toe

## 1. Objectif du projet

Le but du projet etait de developper une IA capable de jouer a l'Ultimate Tic-Tac-Toe, puis de la faire affronter d'autres IA. Le sujet imposait une base de type Minimax, idealement avec elagage alpha-beta, sans dictionnaire de coups predefinis. Chaque decision devait donc etre calculee pendant la partie.

Notre programme permet de jouer en console contre l'IA, avec une grille 9x9 lisible, la gestion de la contrainte du prochain morpion, le choix du joueur qui commence, et un mode IA contre IA utile pour tester rapidement plusieurs parties.

## 2. Regles prises en compte

L'Ultimate Tic-Tac-Toe est compose de neuf morpions locaux 3x3 organises dans une grille macro 3x3. Un coup est defini par une ligne et une colonne sur la grande grille. La position locale du coup impose le morpion dans lequel l'adversaire devra jouer au tour suivant.

Exemple : si un joueur joue dans la case locale en haut a droite d'un petit morpion, l'adversaire est envoye dans le morpion macro en haut a droite.

Cette contrainte est essentielle : un bon coup ne doit pas seulement ameliorer notre position locale, il doit aussi eviter d'envoyer l'adversaire vers une position trop favorable.

## 3. Architecture generale

Le projet est principalement contenu dans `ultimate_tictactoe.py`.

Les elements importants sont :

- une representation du plateau 9x9 ;
- une grille macro 3x3 indiquant les petits morpions gagnes ;
- une contrainte `next_macro` indiquant le petit morpion impose au joueur suivant ;
- une IA basee sur Minimax avec elagage alpha-beta ;
- une limite de temps par coup avec approfondissement iteratif ;
- une evaluation heuristique pour estimer les positions non terminales ;
- des optimisations de recherche : table de transposition, hash Zobrist, tri des coups, killer moves, history heuristic et quiescence search ;
- des fonctions d'affichage et de boucle de jeu en console.

Une specificite importante est la presence d'une classe `GameState`. Elle permet de manipuler l'etat de jeu avec des operations `make_move` et `unmake_move`, au lieu de recopier tout le plateau a chaque noeud de recherche. C'est utile car Minimax explore beaucoup de positions : reduire le cout d'un coup simule permet d'atteindre une profondeur plus grande dans le meme temps.

## 4. Algorithme de recherche

L'IA utilise un Minimax : elle simule ses coups, puis les meilleures reponses adverses, puis ses propres reponses. Le score obtenu est ensuite remonte dans l'arbre pour choisir le meilleur coup.

Comme l'arbre de jeu est trop grand pour etre explore entierement, nous utilisons l'elagage alpha-beta. Il permet d'arreter l'exploration d'une branche lorsqu'on sait deja qu'elle ne pourra pas donner un meilleur resultat que ce qui a ete trouve ailleurs. L'efficacite de l'alpha-beta depend beaucoup de l'ordre dans lequel les coups sont testes.

La limite principale de la recherche est le temps, pas une profondeur fixe. Le code contient bien une constante `MAX_DEPTH = 20`, mais elle sert surtout de plafond de securite. En pratique, l'IA utilise un budget temps (`TIME_LIMIT = 3.0` secondes par defaut) et de l'approfondissement iteratif : elle cherche d'abord a profondeur 1, puis 2, puis 3, etc., jusqu'a ce que le temps disponible soit presque atteint. Ainsi, meme si le temps est atteint pendant une recherche profonde, elle conserve le meilleur coup trouve a la profondeur precedente.

Ce choix est important pour les combats entre IA, car le sujet insiste sur le compromis entre qualite de strategie et rapidite. Une profondeur fixe serait moins adaptee : certaines positions ont peu de coups possibles et peuvent etre explorees plus profondement, alors que d'autres positions sont tres ouvertes et doivent s'arreter plus tot pour respecter le temps par coup.

## 5. Evaluation heuristique

Lorsque la recherche ne peut pas aller jusqu'a la fin de la partie, l'IA doit estimer la qualite d'une position. Notre evaluation separe volontairement plusieurs niveaux.

### Evaluation macro

La grille macro est prioritaire, car gagner un petit morpion n'est utile que s'il aide a aligner trois morpions locaux. L'IA valorise donc :

- les morpions locaux deja gagnes ;
- les lignes macro avec deux morpions gagnes et une case libre ;
- les menaces de victoire globale ;
- le centre et les coins macro, souvent plus utiles strategiquement ;
- les forks macro, c'est-a-dire les positions creant plusieurs menaces simultanees.

Les menaces adverses sont penalisees plus fortement que les menaces propres ne sont recompensees. Ce choix est volontaire : ne pas bloquer une victoire macro adverse est souvent decisif.

### Evaluation locale

Chaque petit morpion est aussi evalue. L'IA tient compte :

- des lignes locales avec deux pions et une case vide ;
- des opportunites de blocage ;
- du controle du centre et des coins ;
- de l'importance du morpion local dans la grille macro.

Le score local reste plus faible que le score macro, car l'objectif final est de gagner la grande grille.

### Evaluation du flux

Une specificite de notre IA est de prendre en compte l'endroit ou le coup envoie l'adversaire. Un coup localement interessant peut etre mauvais s'il donne a l'adversaire un morpion dans lequel il peut gagner ou creer une menace globale.

Cette notion de "flux" est importante dans l'Ultimate Tic-Tac-Toe. Elle permet a l'IA de ne pas jouer comme si les neuf morpions etaient independants.

### Ponderation des scores

L'heuristique fonctionne avec un systeme de bonus et de malus. Le score final est positif si la position est favorable a l'IA, negatif si elle est favorable a l'adversaire.

Les poids ont ete choisis de maniere logique puis ajustes empiriquement : nous avons fait jouer l'IA contre elle-meme, observe les mauvais coups, puis modifie les valeurs pour mieux bloquer les menaces et mieux valoriser les positions vraiment decisives.

Les valeurs les plus fortes concernent la victoire globale : une victoire macro vaut environ `+100000`, et une defaite `-100000`. Ensuite viennent les menaces macro, car elles peuvent directement decider la partie. Par exemple, avoir deux morpions alignes avec une case libre donne un bonus important (`+5000`), alors que laisser la meme menace a l'adversaire donne un malus encore plus fort (`-7000`). Cette asymetrie pousse l'IA a bloquer les menaces dangereuses au lieu de seulement attaquer.

Les forks macro sont aussi pris en compte : creer plusieurs menaces en meme temps donne un bonus, tandis que laisser cette possibilite a l'adversaire donne un malus. Ensuite, l'IA ajoute des bonus plus faibles pour le controle du centre macro, des coins et des bords. Le centre est mieux valorise, car il participe a plus d'alignements possibles.

Au niveau local, les valeurs sont volontairement plus petites : gagner un petit morpion, creer une ligne locale avec deux pions, occuper le centre ou un coin donnent des bonus, mais ils restent moins importants que les objectifs macro. Cela evite que l'IA gagne un petit morpion inutile tout en laissant une menace globale.

Enfin, la mobilite ajoute un petit score selon le nombre de coups disponibles dans le morpion impose. Avoir plus de choix est favorable, alors qu'envoyer l'adversaire dans un morpion avec beaucoup de bonnes options peut devenir dangereux. L'idee generale est donc : priorite a la victoire globale, puis aux menaces macro, puis seulement aux avantages locaux.

## 6. Optimisations implementees

### Hash Zobrist et table de transposition

La table de transposition memorise des positions deja analysees afin de ne pas les recalculer. Chaque etat est identifie par un hash Zobrist, c'est-a-dire une valeur numerique qui represente rapidement la position.

Le principe est le suivant : au lancement du programme, on genere des grands nombres aleatoires pour chaque possibilite importante du jeu, par exemple "un X sur telle case", "un O sur telle case", "tel morpion impose au prochain tour" ou encore "c'est au tour de tel joueur".

Conceptuellement, le hash represente donc une sorte de signature construite a partir de plusieurs informations :

- le contenu du plateau 9x9 ;
- le joueur qui doit jouer ;
- la contrainte du prochain morpion (`next_macro`).

On pourrait imaginer concatener toutes ces informations pour former une grande cle, mais ce serait plus lourd a manipuler. Le hash Zobrist fait l'equivalent de maniere plus efficace : il combine les valeurs aleatoires correspondant aux elements presents avec l'operation XOR, notee `^` en Python. Par exemple, si une case contient un `X`, on ajoute au hash la valeur aleatoire associee a "X sur cette case". Si le prochain joueur est contraint dans un certain morpion, on ajoute aussi la valeur associee a cette contrainte.

L'interet du XOR est qu'il est tres rapide et reversible : appliquer deux fois le meme `^` annule l'effet. Cela permet de mettre a jour le hash pendant la recherche sans tout recalculer. Quand l'IA simule un coup avec `make_move`, elle modifie seulement les parties du hash concernees par ce coup. Quand elle annule le coup avec `unmake_move`, elle reapplique les memes valeurs pour revenir au hash precedent. Cela reduit le temps de calcul, car le Minimax explore beaucoup de positions.

Quand le Minimax retombe sur une position deja vue, cette cle permet de retrouver directement le score calcule auparavant dans la table de transposition, au lieu de reexplorer toute la branche.

Un probleme de la premiere version etait que le hash ne dependait que des pions du plateau. Deux positions avec les memes pions, mais avec un joueur courant different ou une contrainte `next_macro` differente, pouvaient donc etre confondues. C'etait critique, car la table pouvait renvoyer un score faux.

La version actuelle integre :

- les pions du plateau ;
- le joueur a qui c'est le tour ;
- la contrainte du prochain morpion.

La table devient donc beaucoup plus fiable.

### Tri des coups

Avant d'explorer les coups, l'IA les trie pour tester les plus prometteurs en premier. Cela ameliore fortement l'alpha-beta.

Les coups prioritaires sont par exemple :

- les coups qui gagnent un petit morpion ;
- les coups qui bloquent une menace ;
- les coups qui ameliorent la position macro ;
- les coups qui envoient l'adversaire dans un morpion defavorable ;
- les coups deja identifies comme forts par la table de transposition.

### Killer moves et history heuristic

Les killer moves memorisent les coups qui ont provoque une coupure alpha-beta a une certaine profondeur. Si un coup a deja permis de couper une branche, il est souvent utile de le tester tot dans une autre branche similaire.

La history heuristic complete ce mecanisme en donnant un score aux coups qui provoquent souvent des coupures. Cela rend le tri des coups plus adaptatif pendant la recherche.

### Quiescence search

Un probleme classique de Minimax est l'effet d'horizon : l'IA peut s'arreter juste avant une sequence tactique importante et evaluer une position comme bonne alors qu'elle devient mauvaise au coup suivant. Cela arrive surtout quand la profondeur limite tombe au milieu d'un echange de menaces.

Pour limiter ce probleme, nous avons ajoute une quiescence search limitee (`QUIESCENCE_MAX = 2`). Quand la recherche normale arrive a sa limite, l'IA ne s'arrete pas toujours immediatement : si la position contient encore des coups tactiques importants, comme gagner un petit morpion ou bloquer un petit morpion adverse, elle prolonge un peu l'analyse uniquement sur ces coups.

Exemple : l'IA peut voir un coup qui gagne un morpion local et donc semble tres bon. Mais ce coup peut envoyer l'adversaire dans un autre morpion ou il gagne lui aussi, voire cree une menace macro plus dangereuse. Sans quiescence, l'IA risque de s'arreter juste apres son gain local et de surevaluer ce coup. Avec la quiescence search, elle regarde encore la reponse tactique immediate de l'adversaire avant de donner le score final.

Le but n'est pas d'explorer toute la suite de la partie. On prolonge seulement les positions "instables", c'est-a-dire celles ou un coup tactique important vient d'apparaitre. Cela garde un temps de calcul raisonnable tout en evitant certaines evaluations trop brutales.

### Coups forces

Avant de lancer toute la recherche, l'IA verifie certains cas evidents :

- victoire macro immediate ;
- blocage d'une victoire macro adverse ;
- coups locaux tres importants lorsqu'ils ne donnent pas une reponse immediate trop dangereuse.

Cela evite de gaspiller du temps sur des situations ou le meilleur coup est deja clair.

## 7. Problemes rencontres et corrections

Pendant le developpement, plusieurs problemes importants ont ete identifies dans les premieres versions de l'IA.

Le premier probleme etait une heuristique trop locale. L'IA regardait surtout les petits morpions, sans assez tenir compte de la grande grille et du morpion impose au tour suivant. Nous avons donc ajoute une evaluation macro plus forte et une prise en compte explicite du flux.

Le deuxieme probleme etait la mauvaise modelisation de l'envoi de l'adversaire. Dans Ultimate Tic-Tac-Toe, un coup a toujours deux consequences : il place un pion et il controle le prochain terrain de jeu. Nous avons donc ajoute des penalites pour les coups qui envoient l'adversaire vers un morpion dangereux ou lui donnent trop de liberte.

Le troisieme probleme etait le hash incomplet de la table de transposition. Cette erreur etait silencieuse mais grave, car elle pouvait faire reutiliser une evaluation correspondant a une autre situation. Le hash a ete complete avec `side` et `next_macro`.

Le quatrieme probleme etait la profondeur de recherche trop faible en pratique. Meme si une profondeur maximale elevee etait indiquee, ce n'etait pas elle qui determinait reellement la recherche : la vraie limite etait le temps disponible par coup. Les copies de plateau et les recalculs consommaient ce temps trop vite, donc l'IA atteignait une profondeur effective faible. L'utilisation de `GameState`, de `make_move/unmake_move` et de mises a jour incrementales a reduit ce cout, ce qui permet d'aller plus profond dans le meme budget temps.

Le cinquieme probleme etait l'absence de stabilisation tactique a la profondeur limite. La quiescence search a ete ajoutee pour limiter les evaluations trop optimistes ou trop pessimistes au milieu d'une sequence de menaces.

Enfin, les ponderations heuristiques etaient trop arbitraires. Elles ont ete restructurees pour donner une priorite claire : victoire globale, menaces macro, controle macro, puis seulement ensuite avantages locaux.

## 8. Compromis choisis

Le sujet imposait l'utilisation d'un Minimax, idealement avec elagage alpha-beta. Nous n'avions donc pas pour objectif de remplacer cette approche par un autre algorithme comme MCTS. Les compromis ont plutot porte sur la maniere de rendre le Minimax assez rapide et assez pertinent pour l'Ultimate Tic-Tac-Toe.

Nous n'avons pas utilise de dictionnaire de coups. Toutes les decisions sont calculees a partir de l'etat courant.

Nous n'avons pas non plus converti tout le moteur en bitboards. Cette representation serait plus rapide, mais elle aurait rendu le code moins lisible. Le gain principal venait deja de la suppression des copies de plateau et de l'amelioration de l'ordre des coups.

Nous avons aussi evite d'ajouter trop d'optimisations avancees difficiles a expliquer, comme des variantes plus complexes de recherche. Le choix general a ete de rester dans le cadre impose par le projet : un Minimax alpha-beta, optimise avec une bonne heuristique, une limite de temps, une table de transposition et un tri efficace des coups.

## 9. Validation

Plusieurs verifications ont ete effectuees :

- parties IA contre IA ;
- parties contre joueur aleatoire ;
- verification que l'IA respecte la contrainte du morpion impose ;
- verification que le programme peut enchainer plusieurs parties ;
- tests de compilation Python ;
- observation des coups choisis et des logs de partie.

D'apres nos essais, la nouvelle version gagne nettement contre l'ancienne IA et reste stable dans les parties automatiques. Les logs indiquent aussi que l'IA atteint une profondeur plus interessante qu'avant, grace aux optimisations de recherche.

## 10. Limites et ameliorations possibles

L'IA n'est pas parfaite. Elle reste limitee par le temps de calcul et par une heuristique choisie manuellement. Certains plans tres profonds peuvent encore lui echapper.

Des ameliorations possibles seraient :

- faire davantage de parties de test contre d'autres IA pour ajuster les poids de l'heuristique ;
- adapter un peu mieux le temps de reflexion selon la position, par exemple jouer plus vite les coups evidents ;
- comparer notre approche avec un autre type d'IA, comme Monte Carlo, car nous avons vu que certaines IA d'Ultimate Tic-Tac-Toe utilisent cette methode. Cela resterait cependant une piste hors du cadre principal du sujet, qui imposait Minimax.

## 11. Vocabulaire

- **Grille locale** : un petit morpion 3x3.
- **Grille macro** : la grande grille 3x3 composee des 9 morpions locaux. Une case macro correspond donc a un petit morpion.
- **Victoire macro** : victoire globale obtenue en alignant trois morpions locaux gagnes.
- **`next_macro`** : contrainte indiquant dans quel morpion local le prochain joueur doit jouer.
- **Flux** : effet d'un coup sur le prochain morpion impose a l'adversaire.
- **Heuristique** : fonction qui donne un score a une position quand l'IA ne peut pas calculer toute la partie jusqu'a la fin.
- **Minimax** : algorithme qui simule les coups de l'IA et les meilleures reponses adverses pour choisir le meilleur coup possible.
- **Elagage alpha-beta** : optimisation de Minimax qui evite d'explorer des branches inutiles.
- **Approfondissement iteratif** : recherche a profondeur 1, puis 2, puis 3, etc., jusqu'a atteindre la limite de temps.
- **Table de transposition** : memoire des positions deja analysees pour eviter de refaire les memes calculs.
- **Hash Zobrist** : cle numerique qui represente rapidement un etat de jeu complet.
- **Fork** : situation ou un joueur cree plusieurs menaces en meme temps.
- **Quiescence search** : prolongement court de la recherche sur les coups tactiques pour eviter d'evaluer une position instable.
- **Killer move** : coup qui a deja permis de couper une branche de recherche et qui sera teste plus tot ensuite.

## 12. Conclusion

Le projet respecte les contraintes principales du sujet : l'IA repose sur Minimax, utilise l'elagage alpha-beta, ne depend pas d'un dictionnaire de coups et peut jouer des parties completes en console.

La principale difficulte n'a pas ete seulement de gagner des petits morpions, mais de modeliser correctement le flux de l'Ultimate Tic-Tac-Toe : chaque coup doit etre juge selon son effet local, son impact macro et le morpion donne a l'adversaire. C'est cette prise en compte du flux, combinee aux optimisations de recherche, qui constitue la specificite la plus utile de notre implementation.
