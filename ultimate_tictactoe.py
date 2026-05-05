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

Architecture IA (refonte) :
  - Etat de jeu mutable (board, macro, occ_count) avec make/unmake -> pas de copie.
  - Macro maintenu incrementalement : O(1) par coup au lieu de O(81).
  - Hash Zobrist incluant le plateau, la contrainte next_macro et le joueur courant.
  - Transposition table conservee entre coups, remplacement par profondeur.
  - Iterative deepening borne par budget temps.
  - Quiescence search sur les coups "instables" (gain de morpion local).
  - Move ordering : TT-move > killers > history > heuristique statique.
  - Heuristique : combinaison pondere (controle macro, mobilite, flux, position).
"""

import datetime
import math
import os
import random
import re
import sys
import time

# Force UTF-8 sur Windows pour eviter les soucis d'accents dans la console.
if os.name == 'nt':
    os.system('chcp 65001 > nul')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

EMPTY = 0
X = 1
O = 2

SYMBOL = {EMPTY: '.', X: 'X', O: 'O'}

MAX_DEPTH  = 20
TIME_LIMIT = 3.0   # budget par coup

# Log optionnel des coups dans game_log.txt.
TEST = True
TEST_LOG_FILE = "game_log.txt"

# ---------------------------------------------------------------------------
# Zobrist hashing + Transposition Table
# ---------------------------------------------------------------------------

random.seed(42)
# Table de valeurs aleatoires : ZOBRIST[joueur][row][col].
ZOBRIST = [[[random.getrandbits(64) for _ in range(9)] for _ in range(9)] for _ in range(3)]
# Hash supplementaire pour le morpion impose au prochain joueur.
# Index 0..8 = morpion force, 9 = coup libre.
NEXT_MACRO_ZOBRIST = [random.getrandbits(64) for _ in range(10)]

# Flags pour les entrees de la table de transposition.
TT_EXACT = 0   # score exact
TT_LOWER = 1   # borne inferieure (alpha)
TT_UPPER = 2   # borne superieure (beta)

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


def _next_macro_hash(next_macro):
    """Hash de la contrainte de prochain morpion."""
    if next_macro is None:
        return NEXT_MACRO_ZOBRIST[9]
    mr, mc = next_macro
    return NEXT_MACRO_ZOBRIST[mr * 3 + mc]


def tt_key(board_h, next_macro):
    """Cle TT complete : plateau + morpion force."""
    return board_h ^ _next_macro_hash(next_macro)


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

# Pour chaque case (r,c), liste des lignes qui la traversent (indices dans LINES_3x3)
_LINES_BY_CELL = [[[] for _ in range(3)] for _ in range(3)]
for li, line in enumerate(LINES_3x3):
    for r, c in line:
        _LINES_BY_CELL[r][c].append(li)


def check_winner_3x3(cells):
    """Retourne le gagnant d'une grille 3x3, ou EMPTY."""
    for line in LINES_3x3:
        a = cells[line[0][0]][line[0][1]]
        if a == EMPTY:
            continue
        if a == cells[line[1][0]][line[1][1]] == cells[line[2][0]][line[2][1]]:
            return a
    return EMPTY


# ---------------------------------------------------------------------------
# Zobrist hashing
# ---------------------------------------------------------------------------

random.seed(42)
# ZOBRIST[player][row][col] : valeur aleatoire 64 bits
ZOBRIST = [[[random.getrandbits(64) for _ in range(9)] for _ in range(9)] for _ in range(3)]
# Hash pour chaque contrainte next_macro possible : 9 morpions + "libre"
ZOBRIST_NEXT = [random.getrandbits(64) for _ in range(10)]  # 0..8 + 9=libre
# Hash pour le joueur courant (XOR si c'est au tour de O)
ZOBRIST_SIDE = random.getrandbits(64)


def _next_macro_idx(next_macro):
    """Index dans ZOBRIST_NEXT pour la contrainte courante."""
    if next_macro is None:
        return 9
    return next_macro[0] * 3 + next_macro[1]


# ---------------------------------------------------------------------------
# Transposition table (avec remplacement par profondeur)
# ---------------------------------------------------------------------------

TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2

# hash -> (depth, score, flag, best_move)
_tt: dict = {}
TT_MAX_SIZE = 2_000_000


def tt_lookup(h):
    return _tt.get(h)


def tt_store(h, depth, score, flag, best_move):
    """Stocke une entree avec strategie de remplacement par profondeur."""
    existing = _tt.get(h)
    if existing is not None and existing[0] > depth:
        return  # entree existante plus profonde -> on garde
    if len(_tt) >= TT_MAX_SIZE and existing is None:
        # Cache plein : on n'ajoute plus de nouvelles entrees
        # (les entrees existantes peuvent encore etre mises a jour)
        return
    _tt[h] = (depth, score, flag, best_move)


def tt_clear():
    _tt.clear()


# ---------------------------------------------------------------------------
# Etat de jeu (mutable, make/unmake)
# ---------------------------------------------------------------------------

class GameState:
    """
    Etat complet du jeu, mutable, supportant make/unmake en O(1).

    Champs principaux :
      board[r][c]      : 9x9, contient EMPTY/X/O
      macro[mr][mc]    : 3x3, gagnant du morpion local (EMPTY si non gagne)
      occ[mr][mc]      : nombre de cases occupees dans le morpion local
      side             : joueur a jouer (X ou O)
      next_macro       : (mr, mc) ou None
      hash             : hash Zobrist incremental
      history          : pile pour unmake (each: (row, col, prev_macro_val,
                          prev_occ, prev_next_macro, prev_hash, prev_side))
    """

    __slots__ = ("board", "macro", "occ", "side", "next_macro", "hash",
                 "history")

    def __init__(self, board=None, side=X, next_macro=None):
        if board is None:
            self.board = [[EMPTY] * 9 for _ in range(9)]
        else:
            self.board = [row[:] for row in board]
        self.side = side
        self.next_macro = next_macro
        self.macro = [[EMPTY] * 3 for _ in range(3)]
        self.occ = [[0] * 3 for _ in range(3)]
        self.history = []

        # Initialiser macro et occ depuis le board
        for mr in range(3):
            for mc in range(3):
                cnt = 0
                cells = [[EMPTY]*3 for _ in range(3)]
                for r in range(3):
                    for c in range(3):
                        v = self.board[mr*3+r][mc*3+c]
                        cells[r][c] = v
                        if v != EMPTY:
                            cnt += 1
                self.occ[mr][mc] = cnt
                self.macro[mr][mc] = check_winner_3x3(cells)

        # Hash initial
        h = 0
        for r in range(9):
            for c in range(9):
                v = self.board[r][c]
                if v != EMPTY:
                    h ^= ZOBRIST[v][r][c]
        h ^= ZOBRIST_NEXT[_next_macro_idx(next_macro)]
        if side == O:
            h ^= ZOBRIST_SIDE
        self.hash = h

    def is_local_full(self, mr, mc):
        return self.occ[mr][mc] >= 9

    def is_local_available(self, mr, mc):
        return self.macro[mr][mc] == EMPTY and self.occ[mr][mc] < 9

    def _check_local_winner(self, mr, mc):
        """Verifie le gagnant d'un morpion local en lisant directement board."""
        b = self.board
        r0, c0 = mr*3, mc*3
        for line in LINES_3x3:
            a = b[r0+line[0][0]][c0+line[0][1]]
            if a == EMPTY:
                continue
            if a == b[r0+line[1][0]][c0+line[1][1]] == b[r0+line[2][0]][c0+line[2][1]]:
                return a
        return EMPTY

    def get_valid_moves(self):
        """Retourne la liste des coups valides (row, col)."""
        moves = []
        b = self.board
        if self.next_macro is not None:
            mr, mc = self.next_macro
            if self.is_local_available(mr, mc):
                r0, c0 = mr*3, mc*3
                for r in range(3):
                    for c in range(3):
                        if b[r0+r][c0+c] == EMPTY:
                            moves.append((r0+r, c0+c))
                return moves
        # libre
        for mr in range(3):
            for mc in range(3):
                if not self.is_local_available(mr, mc):
                    continue
                r0, c0 = mr*3, mc*3
                for r in range(3):
                    for c in range(3):
                        if b[r0+r][c0+c] == EMPTY:
                            moves.append((r0+r, c0+c))
        return moves

    def is_terminal(self):
        """Retourne (termine, gagnant). gagnant : X, O, 0 (egalite) ou None si en cours."""
        w = check_winner_3x3(self.macro)
        if w != EMPTY:
            return True, w
        # Reste-t-il un coup possible ?
        for mr in range(3):
            for mc in range(3):
                if self.is_local_available(mr, mc):
                    return False, None
        # Plus de coups
        x_cnt = sum(1 for mr in range(3) for mc in range(3) if self.macro[mr][mc] == X)
        o_cnt = sum(1 for mr in range(3) for mc in range(3) if self.macro[mr][mc] == O)
        if x_cnt > o_cnt:
            return True, X
        if o_cnt > x_cnt:
            return True, O
        return True, 0

    def make_move(self, row, col):
        """Joue un coup pour le joueur courant. Met a jour macro, occ, hash, side, next_macro."""
        player = self.side
        mr, mc = row // 3, col // 3
        lr, lc = row % 3, col % 3

        prev_macro_val = self.macro[mr][mc]
        prev_occ = self.occ[mr][mc]
        prev_next_macro = self.next_macro
        prev_hash = self.hash
        prev_side = self.side

        # Pose le pion
        self.board[row][col] = player
        self.occ[mr][mc] = prev_occ + 1

        # Mise a jour hash : pion + retire ancien next_macro + ancien side
        h = self.hash
        h ^= ZOBRIST[player][row][col]
        h ^= ZOBRIST_NEXT[_next_macro_idx(prev_next_macro)]
        if prev_side == O:
            h ^= ZOBRIST_SIDE

        # Recalculer le winner local seulement si pas deja gagne
        if prev_macro_val == EMPTY:
            w = self._check_local_winner(mr, mc)
            if w != EMPTY:
                self.macro[mr][mc] = w

        # Determiner la nouvelle contrainte
        target_mr, target_mc = lr, lc
        if self.is_local_available(target_mr, target_mc):
            new_next = (target_mr, target_mc)
        else:
            new_next = None

        # Changer le joueur
        new_side = O if player == X else X
        h ^= ZOBRIST_NEXT[_next_macro_idx(new_next)]
        if new_side == O:
            h ^= ZOBRIST_SIDE

        self.next_macro = new_next
        self.side = new_side
        self.hash = h

        self.history.append((row, col, prev_macro_val, prev_occ,
                             prev_next_macro, prev_hash, prev_side))

    def unmake_move(self):
        """Annule le dernier coup."""
        row, col, prev_macro_val, prev_occ, prev_next_macro, prev_hash, prev_side = self.history.pop()
        mr, mc = row // 3, col // 3
        self.board[row][col] = EMPTY
        self.occ[mr][mc] = prev_occ
        self.macro[mr][mc] = prev_macro_val
        self.next_macro = prev_next_macro
        self.hash = prev_hash
        self.side = prev_side


