#!/usr/bin/env python3
"""
Ultimate Tic-Tac-Toe avec IA Minimax + Elagage Alpha-Beta
==========================================================
Regles :
  - Grille 9x9 composee de 9 morpions 3x3.
  - Gagner 3 morpions alignes (ligne, colonne ou diagonale) = victoire.
  - Apres un coup en position locale (lr, lc), l'adversaire doit jouer
    dans le morpion macro (lr, lc). Si ce morpion est gagne ou plein,
    l'adversaire joue ou il veut.
  - Si tous les morpions sont termines sans alignement de 3, le joueur
    ayant gagne le plus de morpions remporte la partie.

Coordonnees : colonne d'abord, ligne ensuite (1-9).
"""

import math
import time
import os
import sys

# Force UTF-8 pour les caracteres de boite (Windows CMD)
if os.name == 'nt':
    os.system('chcp 65001 > nul')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

EMPTY = 0
X = 1   # Joueur 1 / croix
O = 2   # Joueur 2 / ronds

SYMBOL = {EMPTY: '.', X: 'X', O: 'O'}

# Profondeur de recherche par defaut
DEFAULT_DEPTH = 4

# ---------------------------------------------------------------------------
# Representation du plateau
# ---------------------------------------------------------------------------

def create_board():
    """Cree un plateau 9x9 vide."""
    return [[EMPTY] * 9 for _ in range(9)]


def get_macro_pos(row, col):
    """Indice du morpion macro (mr, mc) a partir d'une position globale."""
    return row // 3, col // 3


def get_local_pos(row, col):
    """Position locale (lr, lc) dans le morpion macro."""
    return row % 3, col % 3


# ---------------------------------------------------------------------------
# Verification des gagnants
# ---------------------------------------------------------------------------

LINES_3x3 = [
    [(0,0),(0,1),(0,2)],
    [(1,0),(1,1),(1,2)],
    [(2,0),(2,1),(2,2)],
    [(0,0),(1,0),(2,0)],
    [(0,1),(1,1),(2,1)],
    [(0,2),(1,2),(2,2)],
    [(0,0),(1,1),(2,2)],
    [(0,2),(1,1),(2,0)],
]


def check_winner_3x3(cells):
    """Retourne le gagnant d'une grille 3x3 (liste 3x3), ou EMPTY."""
    for line in LINES_3x3:
        a, b, c = [cells[r][col] for r, col in line]
        if a != EMPTY and a == b == c:
            return a
    return EMPTY


def compute_macro(board):
    """Calcule l'etat 3x3 des morpions locaux."""
    macro = [[EMPTY] * 3 for _ in range(3)]
    for mr in range(3):
        for mc in range(3):
            cells = [[board[mr*3+r][mc*3+c] for c in range(3)] for r in range(3)]
            macro[mr][mc] = check_winner_3x3(cells)
    return macro


def is_local_full(board, mr, mc):
    """Vrai si le morpion local (mr, mc) est completement rempli."""
    for r in range(3):
        for c in range(3):
            if board[mr*3+r][mc*3+c] == EMPTY:
                return False
    return True


def is_local_available(board, macro, mr, mc):
    """Vrai si le morpion local est jouable (pas gagne et pas plein)."""
    return macro[mr][mc] == EMPTY and not is_local_full(board, mr, mc)


# ---------------------------------------------------------------------------
# Coups valides
# ---------------------------------------------------------------------------

def get_valid_moves(board, next_macro, macro=None):
    """
    Retourne la liste des coups valides (row, col) en index 0-base.
    next_macro : (mr, mc) si contraint, None si libre.
    """
    if macro is None:
        macro = compute_macro(board)

    moves = []

    def add_moves_for(mr, mc):
        if not is_local_available(board, macro, mr, mc):
            return
        for r in range(3):
            for c in range(3):
                if board[mr*3+r][mc*3+c] == EMPTY:
                    moves.append((mr*3+r, mc*3+c))

    if next_macro is not None:
        mr, mc = next_macro
        if is_local_available(board, macro, mr, mc):
            add_moves_for(mr, mc)
            return moves
        # Le morpion contraint est indisponible -> libre
    for mr in range(3):
        for mc in range(3):
            add_moves_for(mr, mc)
    return moves


