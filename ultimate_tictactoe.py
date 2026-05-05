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
import random

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

# Profondeur maximale et budget temps par coup pour l'iterative deepening
MAX_DEPTH  = 20
TIME_LIMIT = 3.0   # secondes

# logger les coups dans un fichier (game_log.txt)
TEST = True
TEST_LOG_FILE = "game_log.txt"

# ---------------------------------------------------------------------------
# Zobrist hashing + Transposition Table
# ---------------------------------------------------------------------------

random.seed(42)
# Table de valeurs aléatoires : ZOBRIST[joueur][row][col]
ZOBRIST = [[[random.getrandbits(64) for _ in range(9)] for _ in range(9)] for _ in range(3)]

# Flags pour les entrées de la TT
TT_EXACT = 0   # score exact
TT_LOWER = 1   # borne inférieure (alpha)
TT_UPPER = 2   # borne supérieure (beta)

# Transposition table : hash -> (depth, score, flag, best_move)
_tt: dict = {}
TT_MAX_SIZE = 1_000_000


def board_hash(board):
    """Calcule le hash Zobrist d'un plateau."""
    h = 0
    for r in range(9):
        for c in range(9):
            v = board[r][c]
            if v != EMPTY:
                h ^= ZOBRIST[v][r][c]
    return h


def tt_clear():
    _tt.clear()


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


def _macro_line_score(macro, player):
    """
    Score strategique des lignes macro.
    2-dans-une-ligne sans blocage = tres forte priorite.
    """
    opp = O if player == X else X
    score = 0
    for line in LINES_3x3:
        vals = [macro[r][c] for r, c in line]
        p = vals.count(player)
        o = vals.count(opp)
        e = vals.count(EMPTY)
        if o > 0 and p > 0:
            continue  # ligne bloquee
        if p == 2 and e == 1:
            score += 5_000   # menace directe de victoire macro
        elif p == 1 and e == 2:
            score += 1_500   # ligne naissante : valorisee pour anticiper
        elif o == 2 and e == 1:
            score -= 7_000   # bloquer > attaquer : menace adverse immediatement realisable
        elif o == 1 and e == 2:
            score -= 2_000   # ligne naissante adverse : a couper tot
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

    # Lignes macro (priorite principale)
    score += _macro_line_score(macro, player)

    # Bonus position macro : centre > coins > bords
    if macro[1][1] == player:
        score += 800
    elif macro[1][1] == opp:
        score -= 800
    for r, c in [(0,0),(0,2),(2,0),(2,2)]:
        if macro[r][c] == player:
            score += 300
        elif macro[r][c] == opp:
            score -= 300
    for r, c in [(0,1),(1,0),(1,2),(2,1)]:
        if macro[r][c] == player:
            score += 150
        elif macro[r][c] == opp:
            score -= 150

    # Morpions locaux : bonus reduit, subordonne a la strategie macro
    for mr in range(3):
        for mc in range(3):
            if macro[mr][mc] == player:
                score += 100
            elif macro[mr][mc] == opp:
                score -= 100
            else:
                cells = [[board[mr*3+r][mc*3+c] for c in range(3)] for r in range(3)]
                score += _score_3x3(cells, player)

    return score


# ---------------------------------------------------------------------------
# Gestion du timeout pour l'iterative deepening
# ---------------------------------------------------------------------------

class _Timeout(Exception):
    pass

_deadline: float = math.inf   # timestamp limite; math.inf = pas de limite


# ---------------------------------------------------------------------------
# Killer Moves
# ---------------------------------------------------------------------------

# _killers[depth] = liste des 2 derniers coups ayant causé une coupure beta à cette profondeur
_killers: dict = {}


def _add_killer(depth, move):
    lst = _killers.setdefault(depth, [])
    if move not in lst:
        lst.insert(0, move)
        if len(lst) > 2:
            lst.pop()


def killers_clear():
    _killers.clear()


# ---------------------------------------------------------------------------
# Minimax avec elagage Alpha-Beta
# ---------------------------------------------------------------------------