# ---------------------------------------------------------------------------
# Evaluation heuristique
# ---------------------------------------------------------------------------
#
# Echelle des scores (normalisee) :
#   Victoire/defaite globale : ±100_000 (+ depth bonus pour preferer rapide)
#   Victoire macro imminente (2 alignes ouverts)   : ±5_000
#   Ligne macro en construction (1 ouvert)         : ±500
#   Position macro (centre/coins/bords)            : ±50 a ±200
#   Morpion local gagne                            : ±100
#   Position locale (lignes, centre, coins)        : ±1 a ±50
#
# Ratio choisi : la priorite est macro >> local, mais le local reste utile
# pour orienter les premiers coups (avant que la macro ne s'eclaire).

# Poids cle pour la threat-detection
W_MACRO_WIN_THREAT     = 5_000   # je peux gagner la macro au prochain coup (2-en-ligne)
W_MACRO_LOSS_THREAT    = -7_000  # adversaire peut gagner la macro (asymetrie volontaire)
W_MACRO_LINE_OPEN_ME   = 500
W_MACRO_LINE_OPEN_OPP  = -500
W_MACRO_FORK_BONUS     = 2_000   # bonus pour double menace macro
W_MACRO_FORK_PENALTY   = -3_000

# Position macro
W_MACRO_CENTER  = 200
W_MACRO_CORNER  = 80
W_MACRO_EDGE    = 40

# Morpion gagne (au-dela de la ligne)
W_LOCAL_WON     = 100

# Local : valeur dans un morpion non termine
W_LOCAL_LINE_2  = 30   # 2-en-ligne local sans blocage
W_LOCAL_LINE_1  = 3
W_LOCAL_CENTER  = 8
W_LOCAL_CORNER  = 2

# Mobilite / flux
W_MOBILITY      = 4    # par coup en plus pour le joueur a jouer (faible mais utile)
W_BAD_SEND      = -150 # envoyer dans morpion ouvrant lignes adverses


def _score_local_3x3(board, mr, mc, player, opp):
    """Score local d'un morpion non termine, pour le perspective de player."""
    r0, c0 = mr*3, mc*3
    score = 0
    for line in LINES_3x3:
        a = board[r0+line[0][0]][c0+line[0][1]]
        b = board[r0+line[1][0]][c0+line[1][1]]
        c = board[r0+line[2][0]][c0+line[2][1]]
        p = (a == player) + (b == player) + (c == player)
        o = (a == opp) + (b == opp) + (c == opp)
        if p > 0 and o > 0:
            continue
        if p == 2:
            score += W_LOCAL_LINE_2
        elif p == 1:
            score += W_LOCAL_LINE_1
        elif o == 2:
            score -= W_LOCAL_LINE_2
        elif o == 1:
            score -= W_LOCAL_LINE_1
    # centre
    cv = board[r0+1][c0+1]
    if cv == player:
        score += W_LOCAL_CENTER
    elif cv == opp:
        score -= W_LOCAL_CENTER
    # coins
    for r, c in ((0,0),(0,2),(2,0),(2,2)):
        v = board[r0+r][c0+c]
        if v == player:
            score += W_LOCAL_CORNER
        elif v == opp:
            score -= W_LOCAL_CORNER
    return score


def _macro_threats(macro, player, opp):
    """
    Compte les menaces macro :
    Retourne (n_two_open_me, n_two_open_opp, line_score)
    line_score = somme des contributions de toutes les lignes macro.
    """
    n_two_me = 0
    n_two_opp = 0
    line_score = 0
    for line in LINES_3x3:
        a = macro[line[0][0]][line[0][1]]
        b = macro[line[1][0]][line[1][1]]
        c = macro[line[2][0]][line[2][1]]
        p = (a == player) + (b == player) + (c == player)
        o = (a == opp) + (b == opp) + (c == opp)
        if p > 0 and o > 0:
            continue
        if p == 2:
            n_two_me += 1
            line_score += W_MACRO_WIN_THREAT
        elif p == 1:
            line_score += W_MACRO_LINE_OPEN_ME
        elif o == 2:
            n_two_opp += 1
            line_score += W_MACRO_LOSS_THREAT
        elif o == 1:
            line_score += W_MACRO_LINE_OPEN_OPP
    return n_two_me, n_two_opp, line_score


def evaluate(state, ai_player):
    """
    Evalue l'etat pour ai_player. Score normalise (positif = favorable).
    """
    macro = state.macro
    board = state.board

    # Terminal global ?
    w = check_winner_3x3(macro)
    if w == ai_player:
        return 100_000
    if w != EMPTY:
        return -100_000

    opp = O if ai_player == X else X
    score = 0

    # 1. Lignes macro + menaces
    n2_me, n2_opp, line_score = _macro_threats(macro, ai_player, opp)
    score += line_score
    # Forks macro (deux 2-en-lignes simultanees = victoire forcee)
    if n2_me >= 2:
        score += W_MACRO_FORK_BONUS
    if n2_opp >= 2:
        score += W_MACRO_FORK_PENALTY

    # 2. Position macro et morpions gagnes
    for mr in range(3):
        for mc in range(3):
            v = macro[mr][mc]
            if v == ai_player:
                score += W_LOCAL_WON
            elif v == opp:
                score -= W_LOCAL_WON
            # bonus position selon (mr, mc), seulement si on a gagne ou c'est libre
            if (mr, mc) == (1, 1):
                pos_w = W_MACRO_CENTER
            elif (mr, mc) in ((0,0),(0,2),(2,0),(2,2)):
                pos_w = W_MACRO_CORNER
            else:
                pos_w = W_MACRO_EDGE
            if v == ai_player:
                score += pos_w
            elif v == opp:
                score -= pos_w
            else:
                # Morpion ouvert : score local
                score += _score_local_3x3(board, mr, mc, ai_player, opp)

    # 3. Flux / mobilite : avantage si l'adversaire est restreint
    # La contrainte courante s'applique a state.side (pas forcement ai_player)
    if state.next_macro is not None:
        mr, mc = state.next_macro
        if state.is_local_available(mr, mc):
            # Compter les coups disponibles pour le joueur a jouer
            free = 9 - state.occ[mr][mc]
            if state.side == ai_player:
                score += W_MOBILITY * free  # plus de choix = mieux
            else:
                score -= W_MOBILITY * free
        # Si non disponible : libre = 81 - cases jouees, pas tres discriminant
    return score