def apply_move(board, row, col, player):
    """Retourne un nouveau plateau apres le coup."""
    new_board = [r[:] for r in board]
    new_board[row][col] = player
    return new_board


def next_macro_constraint(row, col, board, macro):
    """
    Apres avoir joue en (row, col), retourne le prochain morpion contraint,
    ou None si ce morpion n'est pas disponible (libre de jouer partout).
    """
    lr, lc = get_local_pos(row, col)
    if is_local_available(board, macro, lr, lc):
        return (lr, lc)
    return None


# ---------------------------------------------------------------------------
# Fin de partie
# ---------------------------------------------------------------------------

def check_game_result(board, macro=None):
    """
    Retourne (termine, gagnant).
    gagnant : X, O, ou 0 pour egalite.
    """
    if macro is None:
        macro = compute_macro(board)

    winner = check_winner_3x3(macro)
    if winner != EMPTY:
        return True, winner

    # Verifier si au moins un coup reste possible
    for mr in range(3):
        for mc in range(3):
            if is_local_available(board, macro, mr, mc):
                return False, 0  # Partie en cours

    # Plus de coups : victoire au nombre de morpions
    x_cnt = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == X)
    o_cnt = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == O)
    if x_cnt > o_cnt:
        return True, X
    elif o_cnt > x_cnt:
        return True, O
    return True, 0


# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------

# Prefixe (13 espaces) qui aligne les bordures avec les numeros de lignes
_PFX = "             "

def _cell_str(board, macro, row, col, last_move):
    """Retourne la chaine de 3 chars pour une cellule."""
    mr, mc = row // 3, col // 3
    cell   = board[row][col]
    w      = macro[mr][mc]
    if last_move and (row, col) == last_move:
        return f"({SYMBOL[cell]})"
    if w != EMPTY:
        # Morpion gagne : on remplit toutes ses cases avec le symbole
        return f" {SYMBOL[w]} "
    return f" {SYMBOL[cell]} "


def display_board(board, next_macro=None, last_move=None):
    """Efface l'ecran et affiche le plateau avec une grille claire."""
    os.system('cls' if os.name == 'nt' else 'clear')

    macro = compute_macro(board)

    # --- Titre ---
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║    ULTIMATE TIC-TAC-TOE              ║")
    print("  ╚══════════════════════════════════════╝")
    print()

    # --- En-tete colonnes ---
    # Chaque cellule = 3 chars, separateur = 1 char
    # Apres le PREFIX (13) + '║' (1) + ' '(1) : premiere cellule a la position 15
    hdr = _PFX + " "
    for col in range(9):
        if col > 0:
            hdr += " "   # 1 espace pour │ ou ║
        hdr += f" {col+1} "
    print(hdr)

    # --- Bordure haute ---
    print(_PFX + "╔═══════════╦═══════════╦═══════════╗")

    for row in range(9):
        mr = row // 3

        # Separateur inter-lignes
        if row > 0:
            if row % 3 == 0:
                # Frontiere entre deux morpions (epaisse)
                print(_PFX + "╠═══════════╬═══════════╬═══════════╣")
            else:
                # Frontiere interne (fine)
                print(_PFX + "║───┼───┼───║───┼───┼───║───┼───┼───║")

        # Ligne de donnees
        line = f"  ligne {row+1:2}   ║"
        for col in range(9):
            if col > 0:
                line += "║" if col % 3 == 0 else "│"
            line += _cell_str(board, macro, row, col, last_move)
        line += "║"
        print(line)

    # --- Bordure basse ---
    print(_PFX + "╚═══════════╩═══════════╩═══════════╝")

    # --- Vue macro (3x3) ---
    print()
    print("  Vue macro  (X/O = morpion gagne, = = nul, . = en cours, * = actif)")
    print()
    for mr in range(3):
        if mr > 0:
            print("    ───┼───┼───")
        line = "    "
        for mc in range(3):
            if mc > 0:
                line += "│"
            w        = macro[mr][mc]
            is_full  = is_local_full(board, mr, mc)
            is_actif = (next_macro == (mr, mc))
            if is_actif:
                marker = "*"
            elif w == X:
                marker = "X"
            elif w == O:
                marker = "O"
            elif is_full:
                marker = "="
            else:
                marker = "."
            line += f" {marker} "
        print(line)

    # --- Informations de tour ---
    print()
    if next_macro is not None:
        mr, mc = next_macro
        print(f"  >>> Jouez dans le morpion : colonne {mc+1}, ligne {mr+1} <<<")
    else:
        print("  >>> Libre de jouer dans n'importe quel morpion <<<")
    if last_move:
        r, c = last_move
        print(f"  Dernier coup joue : col {c+1}, ligne {r+1}")
    print()