def _macro_threat(macro, pos, player):
    """
    Retourne le niveau de menace macro lie a la position (mr, mc) = pos.
    Positif si player beneficie, negatif si l'adversaire beneficie.
    Niveau 2 = 2-dans-une-ligne (critique), niveau 1 = 1-dans-une-ligne.
    """
    opp = O if player == X else X
    mr, mc = pos
    best = 0
    for line in LINES_3x3:
        if (mr, mc) not in line:
            continue
        vals = [macro[a][b] for a, b in line]
        p_cnt = vals.count(player)
        o_cnt = vals.count(opp)
        if p_cnt > 0 and o_cnt > 0:
            continue  # ligne bloquee
        if o_cnt == 2:
            best = min(best, -2)   # menace critique adversaire
        elif o_cnt == 1:
            best = min(best, -1)
        elif p_cnt == 2:
            best = max(best, 2)    # victoire macro imminente
        elif p_cnt == 1:
            best = max(best, 1)
    return best


def _move_priority(move, board=None, player=None, macro=None):
    """Priorite d'un coup pour l'ordre de parcours (valeur basse = exploré en premier)."""
    r, c = move
    lr, lc = get_local_pos(r, c)
    mr, mc = get_macro_pos(r, c)
    p = 0

    if board is not None and player is not None:
        opp = O if player == X else X
        cells = [[board[mr*3+i][mc*3+j] for j in range(3)] for i in range(3)]

        # --- Niveau 1 : impact sur la macro ---
        if macro is not None:
            # Simuler la victoire du morpion local par ce coup
            cells[lr][lc] = player
            wins_local = (check_winner_3x3(cells) == player)
            cells[lr][lc] = EMPTY

            if wins_local:
                threat = _macro_threat(macro, (mr, mc), player)
                if threat >= 2:
                    p -= 1000  # gagne la macro immediatement
                elif threat <= -2:
                    p -= 900   # bloque une victoire macro adverse imminente
                elif threat >= 1:
                    p -= 200   # avance une ligne macro pour soi
                elif threat == -1:
                    p -= 160   # coupe une ligne naissante adverse (nouvelle priorite)
                else:
                    p -= 100   # gagne un morpion local (neutre macro)
            else:
                # Blocage local : l'adversaire allait gagner ce morpion
                cells[lr][lc] = opp
                blocks_local = (check_winner_3x3(cells) == opp)
                cells[lr][lc] = EMPTY
                if blocks_local:
                    threat = _macro_threat(macro, (mr, mc), player)
                    if threat <= -2:
                        p -= 880   # bloquer un morpion qui aurait complete la macro adverse
                    elif threat == -1:
                        p -= 70    # bloquer un morpion sur une ligne naissante adverse
                    else:
                        p -= 50

            # --- Niveau 2 : ou on envoie l'adversaire ---
            if is_local_available(board, macro, lr, lc):
                dest_threat = _macro_threat(macro, (lr, lc), opp)
                if dest_threat >= 2:
                    p += 500   # on envoie l'adversaire là où il gagne la macro !
                elif dest_threat == 1:
                    p += 150   # on l'envoie sur une case qui l'avance
                elif dest_threat <= -2:
                    p -= 80    # on l'envoie là où on a 2-en-ligne (bon pour nous)
                elif dest_threat == -1:
                    p -= 40    # on l'envoie là où on a 1-en-ligne (leger avantage)

                # Penalite statique : valeur intrinseque de la destination
                # independante de l'occupation (evite d'envoyer au centre/coins meme vides)
                if macro[lr][lc] == EMPTY:
                    if (lr, lc) == (1, 1):
                        p += 120   # centre macro : toujours precieux pour l'adversaire
                    elif (lr, lc) in ((0,0),(0,2),(2,0),(2,2)):
                        p += 40    # coins macro

    if lr == 1 and lc == 1:   # Centre du morpion local
        p -= 4
    if mr == 1 and mc == 1:   # Morpion central
        p -= 2
    if (lr, lc) in [(0,0),(0,2),(2,0),(2,2)]:  # Coins locaux
        p -= 1
    return p