# ---------------------------------------------------------------------------
# Killers, history heuristic, timeout
# ---------------------------------------------------------------------------

class _Timeout(Exception):
    pass

_deadline: float = math.inf

# Killers indexes par profondeur
_killers: dict = {}
# History heuristic : _history[player][row][col] = score cumule
_history = [[[0]*9 for _ in range(9)] for _ in range(3)]


def _add_killer(depth, move):
    lst = _killers.setdefault(depth, [])
    if move not in lst:
        lst.insert(0, move)
        if len(lst) > 2:
            lst.pop()


def _add_history(player, move, depth):
    r, c = move
    _history[player][r][c] += depth * depth  # bonus quadratique en depth


def killers_clear():
    _killers.clear()


def history_clear():
    for p in range(3):
        for r in range(9):
            for c in range(9):
                _history[p][r][c] = 0


# ---------------------------------------------------------------------------
# Move ordering
# ---------------------------------------------------------------------------

def _move_score(state, move, player, tt_move, killers):
    """Score d'ordre (plus haut = explore en premier)."""
    if move == tt_move:
        return 1_000_000
    if move in killers:
        return 500_000

    r, c = move
    mr, mc = r // 3, c // 3
    lr, lc = r % 3, c % 3
    opp = O if player == X else X
    s = 0

    # Simulation locale rapide pour detecter gain/blocage local
    board = state.board
    r0, c0 = mr*3, mc*3
    # Verifie si poser ici gagne le morpion local
    board[r][c] = player
    wins_local = (state._check_local_winner(mr, mc) == player)
    # Verifie blocage : si l'adversaire avait pose ici, gagnait-il ?
    if not wins_local:
        board[r][c] = opp
        blocks_local = (state._check_local_winner(mr, mc) == opp)
    else:
        blocks_local = False
    board[r][c] = EMPTY

    macro = state.macro
    if wins_local:
        # Cherche l'impact macro : ce gain complete-t-il une ligne macro ?
        for li in _LINES_BY_CELL[mr][mc]:
            line = LINES_3x3[li]
            a = macro[line[0][0]][line[0][1]]
            b = macro[line[1][0]][line[1][1]]
            cc = macro[line[2][0]][line[2][1]]
            cnt_me = (a == player) + (b == player) + (cc == player)
            cnt_op = (a == opp) + (b == opp) + (cc == opp)
            if cnt_op > 0:
                continue
            if cnt_me == 2:
                s += 200_000  # gagne la macro
                break
            elif cnt_me == 1:
                s += 8_000

        # Si ce coup bloque aussi une 2-en-ligne adverse :
        for li in _LINES_BY_CELL[mr][mc]:
            line = LINES_3x3[li]
            a = macro[line[0][0]][line[0][1]]
            b = macro[line[1][0]][line[1][1]]
            cc = macro[line[2][0]][line[2][1]]
            cnt_op = (a == opp) + (b == opp) + (cc == opp)
            cnt_me = (a == player) + (b == player) + (cc == player)
            if cnt_me > 0:
                continue
            if cnt_op == 2:
                s += 100_000  # bloquage critique
        s += 5_000  # gagner un local est intrinsequement bon

    if blocks_local:
        # Bloquer un local empeche l'adversaire de progresser sur sa macro
        for li in _LINES_BY_CELL[mr][mc]:
            line = LINES_3x3[li]
            a = macro[line[0][0]][line[0][1]]
            b = macro[line[1][0]][line[1][1]]
            cc = macro[line[2][0]][line[2][1]]
            cnt_op = (a == opp) + (b == opp) + (cc == opp)
            cnt_me = (a == player) + (b == player) + (cc == player)
            if cnt_me > 0:
                continue
            if cnt_op == 2:
                s += 50_000

    # Penalite : ou envoie-t-on l'adversaire ?
    # next_macro pour l'adversaire = (lr, lc) si dispo, sinon libre
    if state.is_local_available(lr, lc):
        # Si le morpion (lr, lc) ouvre une victoire macro pour opp -> tres mauvais
        for li in _LINES_BY_CELL[lr][lc]:
            line = LINES_3x3[li]
            a = macro[line[0][0]][line[0][1]]
            b = macro[line[1][0]][line[1][1]]
            cc = macro[line[2][0]][line[2][1]]
            cnt_op = (a == opp) + (b == opp) + (cc == opp)
            cnt_me = (a == player) + (b == player) + (cc == player)
            if cnt_me > 0:
                continue
            if cnt_op == 2:
                s -= 80_000  # eviter d'envoyer la
            elif cnt_op == 1:
                s -= 100
        # Penaliser si on envoie au centre macro libre
        if (lr, lc) == (1, 1) and macro[1][1] == EMPTY:
            s -= 200
    else:
        # On laisse l'adversaire libre : tres mauvais en general
        s -= 1_500

    # History heuristic
    s += _history[player][r][c]

    # Position locale (centre > coin > bord)
    if lr == 1 and lc == 1:
        s += 5
    elif (lr, lc) in ((0,0),(0,2),(2,0),(2,2)):
        s += 2

    return s


def _order_moves(state, moves, player, tt_move, depth):
    killers = _killers.get(depth, [])
    moves.sort(key=lambda m: _move_score(state, m, player, tt_move, killers),
               reverse=True)
    return moves


# ---------------------------------------------------------------------------
# Quiescence search
# ---------------------------------------------------------------------------

def _is_capture_move(state, move, player):
    """
    Un coup est 'instable' (capture) s'il :
    - gagne un morpion local
    - bloque un coup gagnant de l'adversaire dans le morpion local
    """
    r, c = move
    mr, mc = r // 3, c // 3
    opp = O if player == X else X
    board = state.board
    board[r][c] = player
    wins = (state._check_local_winner(mr, mc) == player)
    if wins:
        board[r][c] = EMPTY
        return True
    board[r][c] = opp
    blocks = (state._check_local_winner(mr, mc) == opp)
    board[r][c] = EMPTY
    return blocks


def quiescence(state, alpha, beta, ai_player, qdepth):
    """
    Recherche en profondeur sur les coups capturants/forcants.
    Stabilise l'evaluation pour eviter l'effet d'horizon.
    """
    if time.time() >= _deadline:
        raise _Timeout()

    done, winner = state.is_terminal()
    if done:
        if winner == ai_player:
            return 100_000
        if winner == 0:
            return 0
        return -100_000

    stand_pat = evaluate(state, ai_player)
    if qdepth <= 0:
        return stand_pat

    maximizing = (state.side == ai_player)

    if maximizing:
        if stand_pat >= beta:
            return stand_pat
        if stand_pat > alpha:
            alpha = stand_pat
    else:
        if stand_pat <= alpha:
            return stand_pat
        if stand_pat < beta:
            beta = stand_pat

    moves = state.get_valid_moves()
    # Ne garder que les coups capturants
    captures = [m for m in moves if _is_capture_move(state, m, state.side)]
    if not captures:
        return stand_pat

    captures = _order_moves(state, captures, state.side, None, 0)

    if maximizing:
        best = stand_pat
        for move in captures:
            state.make_move(*move)
            val = quiescence(state, alpha, beta, ai_player, qdepth - 1)
            state.unmake_move()
            if val > best:
                best = val
            if val > alpha:
                alpha = val
            if alpha >= beta:
                break
        return best
    else:
        best = stand_pat
        for move in captures:
            state.make_move(*move)
            val = quiescence(state, alpha, beta, ai_player, qdepth - 1)
            state.unmake_move()
            if val < best:
                best = val
            if val < beta:
                beta = val
            if alpha >= beta:
                break
        return best


# ---------------------------------------------------------------------------
# Minimax + Alpha-Beta
# ---------------------------------------------------------------------------

