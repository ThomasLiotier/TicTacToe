#!/usr/bin/env python3
"""
Ultimate Tic-Tac-Toe - port Python du moteur alpha-beta de
zesardine/UltimateTicTacToeAI.

Fichier autonome: ne depend pas de ultimate_tictactoe.py.
Log separe: game_log_zesardine.txt.

Source d'inspiration:
https://github.com/zesardine/UltimateTicTacToeAI/blob/main/tmp.js
"""

import math
import os
import sys
import time
from datetime import datetime

if os.name == "nt":
    os.system("chcp 65001 > nul")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


EMPTY = 0
X = 1
O = -1

SYMBOL = {EMPTY: ".", X: "X", O: "O"}
PLAYER = X
AI = O

LOG_FILE = "game_log_zesardine.txt"

LINES = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
)

LOCAL_WEIGHTS = (1.4, 1.0, 1.4, 1.0, 1.75, 1.0, 1.4, 1.0, 1.4)
SQUARE_WEIGHTS = (0.2, 0.17, 0.2, 0.17, 0.22, 0.17, 0.2, 0.17, 0.2)

RUNS = 0
AI_TIME_LIMIT = 10.0
AI_DEADLINE = None


def create_boards():
    return [[EMPTY for _ in range(9)] for _ in range(9)]


def clone_boards(boards):
    return [b[:] for b in boards]


def check_win_condition(cells):
    for player in (X, O):
        target = player * 3
        for line in LINES:
            if cells[line[0]] + cells[line[1]] + cells[line[2]] == target:
                return player
    return EMPTY


def is_full(cells):
    return EMPTY not in cells


def is_local_playable(boards, board_idx):
    return check_win_condition(boards[board_idx]) == EMPTY and not is_full(boards[board_idx])


def normalize_current_board(boards, current_board):
    if current_board == -1:
        return -1
    if not is_local_playable(boards, current_board):
        return -1
    return current_board


def macro_board(boards):
    return [check_win_condition(boards[i]) for i in range(9)]


def count_playable_squares(boards):
    total = 0
    for b in range(9):
        if check_win_condition(boards[b]) == EMPTY:
            total += sum(1 for v in boards[b] if v == EMPTY)
    return total