def minimax(board, depth, alpha, beta, maximizing, ai_player, next_macro, macro=None, h=None):
    """
    Minimax avec elagage Alpha-Beta + Transposition Table + Killer Moves.
    ai_player : joueur que l'on cherche a maximiser.
    maximizing : True si c'est au tour de ai_player.
    h : hash Zobrist courant du plateau.
    """
    if time.time() >= _deadline:
        raise _Timeout()

    if macro is None:
        macro = compute_macro(board)
    if h is None:
        h = board_hash(board)

    # --- Consultation TT ---
    tt_entry = _tt.get(h)
    if tt_entry is not None:
        tt_depth, tt_score, tt_flag, _ = tt_entry
        if tt_depth >= depth:
            if tt_flag == TT_EXACT:
                return tt_score
            if tt_flag == TT_LOWER and tt_score >= beta:
                return tt_score
            if tt_flag == TT_UPPER and tt_score <= alpha:
                return tt_score

    done, winner = check_game_result(board, macro)
    if done:
        if winner == ai_player:
            return 100_000 + depth
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

    # Killer moves en tête si présents dans la liste
    killers = _killers.get(depth, [])
    moves.sort(key=lambda m: (
        0 if m in killers else 1,
        _move_priority(m, board, current, macro)
    ))

    orig_alpha = alpha
    best_move  = moves[0]

    if maximizing:
        best = -math.inf
        for row, col in moves:
            nh = h ^ ZOBRIST[current][row][col]
            nb = apply_move(board, row, col, current)
            nm = compute_macro(nb)
            nn = next_macro_constraint(row, col, nb, nm)
            val = minimax(nb, depth-1, alpha, beta, False, ai_player, nn, nm, nh)
            if val > best:
                best = val
                best_move = (row, col)
            alpha = max(alpha, val)
            if beta <= alpha:
                _add_killer(depth, (row, col))
                break
    else:
        best = math.inf
        for row, col in moves:
            nh = h ^ ZOBRIST[current][row][col]
            nb = apply_move(board, row, col, current)
            nm = compute_macro(nb)
            nn = next_macro_constraint(row, col, nb, nm)
            val = minimax(nb, depth-1, alpha, beta, True, ai_player, nn, nm, nh)
            if val < best:
                best = val
                best_move = (row, col)
            beta = min(beta, val)
            if beta <= alpha:
                _add_killer(depth, (row, col))
                break

    # --- Ecriture TT ---
    if len(_tt) < TT_MAX_SIZE:
        if best <= orig_alpha:
            flag = TT_UPPER
        elif best >= beta:
            flag = TT_LOWER
        else:
            flag = TT_EXACT
        _tt[h] = (depth, best, flag, best_move)

    return best


def _forced_move(moves, board, macro, player):
    """
    Retourne immediatement un coup force sans lancer minimax :
    1. Coup qui gagne la partie macro (victoire immediate).
    2. Coup qui bloque la victoire macro adverse au coup suivant (2-en-ligne).
    3. Coup qui gagne un morpion coupant une ligne naissante adverse (1-en-ligne)
       sur une case strategique (centre ou coin macro) — uniquement si libre.
    Retourne None si aucun coup force trouve.
    """
    opp = O if player == X else X
    block_2 = None   # bloquer 2-en-ligne adverse
    block_1 = None   # couper 1-en-ligne adverse sur case strategique

    STRATEGIC = {(1, 1), (0, 0), (0, 2), (2, 0), (2, 2)}  # centre + coins macro

    for row, col in moves:
        mr, mc = get_macro_pos(row, col)
        lr, lc = get_local_pos(row, col)
        cells = [[board[mr*3+i][mc*3+j] for j in range(3)] for i in range(3)]

        # Simuler la victoire du morpion local
        cells[lr][lc] = player
        if check_winner_3x3(cells) != player:
            continue  # ce coup ne gagne pas le morpion local

        # Ce coup gagne le morpion local : verifier l'impact macro
        sim_macro = [r[:] for r in macro]
        sim_macro[mr][mc] = player
        if check_winner_3x3(sim_macro) == player:
            return (row, col)   # victoire macro immediate !

        for line in LINES_3x3:
            if (mr, mc) not in line:
                continue
            vals = [macro[a][b] for a, b in line]
            # Bloquer 2-en-ligne adverse
            if block_2 is None and vals.count(opp) == 2 and vals.count(EMPTY) == 1:
                block_2 = (row, col)
            # Couper 1-en-ligne adverse sur case strategique
            if (block_1 is None
                    and vals.count(opp) == 1
                    and vals.count(player) == 0
                    and (mr, mc) in STRATEGIC):
                block_1 = (row, col)

    if block_2 is not None:
        return block_2
    return block_1  # None si aucun coup force