def minimax(state, depth, alpha, beta, ai_player):
    """
    Minimax avec alpha-beta sur l'etat mutable (make/unmake).
    Retourne le score pour ai_player.
    """
    if time.time() >= _deadline:
        raise _Timeout()

    # Terminal ?
    done, winner = state.is_terminal()
    if done:
        if winner == ai_player:
            return 100_000 + depth   # preferer les victoires rapides
        if winner == 0:
            return 0
        return -100_000 - depth

    # TT lookup
    h = state.hash
    tt_entry = _tt.get(h)
    tt_move = None
    if tt_entry is not None:
        tt_depth, tt_score, tt_flag, tt_move = tt_entry
        if tt_depth >= depth:
            if tt_flag == TT_EXACT:
                return tt_score
            if tt_flag == TT_LOWER and tt_score >= beta:
                return tt_score
            if tt_flag == TT_UPPER and tt_score <= alpha:
                return tt_score

    if depth == 0:
        return quiescence(state, alpha, beta, ai_player, QUIESCENCE_MAX)

    moves = state.get_valid_moves()
    if not moves:
        return evaluate(state, ai_player)

    side = state.side
    maximizing = (side == ai_player)

    moves = _order_moves(state, moves, side, tt_move, depth)

    orig_alpha = alpha
    orig_beta = beta
    best_move = moves[0]

    if maximizing:
        best = -math.inf
        for move in moves:
            state.make_move(*move)
            val = minimax(state, depth - 1, alpha, beta, ai_player)
            state.unmake_move()
            if val > best:
                best = val
                best_move = move
            if val > alpha:
                alpha = val
            if alpha >= beta:
                _add_killer(depth, move)
                _add_history(side, move, depth)
                break
    else:
        best = math.inf
        for move in moves:
            state.make_move(*move)
            val = minimax(state, depth - 1, alpha, beta, ai_player)
            state.unmake_move()
            if val < best:
                best = val
                best_move = move
            if val < beta:
                beta = val
            if alpha >= beta:
                _add_killer(depth, move)
                _add_history(side, move, depth)
                break

    # TT store
    if best <= orig_alpha:
        flag = TT_UPPER
    elif best >= orig_beta:
        flag = TT_LOWER
    else:
        flag = TT_EXACT
    tt_store(h, depth, best, flag, best_move)

    return best


# ---------------------------------------------------------------------------
# Forced move detection
# ---------------------------------------------------------------------------

def _forced_move(state, player):
    """
    Detection de coups forces avant minimax :
    1. Coup gagnant la macro immediatement (priorite max).
    2. Coup bloquant une victoire macro adverse au prochain coup.
    Retourne None si aucun coup force evident.

    Note : on ne detecte pas les forks plus complexes ici (laissees a minimax),
    pour ne pas occulter des coups plus subtils. Le forced_move est un filet
    de securite contre les erreurs grossieres.
    """
    moves = state.get_valid_moves()
    if not moves:
        return None
    opp = O if player == X else X
    macro = state.macro
    board = state.board

    block_candidate = None

    for move in moves:
        r, c = move
        mr, mc = r // 3, c // 3
        lr, lc = r % 3, c % 3

        # Le coup doit gagner le morpion local pour avoir un impact macro
        board[r][c] = player
        wins_local = (state._check_local_winner(mr, mc) == player)
        board[r][c] = EMPTY

        if not wins_local:
            continue

        # Simule la macro mise a jour
        for li in _LINES_BY_CELL[mr][mc]:
            line = LINES_3x3[li]
            (r1, c1), (r2, c2), (r3, c3) = line
            vals = [
                player if (r1, c1) == (mr, mc) else macro[r1][c1],
                player if (r2, c2) == (mr, mc) else macro[r2][c2],
                player if (r3, c3) == (mr, mc) else macro[r3][c3],
            ]
            if vals[0] == vals[1] == vals[2] == player:
                # Verifier qu'on n'envoie pas l'adversaire dans une victoire :
                # peu importe ici, c'est une victoire macro IMMEDIATE pour nous
                return move

    # Detection de blocage critique : adversaire a 2-en-ligne avec une 3eme
    # case dont le morpion peut etre gagne par lui au prochain coup.
    # Un coup qui empeche cela passe par : gagner ce 3eme morpion pour soi.
    for move in moves:
        r, c = move
        mr, mc = r // 3, c // 3
        board[r][c] = player
        wins_local = (state._check_local_winner(mr, mc) == player)
        board[r][c] = EMPTY
        if not wins_local:
            continue
        # Ce coup gagne le local : verifie si bloque une 2-en-ligne adverse
        for li in _LINES_BY_CELL[mr][mc]:
            line = LINES_3x3[li]
            cnt_op = sum(1 for (rr, cc) in line if macro[rr][cc] == opp)
            cnt_me = sum(1 for (rr, cc) in line if macro[rr][cc] == player)
            if cnt_me > 0:
                continue
            if cnt_op == 2:
                if block_candidate is None:
                    block_candidate = move

    return block_candidate


# ---------------------------------------------------------------------------
# Recherche racine + iterative deepening
# ---------------------------------------------------------------------------

def _root_search(state, depth, ai_player):
    """Recherche racine retournant (best_move, best_score)."""
    moves = state.get_valid_moves()
    if not moves:
        return None, 0

    h = state.hash
    tt_entry = _tt.get(h)
    tt_move = tt_entry[3] if tt_entry else None

    moves = _order_moves(state, moves, state.side, tt_move, depth)

    alpha, beta = -math.inf, math.inf
    best_move = moves[0]
    best_val = -math.inf

    for move in moves:
        state.make_move(*move)
        val = minimax(state, depth - 1, alpha, beta, ai_player)
        state.unmake_move()
        if val > best_val:
            best_val = val
            best_move = move
        if val > alpha:
            alpha = val

    # Mise a jour TT racine
    tt_store(h, depth, best_val, TT_EXACT, best_move)
    return best_move, best_val


def ai_choose_move_timed(board, next_macro, ai_player, time_limit=TIME_LIMIT):
    """
    Iterative deepening avec budget temps. Retourne le meilleur coup trouve.
    """
    global _deadline

    state = GameState(board=board, side=ai_player, next_macro=next_macro)
    moves = state.get_valid_moves()
    if not moves:
        return None
    if len(moves) == 1:
        return moves[0]

    # Coup force (victoire/blocage macro immediat) : pas besoin de chercher
    forced = _forced_move(state, ai_player)
    if forced is not None:
        return forced

    # On ne vide PAS la TT entre coups : les sous-arbres restent valides
    # car le hash inclut next_macro et side. Mais on remet a zero les killers
    # et l'historique pour eviter la pollution entre positions tres differentes.
    killers_clear()
    history_clear()

    _deadline = time.time() + time_limit
    best_move = moves[0]

    try:
        for depth in range(1, MAX_DEPTH + 1):
            if time.time() >= _deadline:
                break
            candidate, _ = _root_search(state, depth, ai_player)
            if candidate is not None:
                best_move = candidate
    except _Timeout:
        pass

    _deadline = math.inf
    return best_move


# ---------------------------------------------------------------------------
# Affichage (inchange)
# ---------------------------------------------------------------------------

def _cell_str(board, macro, row, col, last_move):
    mr, mc = row // 3, col // 3
    cell = board[row][col]
    w = macro[mr][mc]
    if last_move and (row, col) == last_move:
        return f"({SYMBOL[cell]})"
    if w != EMPTY:
        return f" {SYMBOL[w]} "
    return f" {SYMBOL[cell]} "


def display_board(board, next_macro=None, last_move=None):
    """Efface l'ecran et affiche le plateau."""
    os.system('cls' if os.name == 'nt' else 'clear')
    macro = compute_macro(board)

    print()
    print("  ========================================")
    print("      ULTIMATE TIC-TAC-TOE")
    print("  ========================================")
    print()

    print("             1   2   3     4   5   6     7   8   9")
    print("          +-----------+-----------+-----------+")
    for row in range(9):
        if row > 0 and row % 3 == 0:
            print("          +-----------+-----------+-----------+")
        line = f"  ligne {row+1:2} |"
        for col in range(9):
            line += _cell_str(board, macro, row, col, last_move)
            if col % 3 == 2:
                line += "|"
        print(line)
    print("          +-----------+-----------+-----------+")
    print()
    print("  Vue macro  (X/O = gagne, = = plein, . = en cours, * = actif)")
    print()
    for mr in range(3):
        if mr > 0:
            print("    ---+---+---")
        line = "    "
        for mc in range(3):
            if mc > 0:
                line += "|"
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
# Helpers compatibles avec l'ancienne API (utilises par la boucle de jeu)
# ---------------------------------------------------------------------------