# ---------------------------------------------------------------------------
# Heuristique
# ---------------------------------------------------------------------------

def _score_line(a, b, c, player):
    """Score pour une ligne de 3 cases."""
    opp = O if player == X else X
    vals = [a, b, c]
    p = vals.count(player)
    e = vals.count(EMPTY)
    o = vals.count(opp)

    if o > 0 and p > 0:
        return 0  # Ligne bloquee des deux cotes
    if p == 3:
        return 500
    if p == 2 and e == 1:
        return 50
    if p == 1 and e == 2:
        return 5
    if o == 3:
        return -500
    if o == 2 and e == 1:
        return -50
    if o == 1 and e == 2:
        return -5
    return 0


def _score_3x3(cells, player):
    """Evalue une grille 3x3 pour player."""
    score = 0
    for line in LINES_3x3:
        vals = [cells[r][c] for r, c in line]
        score += _score_line(vals[0], vals[1], vals[2], player)
    # Bonus centre
    center = cells[1][1]
    if center == player:
        score += 10
    elif center != EMPTY:
        score -= 10
    # Bonus coins
    for r, c in [(0,0),(0,2),(2,0),(2,2)]:
        if cells[r][c] == player:
            score += 3
        elif cells[r][c] != EMPTY:
            score -= 3
    return score


def evaluate(board, player, macro=None):
    """
    Evalue le plateau pour `player`.
    Valeur positive = favorable pour player.
    """
    if macro is None:
        macro = compute_macro(board)

    # Victoire / defaite globale
    global_winner = check_winner_3x3(macro)
    if global_winner == player:
        return 100_000
    if global_winner != EMPTY:
        return -100_000

    opp = O if player == X else X
    score = 0

    # Evaluer les lignes du tableau macro
    for line in LINES_3x3:
        vals = [macro[r][c] for r, c in line]
        score += _score_line(vals[0], vals[1], vals[2], player) * 200

    # Bonus macro centre et coins
    if macro[1][1] == player:
        score += 500
    elif macro[1][1] == opp:
        score -= 500
    for r, c in [(0,0),(0,2),(2,0),(2,2)]:
        if macro[r][c] == player:
            score += 150
        elif macro[r][c] == opp:
            score -= 150

    # Evaluer chaque morpion local non termine
    for mr in range(3):
        for mc in range(3):
            if macro[mr][mc] == player:
                score += 300
            elif macro[mr][mc] == opp:
                score -= 300
            else:
                cells = [[board[mr*3+r][mc*3+c] for c in range(3)] for r in range(3)]
                score += _score_3x3(cells, player)

    return score