def ai_choose_move(board, next_macro, ai_player, depth=6):
    """Retourne le meilleur coup (row, col) pour l'IA."""
    macro = compute_macro(board)
    moves = get_valid_moves(board, next_macro, macro)

    if not moves:
        return None

    # Coups forces (victoire/blocage macro) : pas besoin de minimax
    forced = _forced_move(moves, board, macro, ai_player)
    if forced is not None:
        return forced

    moves.sort(key=lambda m: _move_priority(m, board, ai_player, macro))

    h = board_hash(board)
    best_val  = -math.inf
    best_move = moves[0]

    # Consulte la TT pour un coup suggéré et le mettre en tête
    tt_entry = _tt.get(h)
    if tt_entry and tt_entry[3] in moves:
        moves.remove(tt_entry[3])
        moves.insert(0, tt_entry[3])

    for row, col in moves:
        nh = h ^ ZOBRIST[ai_player][row][col]
        nb = apply_move(board, row, col, ai_player)
        nm = compute_macro(nb)
        nn = next_macro_constraint(row, col, nb, nm)
        try:
            val = minimax(nb, depth-1, -math.inf, math.inf, False, ai_player, nn, nm, nh)
        except _Timeout:
            break
        if val > best_val:
            best_val  = val
            best_move = (row, col)

    return best_move


def ai_choose_move_timed(board, next_macro, ai_player, time_limit=TIME_LIMIT):
    """
    Iterative deepening : cherche de profondeur 1 jusqu'a MAX_DEPTH,
    en s'arretant strictement quand le budget temps est epuise.
    Retourne le meilleur coup trouve a la derniere profondeur completee.
    """
    global _deadline
    tt_clear()
    killers_clear()

    macro = compute_macro(board)
    moves = get_valid_moves(board, next_macro, macro)
    if not moves:
        return None

    best_move = moves[0]
    _deadline = time.time() + time_limit

    for depth in range(1, MAX_DEPTH + 1):
        if time.time() >= _deadline:
            break
        try:
            candidate = ai_choose_move(board, next_macro, ai_player, depth)
            if candidate is not None:
                best_move = candidate
        except _Timeout:
            break

    _deadline = math.inf
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
            valid = get_valid_moves(board, next_macro, macro)
            if next_macro is not None:
                mr, mc = next_macro
                cols = sorted(set(c + 1 for _, c in valid))
                rows = sorted(set(r + 1 for r, _ in valid))
                print(f"  Vous devez jouer dans le morpion (colonne {mc+1}, ligne {mr+1})")
                print(f"  Colonnes valides : {cols}  |  Lignes valides : {rows}")
            else:
                print("  Vous pouvez jouer dans n'importe quel morpion disponible.")
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
            if (row_in, col_in) not in valid:
                cols = sorted(set(c + 1 for _, c in valid))
                rows = sorted(set(r + 1 for r, _ in valid))
                print(f"  -> Coup invalide. Colonnes valides : {cols}  |  Lignes valides : {rows}")
                continue
            return row_in, col_in
        except (ValueError, IndexError):
            print("  -> Entree invalide. Exemple : 5 3")


# ---------------------------------------------------------------------------
# Logging (actif si TEST = True)
# ---------------------------------------------------------------------------