# Petits poids positionnels ajoutes a l'heuristique principale.
# Ils donnent un peu plus d'importance au centre et aux coins.
LOCAL_BOARD_WEIGHTS = (1.4, 1.0, 1.4, 1.0, 1.75, 1.0, 1.4, 1.0, 1.4)
LOCAL_CELL_WEIGHTS = (0.2, 0.17, 0.2, 0.17, 0.22, 0.17, 0.2, 0.17, 0.2)
POSITIONAL_EVAL_SCALE = 6
MOVE_ORDER_SCALE = 20


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


def get_macro_pos(row, col):
    return row // 3, col // 3


def _local_winning_moves(cells, player):
    """Liste des cases qui feraient gagner cette grille 3x3 a player."""
    wins = []
    for r in range(3):
        for c in range(3):
            if cells[r][c] != EMPTY:
                continue
            cells[r][c] = player
            if check_winner_3x3(cells) == player:
                wins.append((r, c))
            cells[r][c] = EMPTY
    return wins


def _macro_cell_weight(macro, pos, player):
    """
    Importance d'un morpion local selon sa position macro.
    Plus le morpion peut completer une ligne macro, plus ses menaces locales
    doivent peser dans l'evaluation.
    """
    opp = O if player == X else X
    mr, mc = pos
    weight = 1
    for line in LINES_3x3:
        if (mr, mc) not in line:
            continue
        vals = [macro[r][c] for r, c in line]
        if vals.count(player) > 0 and vals.count(opp) > 0:
            continue
        if vals.count(opp) == 2 and vals.count(EMPTY) == 1:
            weight = max(weight, 7)  # morpion qui donne la partie a l'adversaire
        elif vals.count(player) == 2 and vals.count(EMPTY) == 1:
            weight = max(weight, 5)  # morpion qui peut nous donner la partie
        elif vals.count(opp) == 1 and vals.count(EMPTY) == 2:
            weight = max(weight, 3)
        elif vals.count(player) == 1 and vals.count(EMPTY) == 2:
            weight = max(weight, 2)
    return weight


def _local_tactical_score(cells, player):
    """Score tactique local: menaces immediates et forks."""
    opp = O if player == X else X
    player_wins = len(_local_winning_moves(cells, player))
    opp_wins = len(_local_winning_moves(cells, opp))

    score = 0
    score += player_wins * 80
    score -= opp_wins * 120
    if player_wins >= 2:
        score += 220  # fork local: deux facons de gagner ensuite
    if opp_wins >= 2:
        score -= 320  # fork adverse local, priorite defensive
    return score


def _macro_winning_cells(macro, player):
    """Cases macro vides qui feraient gagner player si ce morpion etait gagne."""
    wins = []
    for mr in range(3):
        for mc in range(3):
            if macro[mr][mc] != EMPTY:
                continue
            sim_macro = [row[:] for row in macro]
            sim_macro[mr][mc] = player
            if check_winner_3x3(sim_macro) == player:
                wins.append((mr, mc))
    return wins


def _legal_local_winning_moves(board, macro, next_macro, player):
    """
    Coups legaux qui gagnent le morpion local pour player.
    Retourne (row, col, mr, mc, wins_macro, macro_win_count_after).
    """
    wins = []
    for row, col in get_valid_moves(board, next_macro, macro):
        mr, mc = get_macro_pos(row, col)
        lr, lc = get_local_pos(row, col)
        cells = [[board[mr*3+r][mc*3+c] for c in range(3)] for r in range(3)]
        cells[lr][lc] = player
        if check_winner_3x3(cells) != player:
            continue

        sim_macro = [line[:] for line in macro]
        sim_macro[mr][mc] = player
        wins_macro = (check_winner_3x3(sim_macro) == player)
        macro_win_count = len(_macro_winning_cells(sim_macro, player))
        wins.append((row, col, mr, mc, wins_macro, macro_win_count))
    return wins


def _turn_tactical_score(board, macro, next_macro, current_player, ai_player):
    """Score tactique des menaces disponibles pour le joueur au trait."""
    sign = 1 if current_player == ai_player else -1
    local_wins = _legal_local_winning_moves(board, macro, next_macro, current_player)
    score = 0

    macro_wins = sum(1 for *_, wins_macro, _ in local_wins if wins_macro)
    if macro_wins:
        score += sign * 90_000

    fork_moves = sum(1 for *_, wins_macro, macro_win_count in local_wins
                     if not wins_macro and macro_win_count >= 2)
    if fork_moves:
        score += sign * 18_000 * fork_moves

    critical_local_wins = sum(
        1 for _, _, mr, mc, wins_macro, _ in local_wins
        if not wins_macro and _macro_cell_weight(macro, (mr, mc), current_player) >= 5
    )
    score += sign * 5_000 * critical_local_wins

    if next_macro is None and local_wins:
        # Un coup libre permet de choisir le meilleur morpion tactique.
        score += sign * (6_000 + 1_500 * len(local_wins))

    return score


def _reply_tactical_risk(board, macro, next_macro, player):
    """Danger du prochain coup adverse apres un coup de player."""
    opp = O if player == X else X
    return -_turn_tactical_score(board, macro, next_macro, opp, player)


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


def _compact_check_win(cells):
    """Version compacte du test de victoire sur une liste de 9 cases."""
    lines = (
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6),
    )
    for side in (1, -1):
        target = side * 3
        for a, b, c in lines:
            if cells[a] + cells[b] + cells[c] == target:
                return side
    return 0


def _compact_line_has_sum(cells, target):
    return (
        cells[0] + cells[1] + cells[2] == target or
        cells[3] + cells[4] + cells[5] == target or
        cells[6] + cells[7] + cells[8] == target or
        cells[0] + cells[3] + cells[6] == target or
        cells[1] + cells[4] + cells[7] == target or
        cells[2] + cells[5] + cells[8] == target or
        cells[0] + cells[4] + cells[8] == target or
        cells[2] + cells[4] + cells[6] == target
    )


def _compact_has_blocked_pair(cells, a):
    triples = (
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6),
    )
    for i, j, k in triples:
        if cells[i] + cells[j] == 2 * a and cells[k] == -a:
            return True
        if cells[j] + cells[k] == 2 * a and cells[i] == -a:
            return True
        if cells[i] + cells[k] == 2 * a and cells[j] == -a:
            return True
    return False


def _compact_local_score(cells):
    """Score local rapide. Positif = favorable au joueur encode en -1."""
    evaluation = 0.0
    for idx, value in enumerate(cells):
        evaluation -= value * LOCAL_CELL_WEIGHTS[idx]

    a = 2
    if cells[0] + cells[1] + cells[2] == a or cells[3] + cells[4] + cells[5] == a or cells[6] + cells[7] + cells[8] == a:
        evaluation -= 6
    if cells[0] + cells[3] + cells[6] == a or cells[1] + cells[4] + cells[7] == a or cells[2] + cells[5] + cells[8] == a:
        evaluation -= 6
    if cells[0] + cells[4] + cells[8] == a or cells[2] + cells[4] + cells[6] == a:
        evaluation -= 7

    if _compact_has_blocked_pair(cells, -1):
        evaluation -= 9

    a = -2
    if cells[0] + cells[1] + cells[2] == a or cells[3] + cells[4] + cells[5] == a or cells[6] + cells[7] + cells[8] == a:
        evaluation += 6
    if cells[0] + cells[3] + cells[6] == a or cells[1] + cells[4] + cells[7] == a or cells[2] + cells[5] + cells[8] == a:
        evaluation += 6
    if cells[0] + cells[4] + cells[8] == a or cells[2] + cells[4] + cells[6] == a:
        evaluation += 7

    if _compact_has_blocked_pair(cells, 1):
        evaluation += 9

    evaluation -= _compact_check_win(cells) * 12
    return evaluation


def _compact_cells_from_local(board, mr, mc, player):
    """Encode un morpion local: joueur evalue = -1, adversaire = 1."""
    opp = O if player == X else X
    cells = []
    for lr in range(3):
        for lc in range(3):
            value = board[mr * 3 + lr][mc * 3 + lc]
            if value == player:
                cells.append(-1)
            elif value == opp:
                cells.append(1)
            else:
                cells.append(0)
    return cells


def _next_macro_index(next_macro):
    if next_macro is None:
        return -1
    mr, mc = next_macro
    return mr * 3 + mc


