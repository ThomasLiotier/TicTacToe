#!/usr/bin/env python3
"""
Compare les deux IA du projet en les faisant jouer l'une contre l'autre.

Exemples:
  python compare_ais.py
  python compare_ais.py --games 6 --time 3
  python compare_ais.py --games 2 --time 10 --log duel_log.txt
"""

import argparse
import time

import ultimate_tictactoe as classic
import ultimate_tictactoe_zesardine as zesardine


CLASSIC = "classic"
ZESARDINE = "zesardine"


def other_player(player):
    return classic.O if player == classic.X else classic.X


def symbol(player):
    return "X" if player == classic.X else "O"


def next_macro_to_z_index(next_macro):
    if next_macro is None:
        return -1
    mr, mc = next_macro
    return mr * 3 + mc


def classic_to_zesardine_boards(board):
    boards = zesardine.create_boards()
    for row in range(9):
        for col in range(9):
            board_idx = (row // 3) * 3 + (col // 3)
            square_idx = (row % 3) * 3 + (col % 3)
            if board[row][col] == classic.X:
                boards[board_idx][square_idx] = zesardine.X
            elif board[row][col] == classic.O:
                boards[board_idx][square_idx] = zesardine.O
    return boards


def player_to_zesardine(player):
    return zesardine.X if player == classic.X else zesardine.O


def choose_move(engine, board, next_macro, player, time_limit, js_moves):
    if engine == CLASSIC:
        move = classic.ai_choose_move_timed(board, next_macro, player, time_limit)
        return move, None

    old_limit = zesardine.AI_TIME_LIMIT
    zesardine.AI_TIME_LIMIT = time_limit
    try:
        zboards = classic_to_zesardine_boards(board)
        zcurrent = next_macro_to_z_index(next_macro)
        zplayer = player_to_zesardine(player)
        move, score, runs = zesardine.choose_ai_move(zboards, zcurrent, zplayer, js_moves)
    finally:
        zesardine.AI_TIME_LIMIT = old_limit

    if move is None:
        return None, {"score": score, "runs": runs}
    board_idx, square_idx = move
    row, col = zesardine.local_to_global(board_idx, square_idx)
    return (row, col), {"score": score, "runs": runs}


def play_game(game_no, x_engine, o_engine, time_limit, verbose=False):
    board = classic.create_board()
    next_macro = None
    current = classic.X
    move_no = 0
    js_moves = 0
    history = []

    engines = {
        classic.X: x_engine,
        classic.O: o_engine,
    }

    while True:
        macro = classic.compute_macro(board)
        done, winner = classic.check_game_result(board, macro)
        if done:
            return {
                "game": game_no,
                "x_engine": x_engine,
                "o_engine": o_engine,
                "winner": winner,
                "moves": move_no,
                "history": history,
                "macro": macro,
            }

        engine = engines[current]
        legal = classic.get_valid_moves(board, next_macro, macro)
        start = time.perf_counter()
        move, extra = choose_move(engine, board, next_macro, current, time_limit, js_moves)
        elapsed = time.perf_counter() - start

        if move not in legal:
            winner = other_player(current)
            history.append({
                "move_no": move_no + 1,
                "engine": engine,
                "player": current,
                "move": move,
                "elapsed": elapsed,
                "invalid": True,
                "extra": extra,
            })
            return {
                "game": game_no,
                "x_engine": x_engine,
                "o_engine": o_engine,
                "winner": winner,
                "moves": move_no,
                "history": history,
                "macro": macro,
                "invalid_by": engine,
            }

        row, col = move
        board = classic.apply_move(board, row, col, current)
        macro = classic.compute_macro(board)
        next_macro = classic.next_macro_constraint(row, col, board, macro)
        move_no += 1

        history.append({
            "move_no": move_no,
            "engine": engine,
            "player": current,
            "move": move,
            "elapsed": elapsed,
            "invalid": False,
            "extra": extra,
        })

        if verbose:
            print(
                f"  {move_no:>2}. {engine:<9} {symbol(current)} -> "
                f"col {col + 1}, ligne {row + 1} [{elapsed:.2f}s]"
            )

        if engine == ZESARDINE:
            js_moves += 1
        current = other_player(current)


def winner_engine(result):
    winner = result["winner"]
    if winner == classic.X:
        return result["x_engine"]
    if winner == classic.O:
        return result["o_engine"]
    return None


def macro_counts(macro):
    x_count = sum(1 for row in macro for value in row if value == classic.X)
    o_count = sum(1 for row in macro for value in row if value == classic.O)
    return x_count, o_count


def format_result(result):
    winner = winner_engine(result)
    x_count, o_count = macro_counts(result["macro"])
    if winner is None:
        label = "nul"
    else:
        label = f"victoire {winner}"
    invalid = f" | coup invalide par {result['invalid_by']}" if "invalid_by" in result else ""
    return (
        f"Partie {result['game']}: X={result['x_engine']} O={result['o_engine']} -> "
        f"{label} en {result['moves']} coups | macro X={x_count} O={o_count}{invalid}"
    )


def write_log(path, results):
    with open(path, "w", encoding="utf-8") as handle:
        for result in results:
            handle.write(format_result(result) + "\n")
            for item in result["history"]:
                move = item["move"]
                if move is None:
                    move_txt = "aucun"
                else:
                    row, col = move
                    move_txt = f"col {col + 1}, ligne {row + 1}"
                extra = item["extra"] or {}
                extra_txt = ""
                if "score" in extra:
                    extra_txt = f" | score={extra['score']:+.2f} runs={extra['runs']}"
                invalid = " | INVALIDE" if item["invalid"] else ""
                handle.write(
                    f"  {item['move_no']:>2}. {item['engine']:<9} {symbol(item['player'])} "
                    f"{move_txt} | {item['elapsed']:.2f}s{extra_txt}{invalid}\n"
                )
            handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Duel classic vs zesardine.")
    parser.add_argument("--games", type=int, default=4, help="Nombre de parties a jouer.")
    parser.add_argument("--time", type=float, default=2.0, help="Secondes par coup et par IA.")
    parser.add_argument("--log", default="ai_duel_log.txt", help="Fichier de log detaille.")
    parser.add_argument("--verbose", action="store_true", help="Affiche chaque coup.")
    args = parser.parse_args()

    if args.games <= 0:
        raise SystemExit("--games doit etre positif")
    if args.time <= 0:
        raise SystemExit("--time doit etre positif")

    results = []
    score = {CLASSIC: 0, ZESARDINE: 0, "draw": 0}

    for game_no in range(1, args.games + 1):
        if game_no % 2 == 1:
            x_engine, o_engine = CLASSIC, ZESARDINE
        else:
            x_engine, o_engine = ZESARDINE, CLASSIC

        print(f"Partie {game_no}/{args.games}: X={x_engine}, O={o_engine}")
        result = play_game(game_no, x_engine, o_engine, args.time, args.verbose)
        results.append(result)
        print("  " + format_result(result))

        winner = winner_engine(result)
        if winner is None:
            score["draw"] += 1
        else:
            score[winner] += 1

    write_log(args.log, results)

    print()
    print("Resume")
    print(f"  classic   : {score[CLASSIC]} victoire(s)")
    print(f"  zesardine : {score[ZESARDINE]} victoire(s)")
    print(f"  nuls      : {score['draw']}")
    print(f"  log       : {args.log}")


if __name__ == "__main__":
    main()