# ---------------------------------------------------------------------------
# Minimax avec elagage Alpha-Beta
# ---------------------------------------------------------------------------

def _move_priority(move):
    """Priorite d'un coup pour l'ordre de parcours (centre en premier)."""
    r, c = move
    lr, lc = get_local_pos(r, c)
    mr, mc = get_macro_pos(r, c)
    # Priorite haute = valeur faible (tri croissant)
    p = 0
    if lr == 1 and lc == 1:   # Centre du morpion local
        p -= 4
    if mr == 1 and mc == 1:   # Morpion central
        p -= 2
    if (lr, lc) in [(0,0),(0,2),(2,0),(2,2)]:  # Coins locaux
        p -= 1
    return p


def minimax(board, depth, alpha, beta, maximizing, ai_player, next_macro, macro=None):
    """
    Minimax avec elagage Alpha-Beta.
    ai_player : joueur que l'on cherche a maximiser.
    maximizing : True si c'est au tour de ai_player.
    """
    if macro is None:
        macro = compute_macro(board)

    done, winner = check_game_result(board, macro)
    if done:
        if winner == ai_player:
            return 100_000 + depth   # Victoire rapide preferee
        elif winner == 0:
            return 0
        else:
            return -100_000 - depth

    if depth == 0:
        return evaluate(board, ai_player, macro)

    opp = O if ai_player == X else X
    current = ai_player if maximizing else opp

    moves = get_valid_moves(board, next_macro, macro)
    if not moves:
        return evaluate(board, ai_player, macro)

    moves.sort(key=_move_priority)

    if maximizing:
        best = -math.inf
        for row, col in moves:
            nb = apply_move(board, row, col, current)
            nm = compute_macro(nb)
            nn = next_macro_constraint(row, col, nb, nm)
            val = minimax(nb, depth-1, alpha, beta, False, ai_player, nn, nm)
            best = max(best, val)
            alpha = max(alpha, val)
            if beta <= alpha:
                break
        return best
    else:
        best = math.inf
        for row, col in moves:
            nb = apply_move(board, row, col, current)
            nm = compute_macro(nb)
            nn = next_macro_constraint(row, col, nb, nm)
            val = minimax(nb, depth-1, alpha, beta, True, ai_player, nn, nm)
            best = min(best, val)
            beta = min(beta, val)
            if beta <= alpha:
                break
        return best


def ai_choose_move(board, next_macro, ai_player, depth=DEFAULT_DEPTH):
    """Retourne le meilleur coup (row, col) pour l'IA."""
    macro = compute_macro(board)
    moves = get_valid_moves(board, next_macro, macro)

    if not moves:
        return None

    moves.sort(key=_move_priority)

    best_val = -math.inf
    best_move = moves[0]

    for row, col in moves:
        nb = apply_move(board, row, col, ai_player)
        nm = compute_macro(nb)
        nn = next_macro_constraint(row, col, nb, nm)
        val = minimax(nb, depth-1, -math.inf, math.inf, False, ai_player, nn, nm)
        if val > best_val:
            best_val = val
            best_move = (row, col)

    return best_move


# ---------------------------------------------------------------------------
# Ecran de résultats
# ---------------------------------------------------------------------------