def _positional_evaluate_game(board, player, macro, next_macro):
    """Petit score positionnel ajoute a l'evaluation principale."""
    current_board = _next_macro_index(next_macro)
    evaluation = 0.0
    main_board = []
    for idx in range(9):
        mr, mc = divmod(idx, 3)
        local = _compact_cells_from_local(board, mr, mc, player)
        local_eval = _compact_local_score(local)
        evaluation += local_eval * 1.5 * LOCAL_BOARD_WEIGHTS[idx]
        if idx == current_board:
            evaluation += local_eval * LOCAL_BOARD_WEIGHTS[idx]
        local_winner = _compact_check_win(local)
        evaluation -= local_winner * LOCAL_BOARD_WEIGHTS[idx]
        main_board.append(local_winner)

    evaluation -= _compact_check_win(main_board) * 5000
    evaluation += _compact_local_score(main_board) * 150
    return evaluation


def _positional_move_score(cells, square):
    """Score rapide pour aider l'ordre des coups dans un morpion local."""
    cells[square] = -1
    evaluation = LOCAL_CELL_WEIGHTS[square]

    if _compact_line_has_sum(cells, -2):
        evaluation += 1
    if _compact_line_has_sum(cells, -3):
        evaluation += 5

    cells[square] = 1
    if _compact_line_has_sum(cells, 3):
        evaluation += 2

    cells[square] = -1
    evaluation -= _compact_check_win(cells) * 15
    cells[square] = 0
    return evaluation


def evaluate(board, player, macro=None, next_macro=None, current_player=None):
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

    player_macro_wins = len(_macro_winning_cells(macro, player))
    opp_macro_wins = len(_macro_winning_cells(macro, opp))
    if player_macro_wins >= 2:
        score += 12_000 * player_macro_wins
    elif player_macro_wins == 1:
        score += 3_000
    if opp_macro_wins >= 2:
        score -= 16_000 * opp_macro_wins
    elif opp_macro_wins == 1:
        score -= 5_000

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
                weight = _macro_cell_weight(macro, (mr, mc), player)
                score += _score_3x3(cells, player) * weight
                score += _local_tactical_score(cells, player) * weight

    if current_player is not None:
        score += _turn_tactical_score(board, macro, next_macro, current_player, player)

    score += int(_positional_evaluate_game(board, player, macro, next_macro) * POSITIONAL_EVAL_SCALE)

    return score


def is_local_full(board, mr, mc):
    for r in range(3):
        for c in range(3):
            if board[mr*3+r][mc*3+c] == EMPTY:
                return False
    return True


# ---------------------------------------------------------------------------
# Killer Moves
# ---------------------------------------------------------------------------

# _killers[depth] = 2 coups qui ont deja cause une coupure beta a cette profondeur.
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
    """Priorite d'un coup pour l'ordre de parcours (valeur basse = explore en premier)."""
    r, c = move
    lr, lc = get_local_pos(r, c)
    mr, mc = get_macro_pos(r, c)
    p = 0

    if board is not None and player is not None:
        opp = O if player == X else X
        cells = [[board[mr*3+i][mc*3+j] for j in range(3)] for i in range(3)]

        # --- Niveau 1 : impact sur la macro ---
        if macro is not None:
            local_weight = _macro_cell_weight(macro, (mr, mc), player)

            # Simuler la victoire du morpion local par ce coup
            cells[lr][lc] = player
            wins_local = (check_winner_3x3(cells) == player)
            creates_fork = (len(_local_winning_moves(cells, player)) >= 2)
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
                if creates_fork:
                    p -= 80 * local_weight

                # Blocage local : l'adversaire allait gagner ce morpion
                cells[lr][lc] = opp
                blocks_local = (check_winner_3x3(cells) == opp)
                blocks_fork = (len(_local_winning_moves(cells, opp)) >= 2)
                cells[lr][lc] = EMPTY
                if blocks_local:
                    threat = _macro_threat(macro, (mr, mc), player)
                    if threat <= -2:
                        p -= 880   # bloquer un morpion qui aurait complete la macro adverse
                    elif threat == -1:
                        p -= 70    # bloquer un morpion sur une ligne naissante adverse
                    else:
                        p -= 50
                elif blocks_fork:
                    p -= 70 * local_weight

            # --- Niveau 2 : ou on envoie l'adversaire ---
            if is_local_available(board, macro, lr, lc):
                dest_threat = _macro_threat(macro, (lr, lc), opp)
                if dest_threat >= 2:
                    p += 500   # on envoie l'adversaire ou il gagne la macro
                elif dest_threat == 1:
                    p += 150   # on l'envoie sur une case qui l'avance
                elif dest_threat <= -2:
                    p -= 80    # on l'envoie ou on a deja 2-en-ligne
                elif dest_threat == -1:
                    p -= 40    # on l'envoie ou on a deja 1-en-ligne

                # Penalite statique : valeur intrinseque de la destination
                # independante de l'occupation (evite d'envoyer au centre/coins meme vides)
                if macro[lr][lc] == EMPTY:
                    if (lr, lc) == (1, 1):
                        p += 120   # centre macro : toujours precieux pour l'adversaire
                    elif (lr, lc) in ((0,0),(0,2),(2,0),(2,2)):
                        p += 40    # coins macro

            nb = apply_move(board, r, c, player)
            nm = compute_macro(nb)
            nn = next_macro_constraint(r, c, nb, nm)
            reply_risk = _reply_tactical_risk(nb, nm, nn, player)
            if reply_risk >= 90_000:
                p += 5_000  # donne une victoire macro legale au prochain coup
            elif reply_risk > 0:
                p += min(2_000, reply_risk // 20)

            compact_cells = _compact_cells_from_local(board, mr, mc, player)
            compact_square = lr * 3 + lc
            p -= int(_positional_move_score(compact_cells, compact_square) * MOVE_ORDER_SCALE)

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
    moves = []

    # --- Consultation TT ---
    key = tt_key(h, next_macro)
    tt_entry = _tt.get(key)
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

    opp = O if ai_player == X else X
    current = ai_player if maximizing else opp

    if depth == 0:
        return evaluate(board, ai_player, macro, next_macro, current)

    moves = get_valid_moves(board, next_macro, macro)
    if not moves:
        return evaluate(board, ai_player, macro, next_macro, current)

    # Killer moves en tete si presents dans la liste.
    killers = _killers.get(depth, [])
    moves.sort(key=lambda m: (
        0 if m in killers else 1,
        _move_priority(m, board, current, macro)
    ))

    orig_alpha = alpha
    orig_beta  = beta
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
        elif best >= orig_beta:
            flag = TT_LOWER
        else:
            flag = TT_EXACT
        _tt[key] = (depth, best, flag, best_move)

    return best


def _opponent_has_immediate_macro_win(board, macro, next_macro, opponent):
    """Vrai si opponent peut gagner la partie au prochain coup."""
    moves = get_valid_moves(board, next_macro, macro)
    for row, col in moves:
        mr, mc = get_macro_pos(row, col)
        lr, lc = get_local_pos(row, col)
        cells = [[board[mr*3+i][mc*3+j] for j in range(3)] for i in range(3)]
        cells[lr][lc] = opponent
        if check_winner_3x3(cells) != opponent:
            continue

        sim_macro = [r[:] for r in macro]
        sim_macro[mr][mc] = opponent
        if check_winner_3x3(sim_macro) == opponent:
            return True
    return False


def _gives_opponent_immediate_macro_win(row, col, board, macro, player):
    """Vrai si jouer ce coup donne une victoire macro immediate a l'adversaire."""
    opp = O if player == X else X
    nb = apply_move(board, row, col, player)
    nm = compute_macro(nb)
    nn = next_macro_constraint(row, col, nb, nm)
    return _opponent_has_immediate_macro_win(nb, nm, nn, opp)


def _forced_move(moves, board, macro, player):
    """
    Retourne immediatement un coup force sans lancer minimax :
    1. Coup qui gagne la partie macro (victoire immediate).
    2. Coup qui bloque la victoire macro adverse au coup suivant (2-en-ligne).
    3. Coup qui gagne un morpion coupant une ligne naissante adverse (1-en-ligne)
       sur une case strategique (centre ou coin macro), uniquement si libre.
    Retourne None si aucun coup force trouve.
    """
    opp = O if player == X else X
    block_2 = None   # (risk, move) pour bloquer 2-en-ligne adverse

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

        if _gives_opponent_immediate_macro_win(row, col, board, macro, player):
            continue

        nb = apply_move(board, row, col, player)
        nm = compute_macro(nb)
        nn = next_macro_constraint(row, col, nb, nm)
        reply_risk = _reply_tactical_risk(nb, nm, nn, player)

        for line in LINES_3x3:
            if (mr, mc) not in line:
                continue
            vals = [macro[a][b] for a, b in line]
            # Bloquer 2-en-ligne adverse
            if vals.count(opp) == 2 and vals.count(EMPTY) == 1:
                candidate = (reply_risk, (row, col))
                if block_2 is None or candidate < block_2:
                    block_2 = candidate

    if block_2 is not None:
        return block_2[1]
    return None


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

    # Si la TT propose un bon coup, on le teste en premier.
    tt_entry = _tt.get(tt_key(h, next_macro))
    if tt_entry and tt_entry[3] in moves:
        moves.remove(tt_entry[3])
        moves.insert(0, tt_entry[3])

    for row, col in moves:
        nh = h ^ ZOBRIST[ai_player][row][col]
        nb = apply_move(board, row, col, ai_player)
        nm = compute_macro(nb)
        nn = next_macro_constraint(row, col, nb, nm)
        val = minimax(nb, depth-1, -math.inf, math.inf, False, ai_player, nn, nm, nh)
        if val > best_val:
            best_val  = val
            best_move = (row, col)

    return best_move


def check_game_result(board, macro=None):
    if macro is None:
        macro = compute_macro(board)
    w = check_winner_3x3(macro)
    if w != EMPTY:
        return True, w
    for mr in range(3):
        for mc in range(3):
            if is_local_available(board, macro, mr, mc):
                return False, 0
    x_cnt = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == X)
    o_cnt = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == O)
    if x_cnt > o_cnt:
        return True, X
    if o_cnt > x_cnt:
        return True, O
    return True, 0