def global_to_local(row, col):
    board_idx = (row // 3) * 3 + (col // 3)
    square_idx = (row % 3) * 3 + (col % 3)
    return board_idx, square_idx


def local_to_global(board_idx, square_idx):
    row = (board_idx // 3) * 3 + (square_idx // 3)
    col = (board_idx % 3) * 3 + (square_idx % 3)
    return row, col


def valid_moves(boards, current_board):
    current_board = normalize_current_board(boards, current_board)
    moves = []
    if current_board != -1:
        for square in range(9):
            if boards[current_board][square] == EMPTY:
                moves.append((current_board, square))
        return moves

    for board_idx in range(9):
        if not is_local_playable(boards, board_idx):
            continue
        for square in range(9):
            if boards[board_idx][square] == EMPTY:
                moves.append((board_idx, square))
    return moves


def apply_move_inplace(boards, board_idx, square_idx, player):
    boards[board_idx][square_idx] = player


def next_board_after(square_idx, boards):
    return normalize_current_board(boards, square_idx)


def game_result(boards):
    macro = macro_board(boards)
    winner = check_win_condition(macro)
    if winner != EMPTY:
        return True, winner
    if not valid_moves(boards, -1):
        x_count = sum(1 for v in macro if v == X)
        o_count = sum(1 for v in macro if v == O)
        if x_count > o_count:
            return True, X
        if o_count > x_count:
            return True, O
        return True, EMPTY
    return False, EMPTY


def line_has_sum(cells, target):
    return any(cells[a] + cells[b] + cells[c] == target for a, b, c in LINES)


def has_blocked_pair_pattern(cells, a):
    for i, j, k in LINES:
        vals = (cells[i], cells[j], cells[k])
        if vals[0] + vals[1] == 2 * a and vals[2] == -a:
            return True
        if vals[1] + vals[2] == 2 * a and vals[0] == -a:
            return True
        if vals[0] + vals[2] == 2 * a and vals[1] == -a:
            return True
    return False


def real_evaluate_square(cells):
    """Evaluation locale du JS, positive pour O/AI, negative pour X/player."""
    evaluation = 0.0
    for idx, value in enumerate(cells):
        evaluation -= value * SQUARE_WEIGHTS[idx]

    if any(cells[a] + cells[b] + cells[c] == 2 for a, b, c in LINES[:3]):
        evaluation -= 6
    if any(cells[a] + cells[b] + cells[c] == 2 for a, b, c in LINES[3:6]):
        evaluation -= 6
    if any(cells[a] + cells[b] + cells[c] == 2 for a, b, c in LINES[6:]):
        evaluation -= 7
    if has_blocked_pair_pattern(cells, O):
        evaluation -= 9

    if any(cells[a] + cells[b] + cells[c] == -2 for a, b, c in LINES[:3]):
        evaluation += 6
    if any(cells[a] + cells[b] + cells[c] == -2 for a, b, c in LINES[3:6]):
        evaluation += 6
    if any(cells[a] + cells[b] + cells[c] == -2 for a, b, c in LINES[6:]):
        evaluation += 7
    if has_blocked_pair_pattern(cells, X):
        evaluation += 9

    evaluation -= check_win_condition(cells) * 12
    return evaluation


def evaluate_game(position, current_board):
    """Evaluation globale du JS, positive pour O/AI."""
    evaluation = 0.0
    main_board = []
    for idx in range(9):
        local_eval = real_evaluate_square(position[idx])
        evaluation += local_eval * 1.5 * LOCAL_WEIGHTS[idx]
        if idx == current_board:
            evaluation += local_eval * LOCAL_WEIGHTS[idx]
        local_winner = check_win_condition(position[idx])
        evaluation -= local_winner * LOCAL_WEIGHTS[idx]
        main_board.append(local_winner)

    evaluation -= check_win_condition(main_board) * 5000
    evaluation += real_evaluate_square(main_board) * 150
    return evaluation


def evaluate_pos(local_board, square):
    """Evaluation du JS pour departager les cases d'un morpion local."""
    local_board[square] = AI
    evaluation = SQUARE_WEIGHTS[square]

    if line_has_sum(local_board, -2):
        evaluation += 1
    if line_has_sum(local_board, -3):
        evaluation += 5

    local_board[square] = PLAYER
    if line_has_sum(local_board, 3):
        evaluation += 2

    local_board[square] = AI
    evaluation -= check_win_condition(local_board) * 15
    local_board[square] = EMPTY
    return evaluation


def sign(x):
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def one_board_minimax(position, depth, alpha, beta, maximizing_player):
    """Fonction JS d'etude sur un seul morpion, conservee pour parite."""
    global RUNS
    RUNS += 1

    winner = check_win_condition(position)
    if winner != EMPTY:
        if depth > 0:
            return -winner * 10 - sign(-winner) * depth * 0.5
        return -winner * 10 - sign(-winner) * depth * 0.1

    count = sum(1 for value in position if value != EMPTY)
    if count == 9 or depth == 1000:
        return 0

    if maximizing_player:
        max_eval = -math.inf
        for square in range(9):
            if position[square] == EMPTY:
                position[square] = AI
                score = one_board_minimax(position, depth + 1, alpha, beta, False)
                position[square] = EMPTY
                max_eval = max(max_eval, score)
                alpha = max(alpha, score)
                if beta <= alpha:
                    break
        return max_eval

    min_eval = math.inf
    for square in range(9):
        if position[square] == EMPTY:
            position[square] = PLAYER
            score = one_board_minimax(position, depth + 1, alpha, beta, True)
            position[square] = EMPTY
            min_eval = min(min_eval, score)
            beta = min(beta, score)
            if beta <= alpha:
                break
    return min_eval


def pick_board(position, maximizing_player):
    """Ancienne fonction JS de selection de morpion, non utilisee par l'IA finale."""
    best_score = -math.inf
    if not maximizing_player:
        best_score = math.inf
    remembered = 0

    for board_idx in range(9):
        if check_win_condition(position[board_idx]) == EMPTY:
            for square in range(9):
                if position[board_idx][square] == EMPTY:
                    position[board_idx][square] = AI if maximizing_player else PLAYER
                    score = evaluate_game(position, square) * 50
                    position[board_idx][square] = EMPTY
                    score += real_evaluate_square(position[square]) * 12
                    if (maximizing_player and score > best_score) or (
                        not maximizing_player and score < best_score
                    ):
                        best_score = score
                        remembered = board_idx
    return remembered


def minimax(position, board_to_play_on, depth, alpha, beta, maximizing_player):
    """Alpha-beta porte depuis tmp.js, avec le meme ordre de parcours."""
    global RUNS
    RUNS += 1

    tmp_play = -1
    calc_eval = evaluate_game(position, board_to_play_on)
    if AI_DEADLINE is not None and time.perf_counter() >= AI_DEADLINE:
        return {"mE": calc_eval, "tP": tmp_play}
    if depth <= 0 or abs(calc_eval) > 5000:
        return {"mE": calc_eval, "tP": tmp_play}

    board_to_play_on = normalize_current_board(position, board_to_play_on)

    if maximizing_player:
        max_eval = -math.inf
        for board_idx in range(9):
            evalut = -math.inf
            if board_to_play_on == -1:
                for square in range(9):
                    if check_win_condition(position[board_idx]) == EMPTY:
                        if position[board_idx][square] == EMPTY:
                            position[board_idx][square] = AI
                            evalut = minimax(
                                position, square, depth - 1, alpha, beta, False
                            )["mE"]
                            position[board_idx][square] = EMPTY
                        if evalut > max_eval:
                            max_eval = evalut
                            tmp_play = board_idx
                        alpha = max(alpha, evalut)
                if beta <= alpha:
                    break
            else:
                if position[board_to_play_on][board_idx] == EMPTY:
                    position[board_to_play_on][board_idx] = AI
                    evalut = minimax(position, board_idx, depth - 1, alpha, beta, False)
                    position[board_to_play_on][board_idx] = EMPTY
                    score = evalut["mE"]
                    if score > max_eval:
                        max_eval = score
                        tmp_play = evalut["tP"]
                    alpha = max(alpha, score)
                else:
                    alpha = math.nan
                if beta <= alpha:
                    break
        return {"mE": max_eval, "tP": tmp_play}

    min_eval = math.inf
    for board_idx in range(9):
        evalua = math.inf
        if board_to_play_on == -1:
            for square in range(9):
                if check_win_condition(position[board_idx]) == EMPTY:
                    if position[board_idx][square] == EMPTY:
                        position[board_idx][square] = PLAYER
                        evalua = minimax(
                            position, square, depth - 1, alpha, beta, True
                        )["mE"]
                        position[board_idx][square] = EMPTY
                    if evalua < min_eval:
                        min_eval = evalua
                        tmp_play = board_idx
                    beta = min(beta, evalua)
            if beta <= alpha:
                break
        else:
            if position[board_to_play_on][board_idx] == EMPTY:
                position[board_to_play_on][board_idx] = PLAYER
                evalua = minimax(position, board_idx, depth - 1, alpha, beta, True)
                position[board_to_play_on][board_idx] = EMPTY
                score = evalua["mE"]
                if score < min_eval:
                    min_eval = score
                    tmp_play = evalua["tP"]
                beta = min(beta, score)
            else:
                beta = math.nan
            if beta <= alpha:
                break
    return {"mE": min_eval, "tP": tmp_play}


def oriented_boards(boards, ai_player):
    """Convertit le joueur courant en O/AI=-1 pour reutiliser le moteur JS."""
    if ai_player == O:
        return clone_boards(boards), 1
    return [[-cell for cell in board] for board in boards], -1


def choose_ai_move(boards, current_board, current_player, js_moves):
    """Choisit un coup avec le protocole de recherche du JS."""
    global AI_DEADLINE, RUNS
    oriented, sign = oriented_boards(boards, current_player)
    local_current = normalize_current_board(oriented, current_board)
    remaining = count_playable_squares(oriented)
    RUNS = 0
    AI_DEADLINE = time.perf_counter() + AI_TIME_LIMIT

    if local_current == -1:
        if js_moves < 10:
            depth = min(4, remaining)
        elif js_moves < 18:
            depth = min(5, remaining)
        else:
            depth = min(6, remaining)
        picked = minimax(oriented, -1, depth, -math.inf, math.inf, True)["tP"]
        if picked == -1 or not is_local_playable(oriented, picked):
            playable = [b for b in range(9) if is_local_playable(oriented, b)]
            picked = playable[0] if playable else -1
        local_current = picked

    if local_current == -1:
        AI_DEADLINE = None
        return None, 0.0, RUNS

    legal_squares = [i for i, v in enumerate(oriented[local_current]) if v == EMPTY]
    if not legal_squares:
        score = evaluate_game(oriented, local_current)
        AI_DEADLINE = None
        return None, score, RUNS

    best_move = legal_squares[0]
    best_scores = [-math.inf for _ in range(9)]

    for square in legal_squares:
        best_scores[square] = evaluate_pos(oriented[local_current], square) * 45

    for square in legal_squares:
        if time.perf_counter() >= AI_DEADLINE:
            break
        oriented[local_current][square] = AI
        if js_moves < 20:
            depth = min(5, remaining)
        elif js_moves < 32:
            depth = min(6, remaining)
        else:
            depth = min(7, remaining)
        result = minimax(oriented, square, depth, -math.inf, math.inf, False)
        oriented[local_current][square] = EMPTY
        best_scores[square] += result["mE"]

    for square in range(9):
        if best_scores[square] > best_scores[best_move]:
            best_move = square

    AI_DEADLINE = None
    return (local_current, best_move), best_scores[best_move], RUNS


def display_board(boards, current_board=-1, last_move=None):
    os.system("cls" if os.name == "nt" else "clear")
    macro = macro_board(boards)
    print()
    print("  ========================================")
    print("      ULTIMATE TIC-TAC-TOE - ZESARDINE AI")
    print("  ========================================")
    print()
    print("             1   2   3   4   5   6   7   8   9")
    print("          +-----------+-----------+-----------+")
    for row in range(9):
        if row > 0 and row % 3 == 0:
            print("          +-----------+-----------+-----------+")
        line = f"  ligne {row+1:2} |"
        for col in range(9):
            board_idx, square_idx = global_to_local(row, col)
            winner = macro[board_idx]
            value = winner if winner != EMPTY else boards[board_idx][square_idx]
            text = SYMBOL[value]
            if last_move == (board_idx, square_idx):
                cell = f"({text})"
            else:
                cell = f" {text} "
            line += cell
            if col % 3 == 2:
                line += "|"
        print(line)
    print("          +-----------+-----------+-----------+")
    print()
    print("  Vue macro:")
    for r in range(3):
        print("   " + " ".join(SYMBOL[macro[r * 3 + c]] for c in range(3)))
    print()
    current_board = normalize_current_board(boards, current_board)
    if current_board == -1:
        print("  >>> Libre de jouer dans n'importe quel morpion <<<")
    else:
        print(f"  >>> Morpion impose : colonne {current_board % 3 + 1}, ligne {current_board // 3 + 1} <<<")
    print()


def log_event(message):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def ask_human_move(boards, current_board, player):
    moves = valid_moves(boards, current_board)
    while True:
        raw = input(f"  [{SYMBOL[player]}] Colonne et ligne (ex: 5 3) : ").strip()
        parts = raw.split()
        if len(parts) != 2:
            print("  -> Format invalide.")
            continue
        try:
            col = int(parts[0]) - 1
            row = int(parts[1]) - 1
        except ValueError:
            print("  -> Entrez deux nombres.")
            continue
        if not (0 <= row < 9 and 0 <= col < 9):
            print("  -> Coordonnees hors limites.")
            continue
        move = global_to_local(row, col)
        if move not in moves:
            print("  -> Coup invalide pour la contrainte actuelle.")
            continue
        return move


def log_local_win(prefix, boards, old_macro, board_idx, player):
    new_macro = macro_board(boards)
    if old_macro[board_idx] == EMPTY and new_macro[board_idx] == player:
        macro_winner = check_win_condition(new_macro)
        msg = f"       -> Morpion local ({board_idx % 3 + 1},{board_idx // 3 + 1}) remporte par {prefix}"
        if macro_winner == player:
            msg += " => ALIGNEMENT MACRO !"
        log_event(msg)


def play_game():
    boards = create_boards()
    current_board = -1
    current = X
    turn_number = 0
    js_moves = 0
    last_move = None

    print()
    print("  Qui commence ?")
    first = input("  [j=Joueur / i=IA] : ").strip().lower()
    if first in ("i", "ia"):
        human = O
        ai_player = X
    else:
        human = X
        ai_player = O

    log_event("=" * 60)
    log_event(f"PARTIE ZESARDINE {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_event(f"Joueur={SYMBOL[human]}  IA={SYMBOL[ai_player]}")
    log_event("=" * 60)

    while True:
        display_board(boards, current_board, last_move)
        done, winner = game_result(boards)
        if done:
            break

        turn_number += 1
        constraint = "libre" if normalize_current_board(boards, current_board) == -1 else (
            f"morpion ({current_board % 3 + 1},{current_board // 3 + 1})"
        )
        old_macro = macro_board(boards)

        if current == human:
            print(f"  Votre tour ({SYMBOL[human]})")
            board_idx, square_idx = ask_human_move(boards, current_board, human)
            log_event(
                f"Coup {turn_number:>3} | JOUEUR ({SYMBOL[human]}) | "
                f"col {local_to_global(board_idx, square_idx)[1]+1}, ligne {local_to_global(board_idx, square_idx)[0]+1} | "
                f"contrainte={constraint}"
            )
        else:
            print(f"  Tour de l'IA ({SYMBOL[ai_player]})...")
            t0 = time.time()
            move, score, runs = choose_ai_move(boards, current_board, ai_player, js_moves)
            elapsed = time.time() - t0
            if move is None:
                break
            board_idx, square_idx = move
            row, col = local_to_global(board_idx, square_idx)
            print(f"  >> IA joue en (col {col+1}, ligne {row+1}) [{elapsed:.2f}s]")
            log_event(
                f"Coup {turn_number:>3} | IA     ({SYMBOL[ai_player]}) | col {col+1}, ligne {row+1} | "
                f"contrainte={constraint} | {elapsed:.2f}s | score={score:+.2f} | runs={runs}"
            )

        apply_move_inplace(boards, board_idx, square_idx, current)
        if current == human:
            js_moves += 1
        log_local_win(SYMBOL[current], boards, old_macro, board_idx, current)
        last_move = (board_idx, square_idx)
        current_board = next_board_after(square_idx, boards)
        current = O if current == X else X

    display_board(boards, current_board, last_move)
    _, winner = game_result(boards)
    print_result(winner, "joueur" if winner == human else "IA")
    log_result(boards, winner, human, ai_player)


def print_result(winner, winner_label=""):
    print()
    if winner == EMPTY:
        print("  RESULTAT : match nul")
    else:
        print(f"  RESULTAT : victoire {winner_label} ({SYMBOL[winner]})")
    print()


def log_result(boards, winner, human=None, ai_player=None):
    macro = macro_board(boards)
    x_count = sum(1 for v in macro if v == X)
    o_count = sum(1 for v in macro if v == O)
    log_event("-" * 60)
    if winner == EMPTY:
        log_event("RESULTAT : NUL")
    elif human is not None and winner == human:
        log_event(f"RESULTAT : VICTOIRE du joueur ({SYMBOL[winner]})")
    elif ai_player is not None and winner == ai_player:
        log_event(f"RESULTAT : VICTOIRE de l'IA ({SYMBOL[winner]})")
    else:
        log_event(f"RESULTAT : VICTOIRE IA-{SYMBOL[winner]}")
    log_event(f"Morpions X={x_count}  O={o_count}")
    log_event("=" * 60 + "\n")


def ai_vs_ai():
    boards = create_boards()
    current_board = -1
    current = X
    move_count = 0
    last_move = None
    total_time = {X: 0.0, O: 0.0}

    auto = input("  Bypass des pauses entre les coups ? (o/n) : ").strip().lower() in ("o", "oui", "y", "yes")

    log_event("=" * 60)
    log_event(f"IA VS IA ZESARDINE {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_event("Log separe du moteur porte depuis tmp.js")
    log_event("=" * 60)

    while True:
        display_board(boards, current_board, last_move)
        done, winner = game_result(boards)
        if done:
            break

        move_count += 1
        old_macro = macro_board(boards)
        constraint = "libre" if normalize_current_board(boards, current_board) == -1 else (
            f"morpion ({current_board % 3 + 1},{current_board // 3 + 1})"
        )

        print(f"  IA-{SYMBOL[current]} reflechit...")
        t0 = time.time()
        move, score, runs = choose_ai_move(boards, current_board, current, move_count)
        elapsed = time.time() - t0
        total_time[current] += elapsed
        if move is None:
            break

        board_idx, square_idx = move
        row, col = local_to_global(board_idx, square_idx)
        print(f"  >> IA-{SYMBOL[current]} joue en (col {col+1}, ligne {row+1}) [{elapsed:.2f}s]")
        log_event(
            f"Coup {move_count:>3} | IA-{SYMBOL[current]} | col {col+1}, ligne {row+1} | "
            f"contrainte={constraint} | {elapsed:.2f}s | score={score:+.2f} | runs={runs}"
        )

        apply_move_inplace(boards, board_idx, square_idx, current)
        log_local_win(f"IA-{SYMBOL[current]}", boards, old_macro, board_idx, current)
        last_move = (board_idx, square_idx)
        current_board = next_board_after(square_idx, boards)
        current = O if current == X else X

        if not auto:
            input("  [Entree pour continuer]")

    display_board(boards, current_board, last_move)
    _, winner = game_result(boards)
    print_result(winner, f"IA-{SYMBOL[winner]}" if winner != EMPTY else "")
    log_result(boards, winner)
    log_event(f"Temps total IA-X={total_time[X]:.1f}s  IA-O={total_time[O]:.1f}s")


if __name__ == "__main__":
    print()
    print("  1. Joueur vs IA")
    print("  2. IA vs IA (demonstration)")
    while True:
        choice = input("  Votre choix : ").strip()
        if choice == "1":
            play_game()
            break
        if choice == "2":
            ai_vs_ai()
            break
        print("  -> Entrez 1 ou 2.")
