#!/usr/bin/env python3
"""
Kanban — File-based project board for Hermes Agent.

Usage:
  kanban init [--path <dir>] [--board "name"]
  kanban add <title> [--col <column>] [--prio P0-P4] [--desc "<desc>"]
  kanban move <id> --col <column>
  kanban list [--col <column>]
  kanban info <id>
  kanban log <id> "<message>"
  kanban edit <id> [--title "<title>"] [--desc "<desc>"] [--prio P0-P4] [--assign <user>]
  kanban board [--output board.md]
  kanban archive [--days 7]

Columns: Backlog, Todo, Doing, Review, Done
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────

BOARD_FILE = "KANBAN.json"
COLUMNS = ["Backlog", "Todo", "Doing", "Review", "Done"]
COLUMN_EMOJI = {
    "Backlog": "📋",
    "Todo":    "📝",
    "Doing":   "🚧",
    "Review":  "🔍",
    "Done":    "✅",
}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
PRIORITY_LABEL = {
    "P0": "🔴 P0 (critical)",
    "P1": "🟠 P1 (high)",
    "P2": "🟡 P2 (medium)",
    "P3": "🟢 P3 (low)",
    "P4": "⚪ P4 (backlog)",
}


# ── Data helpers ────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_board(path):
    board_file = Path(path) / BOARD_FILE
    if not board_file.exists():
        print(f"❌ No kanban board found at {board_file}")
        print("   Run: kanban init")
        sys.exit(1)
    return json.loads(board_file.read_text())


def _save_board(path, board):
    board_file = Path(path) / BOARD_FILE
    board_file.write_text(json.dumps(board, indent=2, ensure_ascii=False))


def _resolve_path(path):
    return Path(path).expanduser().resolve()


def _find_card(board, card_id):
    card_id = card_id.upper()
    for card in board["cards"]:
        if card["id"] == card_id:
            return card
    print(f"❌ Card '{card_id}' not found")
    sys.exit(1)


def _assign_id(board):
    n = board["next_id"]
    board["next_id"] = n + 1
    return f"K{n}"


def _width(s):
    """Approximate display width (counting CJK as 2)."""
    w = 0
    for ch in s:
        if ord(ch) > 0x2E80:
            w += 2
        else:
            w += 1
    return w


def _pad(s, width):
    """Pad string to display width."""
    return s + " " * max(0, width - _width(s))


# ── Commands ────────────────────────────────────────────────────────

def _print_card(card):
    """Print a compact one-line card summary."""
    prio = card.get("priority", "P4")
    prio_icon = "🔴" if prio == "P0" else "🟠" if prio == "P1" else "🟡" if prio == "P2" else "🟢" if prio == "P3" else "⚪"
    assign = f" @{card['assignee']}" if card.get("assignee") else ""
    print(f"   [{card['id']}] {prio_icon} {prio} | {card['title']}{assign}")
    if card.get("desc"):
        for line in card["desc"].split("\n"):
            print(f"          {line}")


def cmd_init(args):
    path = _resolve_path(args.path)
    board_file = path / BOARD_FILE
    if board_file.exists():
        print(f"⚠️  Board already exists at {board_file}")
        return

    board = {
        "board": args.board or f"Board @ {path.name}",
        "columns": COLUMNS,
        "cards": [],
        "next_id": 1,
        "created_at": _now(),
        "updated_at": _now(),
    }
    _save_board(path, board)
    print(f"✅ Kanban board created at {board_file}")
    print(f"   Board: {board['board']}")
    print(f"   Columns: {', '.join(COLUMNS)}")


def cmd_add(args):
    path = _resolve_path(args.path)
    board = _load_board(path)
    col = args.col or "Backlog"
    # Case-insensitive column matching
    match = [c for c in COLUMNS if c.lower() == col.lower()]
    if not match:
        # Try prefix matching
        match = [c for c in COLUMNS if c.lower().startswith(col.lower())]
    if not match:
        print(f"❌ Invalid column: {col}. Choose from: {', '.join(COLUMNS)}")
        sys.exit(1)
    if len(match) > 1:
        print(f"❌ Ambiguous column '{col}'. Matches: {', '.join(match)}")
        sys.exit(1)
    col = match[0]

    card_id = _assign_id(board)
    card = {
        "id": card_id,
        "title": args.title,
        "column": col,
        "priority": args.prio or "P2",
        "assignee": None,
        "desc": args.desc or "",
        "created_at": _now(),
        "logs": [],
    }
    board["cards"].append(card)
    board["updated_at"] = _now()
    _save_board(path, board)

    print(f"✅ [{card_id}] {card['title']} → {COLUMN_EMOJI[col]} {col}")
    _print_card(card)


def cmd_move(args):
    path = _resolve_path(args.path)
    board = _load_board(path)
    card = _find_card(board, args.col_id.upper())
    col_target = args.col

    # Allow partial matching for speed
    match = [c for c in COLUMNS if c.lower().startswith(col_target.lower())]
    if not match:
        print(f"❌ No column matches '{col_target}'. Options: {', '.join(COLUMNS)}")
        sys.exit(1)
    if len(match) > 1:
        print(f"❌ Ambiguous column '{col_target}'. Matches: {', '.join(match)}")
        sys.exit(1)
    col_target = match[0]

    old_col = card["column"]
    if old_col == col_target:
        print(f"⚠️  [{card['id']}] already in {col_target}")
        return

    card["column"] = col_target
    board["updated_at"] = _now()
    card["logs"].append({
        "timestamp": _now(),
        "message": f"Moved from {old_col} → {col_target}",
    })
    _save_board(path, board)

    print(f"✅ [{card['id']}] {COLUMN_EMOJI[old_col]} {old_col} → {COLUMN_EMOJI[col_target]} {col_target}")
    _print_card(card)


def cmd_list(args):
    path = _resolve_path(args.path)
    board = _load_board(path)

    print(f"\n{'=' * 70}")
    print(f"  📋 {board['board']}")
    print(f"{'=' * 70}\n")

    if args.col:
        cols_to_show = [c for c in COLUMNS if c.lower().startswith(args.col.lower())]
        if not cols_to_show:
            print(f"❌ No column matches '{args.col}'")
            return
    else:
        cols_to_show = COLUMNS

    total = 0
    for col in cols_to_show:
        cards_in_col = sorted(
            [c for c in board["cards"] if c["column"] == col],
            key=lambda c: (PRIORITY_ORDER.get(c.get("priority", "P4"), 99), c["created_at"]),
        )
        print(f"  {COLUMN_EMOJI[col]} {col} ({len(cards_in_col)})")
        print(f"  {'─' * 66}")

        if not cards_in_col:
            print(f"  (empty)\n")
            continue

        # Table header
        print(f"    {'ID':<5} {'Priority':<14} {'Title':<40}")
        print(f"    {'─' * 5} {'─' * 14} {'─' * 40}")

        for card in cards_in_col:
            prio = card.get("priority", "P4")
            prio_icon = "🔴" if prio == "P0" else "🟠" if prio == "P1" else "🟡" if prio == "P2" else "🟢" if prio == "P3" else "⚪"
            assign = f" @{card['assignee']}" if card.get("assignee") else ""
            print(f"    {card['id']:<5} {prio_icon} {prio:<11} {card['title'][:38]}{assign}")

        total += len(cards_in_col)
        print()

    print(f"  Total: {sum(1 for c in board['cards'])} cards ({total} shown)\n")


def cmd_info(args):
    path = _resolve_path(args.path)
    board = _load_board(path)
    card_id = args.id.upper()
    card = _find_card(board, card_id)

    print()
    print(f"  {COLUMN_EMOJI[card['column']]} [{card['id']}] {card['title']}")
    print(f"  {'─' * 50}")
    print(f"  Column:   {card['column']}")
    print(f"  Priority: {PRIORITY_LABEL.get(card['priority'], card['priority'])}")
    print(f"  Assignee: {card['assignee'] or '—'}")
    print(f"  Created:  {card['created_at']}")
    if card.get("desc"):
        print(f"  Description:")
        for line in card["desc"].split("\n"):
            print(f"    {line}")
    if card.get("logs"):
        print(f"  Activity Log:")
        for entry in card["logs"]:
            print(f"    [{entry['timestamp']}] {entry['message']}")
    print()


def cmd_log(args):
    path = _resolve_path(args.path)
    board = _load_board(path)
    card = _find_card(board, args.id.upper())
    card["logs"].append({
        "timestamp": _now(),
        "message": args.message,
    })
    board["updated_at"] = _now()
    _save_board(path, board)
    print(f"✅ Log added to [{card['id']}]")
    print(f"   [{args.message}]")


def cmd_edit(args):
    path = _resolve_path(args.path)
    board = _load_board(path)
    card = _find_card(board, args.id.upper())
    changed = []
    if args.title:
        card["title"] = args.title
        changed.append("title")
    if args.desc:
        card["desc"] = args.desc
        changed.append("description")
    if args.prio:
        if args.prio not in PRIORITY_ORDER:
            print(f"❌ Invalid priority: {args.prio}. Choose: P0, P1, P2, P3, P4")
            return
        card["priority"] = args.prio
        changed.append("priority")
    if args.assign:
        card["assignee"] = args.assign.lstrip("@")
        changed.append("assignee")

    if changed:
        card["logs"].append({
            "timestamp": _now(),
            "message": f"Updated: {', '.join(changed)}",
        })
        board["updated_at"] = _now()
        _save_board(path, board)
        print(f"✅ [{card['id']}] updated: {', '.join(changed)}")
    else:
        print("⚠️  Nothing to change (use --title, --desc, --prio, or --assign)")


def cmd_board(args):
    """Export board as a markdown file (for Obsidian / humans)."""
    path = _resolve_path(args.path)
    board = _load_board(path)

    lines = []
    lines.append(f"# 📋 {board['board']}")
    lines.append(f"> Generated: {_now()}\n")

    for col in COLUMNS:
        cards_in_col = sorted(
            [c for c in board["cards"] if c["column"] == col],
            key=lambda c: (PRIORITY_ORDER.get(c.get("priority", "P4"), 99), c["created_at"]),
        )
        lines.append(f"## {COLUMN_EMOJI[col]} {col} ({len(cards_in_col)})")
        if not cards_in_col:
            lines.append("_Empty_\n")
            continue

        lines.append(f"| {''.ljust(5)} | Priority | Task | Assignee |")
        lines.append(f"|{'-'*7}|{'-'*10}|{'-'*50}|{'-'*10}|")

        for card in cards_in_col:
            prio = card.get("priority", "P4")
            assign = card.get("assignee") or "—"
            lines.append(f"| {card['id']} | {prio} | {card['title']} | {assign} |")

        lines.append("")

    lines.append(f"\n---\n_Total: {len(board['cards'])} cards_")

    output = args.output
    if output:
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = path / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines) + "\n")
        print(f"✅ Board exported to {output_path}")
    else:
        print("\n".join(lines))


def cmd_archive(args):
    path = _resolve_path(args.path)
    board = _load_board(path)

    now = datetime.now(timezone.utc)
    to_archive = []
    kept = []

    for card in board["cards"]:
        if card["column"] == "Done":
            try:
                moved_logs = [l for l in card.get("logs", []) if "Done" in l.get("message", "")]
                if moved_logs:
                    last_moved = moved_logs[-1]["timestamp"]
                    moved_at = datetime.strptime(last_moved[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                    days_since = (now - moved_at).days
                    if days_since >= (args.days or 7):
                        to_archive.append(card)
                        continue
            except (ValueError, IndexError):
                pass
        kept.append(card)

    if not to_archive:
        print("ℹ️  Nothing to archive")
        return

    board["cards"] = kept
    board["archived_cards"] = board.get("archived_cards", []) + to_archive
    board["updated_at"] = _now()
    _save_board(path, board)

    print(f"✅ Archived {len(to_archive)} card(s):")
    for card in to_archive:
        print(f"   [{card['id']}] {card['title']}")


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Kanban — File-based project board")
    parser.add_argument("--path", default=".", help="Project directory (default: current)")

    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Create a new kanban board")
    p_init.add_argument("--board", default=None, help="Board name")

    # add
    p_add = sub.add_parser("add", help="Add a card")
    p_add.add_argument("title", help="Card title")
    p_add.add_argument("--col", default=None, help=f"Column ({', '.join(COLUMNS)}, default: Backlog)")
    p_add.add_argument("--prio", default="P2", help="Priority (P0-P4, default: P2)")
    p_add.add_argument("--desc", default=None, help="Description")

    # move
    p_move = sub.add_parser("move", help="Move card between columns")
    p_move.add_argument("col_id", help="Card ID (e.g. K1)")
    p_move.add_argument("--col", required=True, help=f"Target column ({', '.join(COLUMNS)})")

    # list
    p_list = sub.add_parser("list", aliases=["ls"], help="List cards")
    p_list.add_argument("--col", default=None, help="Filter by column")

    # info
    p_info = sub.add_parser("info", help="Show card details")
    p_info.add_argument("id", help="Card ID")

    # log
    p_log = sub.add_parser("log", help="Add activity log to card")
    p_log.add_argument("id", help="Card ID")
    p_log.add_argument("message", help="Log message")

    # edit
    p_edit = sub.add_parser("edit", help="Edit card fields")
    p_edit.add_argument("id", help="Card ID")
    p_edit.add_argument("--title", default=None, help="New title")
    p_edit.add_argument("--desc", default=None, help="New description")
    p_edit.add_argument("--prio", default=None, help=f"Priority ({', '.join(PRIORITY_LABEL.keys())})")
    p_edit.add_argument("--assign", default=None, help="Assignee (@user)")

    # board
    p_board = sub.add_parser("board", help="Export board as markdown")
    p_board.add_argument("--output", default=None, help="Output file path (default: print to stdout)")

    # archive
    p_archive = sub.add_parser("archive", help="Archive completed cards")
    p_archive.add_argument("--days", type=int, default=7, help="Archive if Done for N days (default: 7)")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "add": cmd_add,
        "move": cmd_move,
        "list": cmd_list,
        "ls": cmd_list,
        "info": cmd_info,
        "log": cmd_log,
        "edit": cmd_edit,
        "board": cmd_board,
        "archive": cmd_archive,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