def evaluate_legacy(board, player, macro=None):
    """Wrapper pour compatibilite avec les logs (juste un score d'apercu)."""
    state = GameState(board=board, side=player)
    return evaluate(state, player)


# ---------------------------------------------------------------------------
# Ecran de resultats
# ---------------------------------------------------------------------------

def show_result(board, winner, human, ai):
    os.system('cls' if os.name == 'nt' else 'clear')
    macro = compute_macro(board)

    x_boards = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == X)
    o_boards = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == O)
    player_boards = x_boards if human == X else o_boards
    ai_boards = x_boards if ai == X else o_boards

    if winner == human:
        title = "VICTOIRE"
        subtitle = f"Vous ({SYMBOL[human]}) avez gagne la partie !"
    elif winner != 0:
        title = "DEFAITE"
        subtitle = f"L'IA ({SYMBOL[ai]}) a gagne la partie."
    else:
        title = "MATCH NUL"
        subtitle = "Egalite parfaite !"

    print()
    print("  ========================================")
    print(f"                 {title}")
    print("  ========================================")
    print(f"  {subtitle}")
    print()
    print("  Morpions remportes")
    print(f"  - Vous ({SYMBOL[human]}) : {player_boards}")
    print(f"  - IA   ({SYMBOL[ai]}) : {ai_boards}")
    print()
    print("  Vue finale macro")

    sym_m = {X: 'X', O: 'O', EMPTY: '.'}
    for mr in range(3):
        if mr > 0:
            print("    ---+---+---")
        print("    " + " | ".join(sym_m[macro[mr][mc]] for mc in range(3)))
    print()


# ---------------------------------------------------------------------------
# Tour humain
# ---------------------------------------------------------------------------