def log_event(msg):
    if not TEST:
        return
    with open(TEST_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')


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

    import datetime
    log_event("=" * 60)
    log_event(f"PARTIE  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_event(f"Joueur={SYMBOL[human]} (commence={'oui' if human==X else 'non'})  IA={SYMBOL[ai]}")
    log_event("=" * 60)
    move_num = 0

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

        move_num += 1
        constraint_str = f"morpion ({next_macro[1]+1},{next_macro[0]+1})" if next_macro else "libre"

        if current == human:
            print(f"  Votre tour ({SYMBOL[human]})")
            row, col = human_turn(board, next_macro, human)
            print(f"  >> Joueur joue en (col {col+1}, ligne {row+1})")
            log_event(f"Coup {move_num:>3} | JOUEUR ({SYMBOL[human]}) | col {col+1}, ligne {row+1} | contrainte={constraint_str}")
        else:
            print(f"  Tour de l'IA ({SYMBOL[ai]})... calcul en cours.")
            t0 = time.time()
            move = ai_choose_move_timed(board, next_macro, ai)
            elapsed = time.time() - t0
            if move is None:
                print("  L'IA n'a aucun coup valide !")
                break
            row, col = move
            score_before = evaluate(board, ai, macro)
            print(f"  >> IA joue en (col {col+1}, ligne {row+1})  [{elapsed:.2f}s]")
            log_event(f"Coup {move_num:>3} | IA     ({SYMBOL[ai]}) | col {col+1}, ligne {row+1} | contrainte={constraint_str} | {elapsed:.2f}s | score={score_before:+d}")

        board      = apply_move(board, row, col, current)
        last_move  = (row, col)
        new_macro  = compute_macro(board)

        # Log si un morpion local vient d'être gagné
        mr_p, mc_p = get_macro_pos(row, col)
        if new_macro[mr_p][mc_p] == current:
            macro_line_count = sum(
                1 for line in LINES_3x3
                if (mr_p, mc_p) in line and all(new_macro[a][b] == current for a, b in line)
            )
            log_event(f"       -> Morpion local ({mc_p+1},{mr_p+1}) remporte par {SYMBOL[current]}"
                      + (f" => ALIGNEMENT MACRO !" if macro_line_count > 0 else ""))

        next_macro = next_macro_constraint(row, col, board, new_macro)
        current    = O if current == X else X

    # Ecran de résultats
    macro  = compute_macro(board)
    _, winner = check_game_result(board, macro)
    x_cnt = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == X)
    o_cnt = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == O)
    log_event("-" * 60)
    if winner == human:
        log_event(f"RESULTAT : VICTOIRE du joueur ({SYMBOL[human]})")
    elif winner != 0:
        log_event(f"RESULTAT : VICTOIRE de l'IA ({SYMBOL[ai]})")
    else:
        log_event(f"RESULTAT : NUL  (X={x_cnt} morpions, O={o_cnt} morpions)")
    log_event(f"Morpions X={x_cnt}  O={o_cnt}")
    log_event("=" * 60 + "\n")

    show_result(board, winner, human, ai)

    again = input("  Rejouer ? (o/n) : ").strip().lower()
    return again in ('o', 'oui', 'y', 'yes')


# ---------------------------------------------------------------------------
# Mode IA vs IA (pour tests)
# ---------------------------------------------------------------------------