def show_result(board, winner, human, ai):
    """Affiche l'ecran de resultat apres la fin d'une partie."""
    os.system('cls' if os.name == 'nt' else 'clear')
    macro = compute_macro(board)

    x_boards = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == X)
    o_boards = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == O)
    player_boards = x_boards if human == X else o_boards
    ai_boards     = x_boards if ai    == X else o_boards

    W = 37  # largeur interieure de la boite

    def bline(txt=""):
        """Ligne de boite alignee."""
        return "  │" + txt.center(W) + "│"

    def bsep(mid="─"):
        return "  ├" + mid * W + "┤"

    # Titre selon le resultat
    if winner == human:
        titre     = "   ** VICTOIRE **   "
        sous      = f"Vous ({SYMBOL[human]}) avez gagne la partie !"
    elif winner != 0:
        titre     = "    ** DEFAITE **    "
        sous      = f"L'IA ({SYMBOL[ai]}) a gagne la partie."
    else:
        titre     = "  ** MATCH NUL **   "
        sous      = "Egalite parfaite !"

    print()
    print("  ╔" + "═" * W + "╗")
    print(bline())
    print(bline(titre))
    print(bline())
    print("  ╠" + "═" * W + "╣")
    print(bline())
    print(bline(sous))
    print(bline())
    print(bsep())

    # Score morpions
    print(bline("Morpions remportes"))
    print(bsep())
    print(bline(f"Vous  ({SYMBOL[human]})  :  {player_boards}  morpion(s)"))
    print(bline(f"IA    ({SYMBOL[ai]})  :  {ai_boards}  morpion(s)"))
    print(bsep())

    # Vue macro finale
    print(bline("Vue finale (macro)"))
    print(bsep())
    sym_m = {X: 'X', O: 'O', EMPTY: '.'}
    for mr in range(3):
        if mr > 0:
            print(bline("───┼───┼───"))
        row_str = " ".join(
            ("│" if mc > 0 else "") + f" {sym_m[macro[mr][mc]]} "
            for mc in range(3)
        )
        print(bline(row_str))

    print(bline())
    print("  ╚" + "═" * W + "╝")
    print()


# ---------------------------------------------------------------------------
# Tour du joueur humain
# ---------------------------------------------------------------------------

def human_turn(board, next_macro, player):
    """Demande et valide la saisie du joueur humain. Retourne (row, col)."""
    macro = compute_macro(board)

    while True:
        try:
            if next_macro is not None:
                mr, mc = next_macro
                print(f"  Vous devez jouer dans le morpion (colonne {mc+1}, ligne {mr+1})")
            raw = input(f"  [{SYMBOL[player]}] Colonne et ligne (ex: 5 3) : ").strip()
            parts = raw.split()
            if len(parts) != 2:
                print("  -> Format invalide. Deux nombres attendus (colonne ligne).")
                continue
            col_in = int(parts[0]) - 1
            row_in = int(parts[1]) - 1
            if not (0 <= row_in <= 8 and 0 <= col_in <= 8):
                print("  -> Hors limites. Utilisez des valeurs entre 1 et 9.")
                continue
            valid = get_valid_moves(board, next_macro, macro)
            if (row_in, col_in) not in valid:
                print("  -> Coup invalide. Ce coup n'est pas autorise ici.")
                continue
            return row_in, col_in
        except (ValueError, IndexError):
            print("  -> Entree invalide. Exemple : 5 3")


# ---------------------------------------------------------------------------
# Boucle de jeu principale
# ---------------------------------------------------------------------------