def human_turn(board, next_macro, player):
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
# Logging
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

    while True:
        c = input("  Qui commence ? [j=Joueur / i=IA] : ").strip().lower()
        if c in ('j', 'joueur'):
            human = X
            ai = O
            print("  Le joueur commence avec les X.")
            break
        elif c in ('i', 'ia'):
            human = O
            ai = X
            print("  L'IA commence avec les X.")
            break
        else:
            print("  -> Entrez 'j' ou 'i'.")

    print()

    log_event("=" * 60)
    log_event(f"PARTIE  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_event(f"Joueur={SYMBOL[human]} (commence={'oui' if human==X else 'non'})  IA={SYMBOL[ai]}")
    log_event("=" * 60)
    move_num = 0

    board = create_board()
    next_macro = None
    last_move = None
    current = X

    # Vide la TT au debut d'une nouvelle partie
    tt_clear()

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
            board_after = apply_move(board, row, col, ai)
            macro_after = compute_macro(board_after)
            next_after = next_macro_constraint(row, col, board_after, macro_after)
            score_after = evaluate(board_after, ai, macro_after, next_after, human)
            print(f"  >> IA joue en (col {col+1}, ligne {row+1})  [{elapsed:.2f}s]")
            log_event(f"Coup {move_num:>3} | IA     ({SYMBOL[ai]}) | col {col+1}, ligne {row+1} | contrainte={constraint_str} | {elapsed:.2f}s | score_avant={score_before:+d} | score_apres={score_after:+d}")

        board = apply_move(board, row, col, current)
        last_move = (row, col)
        new_macro = compute_macro(board)

        # Petit log pratique pour voir quand un morpion local est gagne.
        mr_p, mc_p = get_macro_pos(row, col)
        if new_macro[mr_p][mc_p] == current:
            macro_line_count = sum(
                1 for line in LINES_3x3
                if (mr_p, mc_p) in line and all(new_macro[a][b] == current for a, b in line)
            )
            log_event(f"       -> Morpion local ({mc_p+1},{mr_p+1}) remporte par {SYMBOL[current]}"
                      + (" => ALIGNEMENT MACRO !" if macro_line_count > 0 else ""))

        next_macro = next_macro_constraint(row, col, board, new_macro)
        current = O if current == X else X

    # Ecran de resultats.
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
# IA vs IA
# ---------------------------------------------------------------------------

def ai_vs_ai():
    print()
    print("=" * 40)
    print("   Mode IA vs IA")
    print("=" * 40)
    print(f"  Budget temps par coup : {TIME_LIMIT}s")
    print()

    auto_continue = input("  Bypass des pauses entre les coups ? (o/n) : ").strip().lower()
    auto_continue = auto_continue in ('o', 'oui', 'y', 'yes')
    print("  Mode automatique active." if auto_continue else "  Mode pas-a-pas active.")

    diversify = input("  Diversifier un peu les ouvertures ? (o/n) : ").strip().lower()
    diversify = diversify in ('o', 'oui', 'y', 'yes')
    if diversify:
        print("  Diversification active : choix aleatoire parmi les bons coups des 8 premiers tours.")
    else:
        print("  Diversification desactivee : partie deterministe.")
    print()

    log_event("=" * 60)
    log_event(f"IA VS IA  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_event(f"Budget temps : {TIME_LIMIT}s par coup")
    log_event(f"Mode automatique : {'oui' if auto_continue else 'non'}")
    log_event(f"Diversification ouvertures : {'oui' if diversify else 'non'}")
    log_event("=" * 60)

    board = create_board()
    next_macro = None
    last_move = None
    current = X
    move_count = 0
    history = []
    total_time = {X: 0.0, O: 0.0}

    tt_clear()

    while True:
        display_board(board, next_macro, last_move)
        macro = compute_macro(board)
        x_boards = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == X)
        o_boards = sum(1 for mr in range(3) for mc in range(3) if macro[mr][mc] == O)
        done, winner = check_game_result(board, macro)
        if done:
            break

        print("  ----------------------------------------")
        print(f"  Coup {move_count+1:<3} | IA-X: {x_boards} morpion(s) | IA-O: {o_boards} morpion(s)")
        print(f"  Temps total | IA-X: {total_time[X]:.1f}s | IA-O: {total_time[O]:.1f}s")
        print("  ----------------------------------------")
        print()

        if next_macro is not None:
            mr, mc = next_macro
            print(f"  Contrainte : IA-{SYMBOL[current]} doit jouer dans le morpion (col {mc+1}, ligne {mr+1})")
        else:
            print(f"  IA-{SYMBOL[current]} est libre de jouer n'importe ou.")
        print()

        print(f"  IA-{SYMBOL[current]} reflechit (budget {TIME_LIMIT}s)...", end="", flush=True)
        t0 = time.time()
        if diversify and move_count < 8:
            opening_moves = get_valid_moves(board, next_macro, macro)
            opening_moves.sort(key=lambda m: _move_priority(m, board, current, macro))
            pool = opening_moves[:min(5, len(opening_moves))]
            move = random.choice(pool) if pool else None
        else:
            move = ai_choose_move_timed(board, next_macro, current)
        elapsed = time.time() - t0
        total_time[current] += elapsed
        print(f" {elapsed:.2f}s")

        if move is None:
            print("  Plus de coups !")
            break

        row, col = move
        score = evaluate(board, current, macro, next_macro, current)
        board_after = apply_move(board, row, col, current)
        macro_after = compute_macro(board_after)
        next_after = next_macro_constraint(row, col, board_after, macro_after)
        score_after = evaluate(board_after, current, macro_after, next_after, O if current == X else X)
        constraint_str = f"morpion ({next_macro[1]+1},{next_macro[0]+1})" if next_macro else "libre"
        print(f"  >> IA-{SYMBOL[current]} joue en (col {col+1}, ligne {row+1})")
        print(f"     Score heuristique avant coup : {score:+d}")
        print(f"     Score heuristique apres coup : {score_after:+d}")
        log_event(f"Coup {move_count+1:>3} | IA-{SYMBOL[current]} | col {col+1}, ligne {row+1} | contrainte={constraint_str} | {elapsed:.2f}s | score_avant={score:+d} | score_apres={score_after:+d}")

        board = apply_move(board, row, col, current)
        last_move = (row, col)
        new_macro = compute_macro(board)

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
        current = O if current == X else X
        move_count += 1

        if not auto_continue:
            print()
            input("  [Entree pour continuer]")

    # Ecran de resultats IA vs IA.
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
    print("  " + "=" * 42)
    if winner == X:
        print("        *** IA-X remporte la partie ! ***")
    elif winner == O:
        print("        *** IA-O remporte la partie ! ***")
    else:
        print("              *** MATCH NUL ***")
    print("  " + "=" * 42)
    print()
    print(f"  Morpions IA-X : {x_boards}  |  Morpions IA-O : {o_boards}")
    print(f"  Total de coups joues : {move_count}")
    print(f"  Temps total IA-X : {total_time[X]:.1f}s  |  Temps total IA-O : {total_time[O]:.1f}s")
    if move_count > 0:
        print(f"  Temps moyen/coup  IA-X : {total_time[X]/max(1, sum(1 for h in history if h[0]=='X')):.2f}s"
              f"  |  IA-O : {total_time[O]/max(1, sum(1 for h in history if h[0]=='O')):.2f}s")
    print()
    print("  Historique des coups :")
    print("  " + "-" * 38)
    for i, (sym, c, r, t) in enumerate(history):
        print(f"  Coup {i+1:>2} | IA-{sym} | col {c}, ligne {r} | {t:.2f}s")
    print()


# ---------------------------------------------------------------------------
# Analyse des logs
# ---------------------------------------------------------------------------

LOG_MOVE_RE = re.compile(
    r"Coup\s+(\d+)\s+\|\s+(IA-X|IA-O|IA\s+\([XO]\)|JOUEUR\s+\([XO]\))"
    r"\s+\|\s+col\s+(\d+), ligne\s+(\d+)"
)
LOG_SCORE_RE = re.compile(r"score_avant=([+-]?\d+)\s+\|\s+score_apres=([+-]?\d+)")


def _parse_logged_player(label):
    if "X" in label:
        return X
    if "O" in label:
        return O
    return EMPTY


def _parse_log_games(path=TEST_LOG_FILE):
    """Parse les parties du log en sequences de coups."""
    games = []
    current = None
    if not os.path.exists(path):
        return games

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("IA VS IA") or line.startswith("PARTIE"):
                if current and current["moves"]:
                    games.append(current)
                current = {"header": line, "moves": []}
                continue
            if current is None:
                continue

            m = LOG_MOVE_RE.search(line)
            if not m:
                continue

            move_num = int(m.group(1))
            player = _parse_logged_player(m.group(2))
            col = int(m.group(3))
            row = int(m.group(4))
            score_match = LOG_SCORE_RE.search(line)
            score_before = int(score_match.group(1)) if score_match else None
            score_after = int(score_match.group(2)) if score_match else None
            current["moves"].append({
                "num": move_num,
                "player": player,
                "row": row - 1,
                "col": col - 1,
                "score_before": score_before,
                "score_after": score_after,
            })

    if current and current["moves"]:
        games.append(current)
    return games


def _format_move(move):
    row, col = move
    return f"col {col+1}, ligne {row+1}"


def _macro_compact(macro):
    return "/".join("".join(SYMBOL[v] for v in row) for row in macro)


def _analyze_alternatives(board, next_macro, player, played_move, limit=5):
    """Retourne les meilleures alternatives immediates selon evaluate apres coup."""
    macro = compute_macro(board)
    opp = O if player == X else X
    rows = []
    for move in get_valid_moves(board, next_macro, macro):
        row, col = move
        nb = apply_move(board, row, col, player)
        nm = compute_macro(nb)
        nn = next_macro_constraint(row, col, nb, nm)
        after = evaluate(nb, player, nm, nn, opp)
        risk = _reply_tactical_risk(nb, nm, nn, player)
        rows.append({
            "move": move,
            "played": move == played_move,
            "score_after": after,
            "reply_risk": risk,
            "next_macro": nn,
            "macro": _macro_compact(nm),
        })
    rows.sort(key=lambda x: x["score_after"], reverse=True)
    return rows[:limit], next((x for x in rows if x["played"]), None)


def analyze_game_log(path=TEST_LOG_FILE, drop_threshold=3_000):
    """
    Rejoue le log et signale les coups ou score_apres chute fortement.
    Utile pour verifier si le coup joue etait le moins mauvais ou une erreur.
    """
    games = _parse_log_games(path)
    if not games:
        print(f"  Aucun log exploitable trouve dans {path}.")
        return

    print()
    print("=" * 60)
    print("  ANALYSE DES COUPS CATASTROPHIQUES")
    print("=" * 60)
    print(f"  Seuil de chute : {drop_threshold} points")
    print()

    total_alerts = 0
    for game_idx, game in enumerate(games, 1):
        board = create_board()
        next_macro = None
        alerts = []

        for info in game["moves"]:
            player = info["player"]
            move = (info["row"], info["col"])
            macro = compute_macro(board)
            valid = get_valid_moves(board, next_macro, macro)
            if move not in valid:
                print(f"  Partie {game_idx}, coup {info['num']}: coup invalide dans le log, ignore.")
                continue

            score_before = info["score_before"]
            score_after = info["score_after"]
            if score_before is not None and score_after is not None:
                drop = score_before - score_after
                if drop >= drop_threshold:
                    top, played = _analyze_alternatives(board, next_macro, player, move)
                    best = top[0] if top else None
                    alerts.append((info, drop, played, best, top, _macro_compact(macro), next_macro))

            board = apply_move(board, move[0], move[1], player)
            new_macro = compute_macro(board)
            next_macro = next_macro_constraint(move[0], move[1], board, new_macro)

        if not alerts:
            continue

        total_alerts += len(alerts)
        print(f"  Partie {game_idx}: {game['header']}")
        for info, drop, played, best, top, macro_before, constraint in alerts:
            player_sym = SYMBOL[info["player"]]
            print(f"    Coup {info['num']} IA-{player_sym}: {_format_move((info['row'], info['col']))}")
            print(f"      chute={drop:+d} | macro={macro_before} | contrainte={constraint}")
            if played is not None:
                print(f"      joue: score_apres={played['score_after']:+d}, risk_reply={played['reply_risk']:+d}, next={played['next_macro']}")
            if best is not None and (played is None or best["move"] != played["move"]):
                gain = best["score_after"] - (played["score_after"] if played else info["score_after"])
                print(f"      meilleure immediate: {_format_move(best['move'])}, score_apres={best['score_after']:+d}, gain={gain:+d}, risk_reply={best['reply_risk']:+d}")
            print("      top alternatives:")
            for alt in top:
                tag = "*" if alt["played"] else " "
                print(f"       {tag} {_format_move(alt['move'])}: score={alt['score_after']:+d}, risk={alt['reply_risk']:+d}, next={alt['next_macro']}")
        print()

    if total_alerts == 0:
        print("  Aucun coup catastrophique detecte avec ce seuil.")
    else:
        print(f"  Total alertes : {total_alerts}")
    print()


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("  1. Joueur vs IA")
    print("  2. IA vs IA (demonstration)")
    print("  3. Analyser game_log.txt")
    while True:
        choice = input("  Votre choix : ").strip()
        if choice == '1':
            while play_game():
                pass
            break
        elif choice == '2':
            ai_vs_ai()
            break
        elif choice == '3':
            analyze_game_log()
            break
        else:
            print("  -> Entrez 1, 2 ou 3.")