def ai_vs_ai():
    """Fait jouer deux IA l'une contre l'autre."""
    print()
    print("=" * 40)
    print("   Mode IA vs IA")
    print("=" * 40)
    print(f"  Budget temps par coup : {TIME_LIMIT}s")
    print()

    import datetime
    log_event("=" * 60)
    log_event(f"IA VS IA  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_event(f"Budget temps : {TIME_LIMIT}s par coup")
    log_event("=" * 60)

    board       = create_board()
    next_macro  = None
    last_move   = None
    current     = X
    move_count  = 0
    history     = []
    total_time  = {X: 0.0, O: 0.0}

    while True:
        display_board(board, next_macro, last_move)

        macro = compute_macro(board)
        x_boards = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == X)
        o_boards = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == O)

        done, winner = check_game_result(board, macro)
        if done:
            break

        # --- Panneau de statut ---
        print("  ┌─────────────────────────────────────────┐")
        print(f"  │  Coup n°{move_count+1:<3}  │  IA-X : {x_boards} morpion(s)  │  IA-O : {o_boards} morpion(s)  │")
        print(f"  │  Temps total  IA-X : {total_time[X]:.1f}s  │  IA-O : {total_time[O]:.1f}s        │")
        print("  └─────────────────────────────────────────┘")
        print()

        if next_macro is not None:
            mr, mc = next_macro
            print(f"  Contrainte : IA-{SYMBOL[current]} doit jouer dans le morpion (col {mc+1}, ligne {mr+1})")
        else:
            print(f"  IA-{SYMBOL[current]} est libre de jouer n'importe ou.")
        print()

        print(f"  IA-{SYMBOL[current]} reflechit (budget {TIME_LIMIT}s)...", end="", flush=True)
        t0 = time.time()
        move = ai_choose_move_timed(board, next_macro, current)
        elapsed = time.time() - t0
        total_time[current] += elapsed
        print(f" {elapsed:.2f}s")

        if move is None:
            print("  Plus de coups !")
            break

        row, col = move
        score = evaluate(board, current, macro)
        constraint_str = f"morpion ({next_macro[1]+1},{next_macro[0]+1})" if next_macro else "libre"
        print(f"  >> IA-{SYMBOL[current]} joue en (col {col+1}, ligne {row+1})")
        print(f"     Score heuristique avant coup : {score:+d}")
        log_event(f"Coup {move_count+1:>3} | IA-{SYMBOL[current]} | col {col+1}, ligne {row+1} | contrainte={constraint_str} | {elapsed:.2f}s | score={score:+d}")

        board      = apply_move(board, row, col, current)
        last_move  = (row, col)
        new_macro  = compute_macro(board)

        # Morpion local venait d'etre gagne ?
        mr_played, mc_played = get_macro_pos(row, col)
        if new_macro[mr_played][mc_played] == current:
            print(f"  *** IA-{SYMBOL[current]} remporte le morpion local ({mc_played+1},{mr_played+1}) ! ***")
            macro_line_count = sum(
                1 for line in LINES_3x3
                if (mr_played, mc_played) in line and all(new_macro[a][b] == current for a, b in line)
            )
            log_event(f"       -> Morpion local ({mc_played+1},{mr_played+1}) remporte par IA-{SYMBOL[current]}"
                      + (" => ALIGNEMENT MACRO !" if macro_line_count > 0 else ""))

        next_macro = next_macro_constraint(row, col, board, new_macro)
        if next_macro is not None:
            nmr, nmc = next_macro
            print(f"  => IA-{SYMBOL[O if current==X else X]} sera contrainte au morpion (col {nmc+1}, ligne {nmr+1})")
        else:
            print(f"  => IA-{SYMBOL[O if current==X else X]} sera libre de jouer partout.")

        history.append((SYMBOL[current], col+1, row+1, elapsed))
        current    = O if current == X else X
        move_count += 1

        print()
        input("  [Entree pour continuer]")

    # Ecran de résultats IA vs IA
    macro = compute_macro(board)
    x_boards = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == X)
    o_boards = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == O)
    _, winner = check_game_result(board, macro)

    log_event("-" * 60)
    if winner == X:
        log_event("RESULTAT : VICTOIRE IA-X")
    elif winner == O:
        log_event("RESULTAT : VICTOIRE IA-O")
    else:
        log_event(f"RESULTAT : NUL  (X={x_boards} morpions, O={o_boards} morpions)")
    log_event(f"Morpions X={x_boards}  O={o_boards}  |  Coups joues={move_count}")
    log_event(f"Temps total IA-X={total_time[X]:.1f}s  IA-O={total_time[O]:.1f}s")
    log_event("=" * 60 + "\n")

    os.system('cls' if os.name == 'nt' else 'clear')
    display_board(board, None, last_move)
    print()
    print("  " + "═" * 42)
    if winner == X:
        print("  ║       *** IA-X remporte la partie ! ***      ║"[:44])
    elif winner == O:
        print("  ║       *** IA-O remporte la partie ! ***      ║"[:44])
    else:
        print("  ║              *** MATCH NUL ***               ║"[:44])
    print("  " + "═" * 42)
    print()
    print(f"  Morpions IA-X : {x_boards}  |  Morpions IA-O : {o_boards}")
    print(f"  Total de coups joues : {move_count}")
    print(f"  Temps total IA-X : {total_time[X]:.1f}s  |  Temps total IA-O : {total_time[O]:.1f}s")
    if move_count > 0:
        print(f"  Temps moyen/coup  IA-X : {total_time[X]/max(1, sum(1 for h in history if h[0]=='X')):.2f}s"
              f"  |  IA-O : {total_time[O]/max(1, sum(1 for h in history if h[0]=='O')):.2f}s")
    print()
    print("  Historique des coups :")
    print("  " + "─" * 38)
    for i, (sym, c, r, t) in enumerate(history):
        print(f"  Coup {i+1:>2} | IA-{sym} | col {c}, ligne {r} | {t:.2f}s")
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
            while play_game():
                pass
            break
        elif choice == '2':
            ai_vs_ai()
            break
        else:
            print("  -> Entrez 1 ou 2.")