def play_game():
    """Lance et gere une partie complete."""
    print()
    print("=" * 56)
    print("    ULTIMATE TIC-TAC-TOE  --  IA Minimax + Alpha-Beta")
    print("=" * 56)
    print()
    print("  Regles rapides :")
    print("  - Grille 9x9 = 9 morpions 3x3.")
    print("  - Gagnez 3 morpions alignes pour remporter la partie.")
    print("  - Votre coup impose le morpion ou joue l'adversaire.")
    print("  - Coordonnees : colonne d'abord, ligne ensuite (1-9).")
    print()

    # Choix du premier joueur
    while True:
        c = input("  Qui commence ? [j=Joueur / i=IA] : ").strip().lower()
        if c in ('j', 'joueur'):
            human = X
            ai    = O
            print("  Le joueur commence avec les X.")
            break
        elif c in ('i', 'ia'):
            human = O
            ai    = X
            print("  L'IA commence avec les X.")
            break
        else:
            print("  -> Entrez 'j' ou 'i'.")

    print()

    board        = create_board()
    next_macro   = None   # Premier coup : libre
    last_move    = None
    current      = X     # X commence toujours

    while True:
        display_board(board, next_macro, last_move)

        macro = compute_macro(board)
        done, winner = check_game_result(board, macro)
        if done:
            break

        if current == human:
            print(f"  Votre tour ({SYMBOL[human]})")
            row, col = human_turn(board, next_macro, human)
            print(f"  >> Joueur joue en (col {col+1}, ligne {row+1})")
        else:
            print(f"  Tour de l'IA ({SYMBOL[ai]})... calcul en cours.")
            t0 = time.time()
            move = ai_choose_move(board, next_macro, ai)
            elapsed = time.time() - t0
            if move is None:
                print("  L'IA n'a aucun coup valide !")
                break
            row, col = move
            print(f"  >> IA joue en (col {col+1}, ligne {row+1})  [{elapsed:.2f}s]")

        board      = apply_move(board, row, col, current)
        last_move  = (row, col)
        new_macro  = compute_macro(board)
        next_macro = next_macro_constraint(row, col, board, new_macro)
        current    = O if current == X else X

    # Ecran de résultats
    macro  = compute_macro(board)
    _, winner = check_game_result(board, macro)
    show_result(board, winner, human, ai)

    again = input("  Rejouer ? (o/n) : ").strip().lower()
    if again in ('o', 'oui', 'y', 'yes'):
        play_game()


# ---------------------------------------------------------------------------
# Mode IA vs IA (pour tests)
# ---------------------------------------------------------------------------

def ai_vs_ai(depth_x=DEFAULT_DEPTH, depth_o=DEFAULT_DEPTH):
    """Fait jouer deux IA l'une contre l'autre."""
    print()
    print("=" * 40)
    print("   Mode IA vs IA")
    print("=" * 40)

    board       = create_board()
    next_macro  = None
    last_move   = None
    current     = X
    move_count  = 0

    while True:
        display_board(board, next_macro, last_move)

        macro = compute_macro(board)
        done, winner = check_game_result(board, macro)
        if done:
            break

        depth = depth_x if current == X else depth_o
        t0 = time.time()
        move = ai_choose_move(board, next_macro, current, depth)
        elapsed = time.time() - t0

        if move is None:
            print("  Plus de coups !")
            break

        row, col = move
        print(f"  >> IA-{SYMBOL[current]} joue ({col+1}, {row+1})  [{elapsed:.2f}s]")

        board      = apply_move(board, row, col, current)
        last_move  = (row, col)
        new_macro  = compute_macro(board)
        next_macro = next_macro_constraint(row, col, board, new_macro)
        current    = O if current == X else X
        move_count += 1

        input("  [Entree pour continuer]")

    # Ecran de résultats IA vs IA
    macro = compute_macro(board)
    x_boards = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == X)
    o_boards = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == O)
    _, winner = check_game_result(board, macro)

    os.system('cls' if os.name == 'nt' else 'clear')
    display_board(board, None, last_move)
    print()
    print("  " + "═" * 38)
    if winner == X:
        print("  ║      *** IA-X remporte la partie ! ***      ║" [:40])
    elif winner == O:
        print("  ║      *** IA-O remporte la partie ! ***      ║" [:40])
    else:
        print("  ║             *** MATCH NUL ***           ║" [:40])
    print("  " + "═" * 38)
    print(f"  IA-X : {x_boards} morpion(s) gagne(s)")
    print(f"  IA-O : {o_boards} morpion(s) gagne(s)")
    print(f"  Total de coups joues : {move_count}")
    print()


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("  1. Joueur vs IA")
    print("  2. IA vs IA (demonstration)")
    while True:
        choice = input("  Votre choix : ").strip()
        if choice == '1':
            play_game()
            break
        elif choice == '2':
            ai_vs_ai()
            break
        else:
            print("  -> Entrez 1 ou 2.")
