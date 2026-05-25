import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import shutil

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm
from rich.align import Align
from rich.text import Text
from rich.live import Live

from cabinet.config import DEFAULT_TARGET_DIR, load_rules, save_rules
from cabinet.organizer import CabinetOrganizer
from cabinet.history import save_session, get_last_session, pop_last_session
from cabinet.i18n import t, set_language, get_current_language

# Check system capability for raw key reading
try:
    import tty
    import termios
    UNIX_SYSTEM = True
except ImportError:
    UNIX_SYSTEM = False

console = Console()

BANNER = """
   ______      __     _                 __ 
  / ____/___ _/ /_   (_)___  ___  _____/ /_
 / /   / __ `/ __ \ / / __ \/ _ \/ ___/ __/
/ /___/ /_/ / /_/ // / / / /  __/ /__/ /_  
\____/\__,_/_.___//_/_/ /_/\___/\___/\__/  
"""

def get_char() -> str:
    """Read a single character from the standard input in raw mode."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x03':  # Ctrl+C handler
            raise KeyboardInterrupt
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def interactive_select(options: List[str], header: str = "") -> int:
    """Render an interactive keyboard-navigated menu."""
    if not UNIX_SYSTEM:
        # Simple fallback for non-Unix operating systems (e.g. Windows)
        if header:
            console.print(header)
        for idx, opt in enumerate(options, start=1):
            console.print(f"  [bold cyan]{idx}[/bold cyan]. {opt}")
        choice = Prompt.ask(
            f"\n[bold]{t('your_choice')}[/bold]", 
            choices=[str(i) for i in range(1, len(options) + 1)], 
            default="1"
        )
        return int(choice) - 1

    selected_idx = 0
    
    def generate_view() -> Panel:
        lines = []
        for idx, option in enumerate(options):
            if idx == selected_idx:
                lines.append(f"[bold magenta] ❯ {option}[/bold magenta]")
            else:
                lines.append(f"   [dim white]{option}[/dim white]")
                
        menu_content = "\n".join(lines)
        full_text = f"{header}\n\n{menu_content}" if header else menu_content
        return Panel(
            full_text,
            border_style="magenta",
            expand=False,
            title=f"[bold]{t('nav_help')}[/bold]",
            title_align="left"
        )

    console.show_cursor(False)
    try:
        with Live(generate_view(), auto_refresh=False, transient=True) as live:
            while True:
                live.update(generate_view())
                live.refresh()
                
                ch = get_char()
                if ch in ('\r', '\n'):
                    return selected_idx
                elif ch == '\x1b':  # Escape sequence for arrow keys
                    ch2 = get_char()
                    ch3 = get_char()
                    if ch2 == '[':
                        if ch3 == 'A':    # Up Arrow
                            selected_idx = (selected_idx - 1) % len(options)
                        elif ch3 == 'B':  # Down Arrow
                            selected_idx = (selected_idx + 1) % len(options)
    finally:
        console.show_cursor(True)

def interactive_confirm(question: str) -> bool:
    """Render an interactive Yes/No confirmation dialog."""
    if not UNIX_SYSTEM:
        return Confirm.ask(question)
        
    selected_idx = 0  # 0 = Yes, 1 = No
    options = [t("yes"), t("no")]
    
    def generate_view() -> Panel:
        buttons = []
        for idx, opt in enumerate(options):
            if idx == selected_idx:
                buttons.append(f"[bold white on magenta]  {opt}  [/bold white on magenta]")
            else:
                buttons.append(f"[dim white]  {opt}  [/dim white]")
                
        button_line = "   ".join(buttons)
        content = Group(
            Text.from_markup(f"[bold white]{question}[/bold white]\n"),
            Align.center(Text.from_markup(button_line))
        )
        return Panel(
            content,
            border_style="cyan",
            expand=False,
            title=f"[bold]{t('confirmation_title')}[/bold]",
            title_align="center"
        )
        
    console.show_cursor(False)
    try:
        with Live(generate_view(), auto_refresh=False, transient=True) as live:
            while True:
                live.update(generate_view())
                live.refresh()
                
                ch = get_char()
                if ch in ('\r', '\n'):
                    return selected_idx == 0
                elif ch == '\x1b':
                    ch2 = get_char()
                    ch3 = get_char()
                    if ch2 == '[':
                        if ch3 in ('C', 'D'):  # Left/Right Arrows
                            selected_idx = 1 - selected_idx
    finally:
        console.show_cursor(True)

def welcome_animation():
    """Display a colorful glowing welcome animation banner."""
    console.clear()
    colors = ["cyan", "magenta", "blue", "green"]
    for color in colors:
        console.clear()
        styled_banner = Text(BANNER, style=f"bold {color}")
        console.print(Align.center(styled_banner))
        console.print(Align.center(f"[bold white]{t('starting_cli')}[/bold white]"))
        time.sleep(0.1)
    console.clear()

def format_size(size_in_bytes: int) -> str:
    """Format size in bytes to a human-readable string."""
    val = float(size_in_bytes)
    units = [t("b"), t("kb"), t("mb"), t("gb")]
    for unit in units:
        if val < 1024.0:
            return f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} {t('tb')}"

def get_tree_preview(preview_dict: Dict[str, List[Tuple[Path, Path]]], root_dir: Path) -> Tree:
    """Build a visual tree representation of planned file relocation operations."""
    tree = Tree(f"[bold cyan]📂 {root_dir.name}[/bold cyan]")
    node_map = {"": tree}
    
    for folder_path_str in sorted(preview_dict.keys()):
        parts = folder_path_str.split(os.sep)
        current_path = ""
        
        for part in parts:
            parent_path = current_path
            current_path = os.path.join(current_path, part) if current_path else part
            
            if current_path not in node_map:
                parent_node = node_map[parent_path]
                node_map[current_path] = parent_node.add(f"[bold yellow]📁 {part}[/bold yellow]")
                
        leaf_node = node_map[folder_path_str]
        for src, dest in preview_dict[folder_path_str]:
            try:
                size = src.stat().st_size
                size_str = format_size(size)
            except Exception:
                size_str = t("size_unknown")
            leaf_node.add(f"[green]📄 {src.name}[/green] [dim]({size_str})[/dim]")
            
    return tree

def run_undo(organizer: CabinetOrganizer):
    """Roll back the last organization session."""
    last_session = get_last_session()
    
    if not last_session:
        console.print(Panel(f"[bold red]{t('no_history_found')}[/bold red]", border_style="red"))
        return
        
    timestamp_str = last_session.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(timestamp_str)
        date_formatted = dt.strftime(f"%d/%m/%Y {t('at')} %H:%M:%S")
    except Exception:
        date_formatted = timestamp_str
        
    strategy = last_session.get("strategy", t("unknown"))
    moves = last_session.get("moves", [])
    
    console.print(Panel(
        f"[bold yellow]{t('last_session_found')}[/bold yellow]\n"
        f"• {t('date_label')} : [cyan]{date_formatted}[/cyan]\n"
        f"• {t('strategy_label')} : [cyan]{strategy}[/cyan]\n"
        f"• {t('files_to_restore')} : [cyan]{len(moves)}[/cyan]",
        title=f"[bold]{t('undo_title')}[/bold]",
        border_style="yellow"
    ))
    
    confirm = interactive_confirm(t("confirm_restore"))
    if not confirm:
        console.print(f"[dim]{t('undo_canceled')}[/dim]")
        return
        
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task(f"[yellow]{t('restoring_files')}", total=None)
        popped_session = pop_last_session()
        if not popped_session:
            console.print(f"[bold red]{t('error_restoring_session')}[/bold red]")
            return
            
        reverted_count, errors = organizer.revert_moves(popped_session["moves"])
        
    if reverted_count > 0:
        console.print(Panel(
            f"[bold green]{t('restored_success', count=reverted_count)}[/bold green]",
            border_style="green"
        ))
    
    if errors:
        console.print(f"[bold red]{t('some_errors_occurred')}[/bold red]")
        for err in errors:
            console.print(f"[red]• {err}[/red]")

def run_organization_flow(organizer: CabinetOrganizer, strategy: str):
    """Execute the full organization workflow for a selected strategy."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task(f"[cyan]{t('scanning_folder')}", total=None)
        files = organizer.scan_files()
        
    if not files:
        console.print(Panel(
            f"[bold green]{t('folder_clean', name=organizer.target_dir.name)}[/bold green]",
            border_style="green"
        ))
        return
        
    preview = organizer.preview_organization(files, strategy)
    
    console.print(f"\n[bold cyan]{t('preview_title')}[/bold cyan]")
    tree_preview = get_tree_preview(preview, organizer.target_dir)
    console.print(tree_preview)
    console.print(f"\n[bold]{t('total_files_to_organize', count=len(files))}[/bold]\n")
    
    confirm = interactive_confirm(t("confirm_organization"))
    if not confirm:
        console.print(f"[dim]{t('organization_canceled')}[/dim]")
        return
        
    moves = []
    errors = []
    
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40, complete_style="green", finished_style="bold green"),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task(f"[cyan]{t('moving_files')}", total=len(files))
        
        for file in files:
            file_moves, file_errors = organizer.organize([file], strategy)
            moves.extend(file_moves)
            errors.extend(file_errors)
            progress.advance(task, 1)
            time.sleep(0.02)  # Tiny sleep for smooth visual rendering
            
    if moves:
        save_session(moves, strategy)
        
    console.print(f"\n[bold green]{t('organization_success')}[/bold green]\n")
    
    table = Table(title=t("summary_title"), border_style="cyan")
    table.add_column(t("summary_file"), style="green", no_wrap=True)
    table.add_column(t("summary_dest"), style="yellow")
    table.add_column(t("summary_size"), justify="right", style="magenta")
    
    total_size = 0
    for move in moves:
        dest_path = Path(move["dest"])
        try:
            size = dest_path.stat().st_size
            total_size += size
            size_str = format_size(size)
        except Exception:
            size_str = "N/A"
            
        try:
            rel_dest = dest_path.relative_to(organizer.target_dir)
        except ValueError:
            rel_dest = dest_path
            
        table.add_row(dest_path.name, str(rel_dest.parent), size_str)
        
    console.print(table)
    console.print(f"\n[bold]{t('summary_moved_count', count=len(moves), size=format_size(total_size))}[/bold]\n")
    
    if errors:
        console.print(f"[bold red]{t('cannot_move_errors')}[/bold red]")
        for err in errors:
            console.print(f"[red]• {err}[/red]")

def open_file_system(path: Path):
    """Open a file using the host operating system's default handler application."""
    try:
        if sys.platform == "darwin":
            import subprocess
            subprocess.run(["open", str(path)], check=True)
        elif sys.platform.startswith("linux"):
            import subprocess
            subprocess.run(["xdg-open", str(path)], check=True)
        elif sys.platform == "win32":
            os.startfile(path)
    except Exception as e:
        console.print(f"[bold red]{t('open_file_error', name=path.name, err=str(e))}[/bold red]")

def run_duplicates_flow(organizer: CabinetOrganizer):
    """Scan, preview, and selectively purge duplicate files."""
    choices = [
        t("dup_scope_root"),
        t("dup_scope_rec")
    ]
    idx = interactive_select(choices, f"[bold yellow]{t('dup_scope_select')}[/bold yellow]")
    recursive = (idx == 1)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task(f"[cyan]{t('duplicate_scan')}", total=None)
        duplicate_groups = organizer.find_duplicates(recursive=recursive)
        
    if not duplicate_groups:
        console.print(Panel(
            f"[bold green]{t('duplicate_no_files')}[/bold green]", 
            border_style="green"
        ))
        Prompt.ask(t("press_enter"))
        return
        
    console.print(Panel(
        f"[bold yellow]{t('dup_scan_finished', count=len(duplicate_groups))}[/bold yellow]",
        border_style="yellow"
    ))
    
    # Prompt the user for execution mode: review one by one vs. clean all automatically
    action_modes = [
        t("dup_action_review"),
        t("dup_action_auto")
    ]
    mode_idx = interactive_select(action_modes, f"[bold yellow]{t('dup_action_select')}[/bold yellow]")
    
    deleted_count = 0
    total_freed_size = 0
    errors = []
    
    trash_dir = Path.home() / ".Trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    
    if mode_idx == 1:
        # Confirm automatic batch deletion
        confirm = interactive_confirm(t("dup_confirm_auto"))
        if not confirm:
            console.print(f"[dim]{t('action_canceled')}[/dim]")
            Prompt.ask(t("press_enter"))
            return
            
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            progress.add_task(f"[cyan]{t('dup_auto_cleaning')}", total=None)
            for composite_key, paths in duplicate_groups.items():
                try:
                    size = int(composite_key.split('_')[0])
                except Exception:
                    size = paths[0].stat().st_size
                
                # Keep the first file, delete the rest
                keep_path = paths[0]
                del_paths = paths[1:]
                for dp in del_paths:
                    try:
                        if dp.exists():
                            dest = organizer.resolve_conflict(trash_dir / dp.name)
                            shutil.move(str(dp), str(dest))
                            deleted_count += 1
                            total_freed_size += size
                    except Exception as e:
                        errors.append(t("open_file_error", name=dp.name, err=str(e)))
                        
    else:
        # Review one by one mode
        group_idx = 1
        for composite_key, paths in duplicate_groups.items():
            try:
                size = int(composite_key.split('_')[0])
            except Exception:
                size = paths[0].stat().st_size
                
            size_str = format_size(size)
            
            while True:
                options = []
                for p in paths:
                    try:
                        rel_p = p.relative_to(organizer.target_dir)
                    except ValueError:
                        rel_p = p
                    options.append(t("dup_keep_only", path=rel_p))
                    
                options.append(t("dup_compare_files"))
                options.append(t("dup_skip_group"))
                
                header = t("dup_group_header", idx=group_idx, total=len(duplicate_groups), size=size_str)
                choice_idx = interactive_select(options, header)
                
                if choice_idx < len(paths):
                    # User wants to keep this specific copy
                    keep_path = paths[choice_idx]
                    del_paths = [p for p in paths if p != keep_path]
                    
                    for dp in del_paths:
                        try:
                            if dp.exists():
                                dest = organizer.resolve_conflict(trash_dir / dp.name)
                                shutil.move(str(dp), str(dest))
                                deleted_count += 1
                                total_freed_size += size
                        except Exception as e:
                            errors.append(t("open_file_error", name=dp.name, err=str(e)))
                    break
                    
                elif choice_idx == len(paths):
                    # Launch default opening action for comparisons
                    console.print(f"[cyan]{t('dup_opening_files')}[/cyan]")
                    for p in paths:
                        open_file_system(p)
                    time.sleep(0.8)
                    continue
                    
                else:
                    # Bypass this duplicate group
                    console.print(f"[dim]{t('dup_group_ignored')}[/dim]")
                    break
                    
            group_idx += 1
            console.print("─" * 40)
        
    console.print(Panel(
        t("dup_summary", count=deleted_count, size=format_size(total_freed_size)),
        border_style="green",
        title=f"[bold]{t('dup_summary_title')}[/bold]"
    ))
    
    if errors:
        console.print(f"[bold red]{t('some_errors_occurred')}[/bold red]")
        for err in errors:
            console.print(f"[red]• {err}[/red]")
    Prompt.ask(t("press_enter"))

def run_cleanup_flow(organizer: CabinetOrganizer):
    """Identify and archive or delete files based on age rules."""
    days_str = Prompt.ask(f"[bold]{t('cleanup_age_prompt')}[/bold]", default="30").strip()
    if days_str.lower() in ('q', 'quit', 'cancel', 'exit', 'back'):
        console.print(f"[dim]{t('cleanup_canceled_msg')}[/dim]")
        Prompt.ask(t("press_enter"))
        return
        
    try:
        days = int(days_str)
    except ValueError:
        days = 30
        
    action_choices = [
        t("cleanup_opt_zip"),
        t("cleanup_opt_trash")
    ]
    action_idx = interactive_select(action_choices, f"[bold yellow]{t('cleanup_action_select')}[/bold yellow]")
    action = "archive" if action_idx == 0 else "trash"
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task(f"[cyan]{t('cleanup_scanning')}", total=None)
        old_files = organizer.get_old_files(days)
        
    if not old_files:
        console.print(Panel(
            f"[bold green]{t('cleanup_no_old', days=days)}[/bold green]",
            border_style="green"
        ))
        Prompt.ask(t("press_enter"))
        return
        
    table = Table(title=t("cleanup_found_title", days=days), border_style="yellow")
    table.add_column(t("summary_file"), style="cyan")
    table.add_column(t("date_label"), style="yellow")
    table.add_column(t("summary_size"), justify="right", style="magenta")
    
    total_size = 0
    for file in old_files:
        try:
            size = file.stat().st_size
            total_size += size
            mtime = datetime.fromtimestamp(file.stat().st_mtime).strftime("%d/%m/%Y")
            
            try:
                rel_path = file.relative_to(organizer.target_dir)
            except ValueError:
                rel_path = file
                
            table.add_row(str(rel_path), mtime, format_size(size))
        except Exception:
            continue
            
    console.print(table)
    console.print(t("cleanup_total", count=len(old_files), size=format_size(total_size)))
    
    confirm = interactive_confirm(t("cleanup_confirm", action=t("cleanup_opt_trash") if action == "trash" else t("cleanup_opt_zip")))
    if not confirm:
        console.print(f"[dim]{t('action_canceled')}[/dim]")
        Prompt.ask(t("press_enter"))
        return
        
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task(f"[cyan]{t('processing')}", total=None)
        success_count, archive_path, errors = organizer.clean_old_files(days, action)
        
    if success_count > 0:
        if action == "trash":
            console.print(Panel(
                f"[bold green]{t('cleanup_success_trash', count=success_count)}[/bold green]",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[bold green]{t('cleanup_success_archive', count=success_count, path=archive_path.name)}[/bold green]",
                border_style="green"
            ))
            
    if errors:
        console.print(f"[bold red]{t('some_errors_occurred')}[/bold red]")
        for err in errors:
            console.print(f"[red]• {err}[/red]")
    Prompt.ask(t("press_enter"))

def run_smart_rules_flow():
    """Render the configuration settings menu for pattern-based Smart Rules."""
    while True:
        console.clear()
        console.print(Panel(
            f"[bold cyan]{t('rules_banner')}[/bold cyan]",
            border_style="cyan"
        ))
        
        rules = load_rules()
        options = [
            t("rules_opt_list"),
            t("rules_opt_add"),
            t("rules_opt_delete"),
            t("rules_opt_back")
        ]
        choice_idx = interactive_select(options, f"[bold magenta]{t('rules_select_option')}[/bold magenta]")
        
        if choice_idx == 0:
            if not rules:
                console.print(t("rules_none_active"))
            else:
                table = Table(title=t("rules_table_title"), border_style="cyan")
                table.add_column(t("rules_table_pattern"), style="green", bold=True)
                table.add_column(t("rules_table_folder"), style="yellow")
                for r in rules:
                    table.add_row(r.get("pattern", ""), r.get("folder", ""))
                console.print(table)
            Prompt.ask(t("press_enter"))
            
        elif choice_idx == 1:
            pattern = Prompt.ask(f"\n[bold]{t('rules_enter_pattern')}[/bold]").strip()
            if not pattern or pattern.lower() in ('q', 'quit', 'cancel', 'exit', 'back'):
                console.print(f"[dim]{t('rules_add_canceled')}[/dim]")
                Prompt.ask(t("press_enter"))
                continue
                
            folder = Prompt.ask(f"[bold]{t('rules_enter_folder')}[/bold]").strip()
            if not folder or folder.lower() in ('q', 'quit', 'cancel', 'exit', 'back'):
                console.print(f"[dim]{t('rules_add_canceled')}[/dim]")
                Prompt.ask(t("press_enter"))
                continue
                
            if any(r.get("pattern", "").lower() == pattern.lower() for r in rules):
                console.print(t("rules_already_exists"))
                Prompt.ask(t("press_enter"))
                continue
                
            rules.append({"pattern": pattern, "folder": folder})
            save_rules(rules)
            console.print(t("rules_added_success", pattern=pattern, folder=folder))
            Prompt.ask(t("press_enter"))
            
        elif choice_idx == 2:
            if not rules:
                console.print(t("rules_none_to_delete"))
                Prompt.ask(t("press_enter"))
                continue
                
            table = Table(title=t("rules_delete_title"), border_style="red")
            table.add_column(t("rules_num_col"), justify="center", style="bold red")
            table.add_column(t("rules_keyword_col"), style="green")
            table.add_column(t("rules_target_col"), style="yellow")
            
            for idx, r in enumerate(rules, start=1):
                table.add_row(str(idx), r.get("pattern", ""), r.get("folder", ""))
                
            console.print(table)
            
            del_idx_str = Prompt.ask(
                f"[bold]{t('rules_enter_number_to_delete')}[/bold]",
                default=""
            ).strip()
            if not del_idx_str or del_idx_str.lower() in ('q', 'quit', 'cancel', 'exit', 'back'):
                console.print(f"[dim]{t('rules_delete_canceled')}[/dim]")
                continue
                
            try:
                del_idx = int(del_idx_str) - 1
                if 0 <= del_idx < len(rules):
                    removed = rules.pop(del_idx)
                    save_rules(rules)
                    console.print(t("rules_deleted_success", pattern=removed['pattern']))
                else:
                    console.print(t("rules_invalid_number"))
            except ValueError:
                console.print(t("rules_invalid_input"))
            Prompt.ask(t("press_enter"))
            
        elif choice_idx == 3:
            break

def run_stats_flow(organizer: CabinetOrganizer):
    """Gather file metrics and render directory layout analysis."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task(f"[cyan]{t('stats_scanning')}", total=None)
        files = organizer.scan_all_files_recursive()
        
    if not files:
        console.print(Panel(
            f"[bold yellow]{t('stats_no_files')}[/bold yellow]",
            border_style="yellow"
        ))
        Prompt.ask(t("press_enter"))
        return
        
    stats: Dict[str, Dict[str, any]] = {}
    total_size = 0
    total_files = len(files)
    
    for file in files:
        try:
            size = file.stat().st_size
            total_size += size
            
            try:
                rel = file.relative_to(organizer.target_dir)
                category = rel.parts[0] if len(rel.parts) > 1 else t("stats_root_label")
            except ValueError:
                category = "Divers"
                
            if category not in stats:
                stats[category] = {"count": 0, "size": 0}
                
            stats[category]["count"] += 1
            stats[category]["size"] += size
        except Exception:
            continue
            
    table = Table(title=t("stats_table_title"), border_style="cyan")
    table.add_column(t("stats_col_folder"), style="bold green")
    table.add_column(t("stats_col_files"), justify="right", style="cyan")
    table.add_column(t("stats_col_size"), justify="right", style="magenta")
    table.add_column(t("stats_col_ratio"), justify="right", style="yellow")
    table.add_column(t("stats_col_visual"), style="white")
    
    sorted_stats = sorted(stats.items(), key=lambda item: item[1]["size"], reverse=True)
    max_bar_width = 25
    
    for cat, data in sorted_stats:
        cat_size = data["size"]
        count = data["count"]
        percentage = (cat_size / total_size) * 100 if total_size > 0 else 0
        
        num_blocks = int((percentage / 100) * max_bar_width)
        bar = "█" * num_blocks + "░" * (max_bar_width - num_blocks)
        
        if percentage > 50:
            bar_color = "red"
        elif percentage > 25:
            bar_color = "yellow"
        else:
            bar_color = "green"
            
        table.add_row(
            cat,
            str(count),
            format_size(cat_size),
            f"{percentage:.1f} %",
            f"[{bar_color}]{bar}[/{bar_color}]"
        )
        
    table.add_section()
    table.add_row(
        t("stats_total"),
        str(total_files),
        format_size(total_size),
        "100.0 %",
        "[bold cyan]" + "█" * max_bar_width + "[/bold cyan]"
    )
    
    console.print(table)
    Prompt.ask(t("press_enter_continue"))

def main():
    """Main application loop and CLI routing entry point."""
    from cabinet.config import setup_logging, LOG_FILE
    import logging
    
    setup_logging()
    logging.info("=== Starting Cabinet CLI session ===")
    
    try:
        # Trigger glowing colored welcome animation banner
        welcome_animation()
        
        organizer = CabinetOrganizer(DEFAULT_TARGET_DIR)
        
        while True:
            console.clear()
            
            styled_banner = Text(BANNER, style="bold cyan")
            console.print(Align.center(styled_banner))
            console.print(Align.center(f"[bold magenta]─── {t('welcome_banner')} ───[/bold magenta]"))
            console.print(Align.center(f"[dim white]{t('created_by')} [bold cyan]Moussandou[/bold cyan][/dim white]\n"))
            
            console.print(Panel(
                f"{t('monitored_folder')} : [bold cyan]{organizer.target_dir}[/bold cyan]\n"
                f"{t('ready_to_organize')}",
                border_style="magenta",
                title="[bold]Cabinet CLI[/bold]",
                title_align="center"
            ))
            
            options = [
                t("menu_category"),
                t("menu_date"),
                t("menu_extension"),
                t("menu_hybrid"),
                t("menu_undo"),
                t("menu_duplicates"),
                t("menu_cleanup"),
                t("menu_rules"),
                t("menu_stats"),
                t("menu_language"),
                t("menu_quit")
            ]
            
            choice_idx = interactive_select(options, f"[bold magenta]{t('menu_title')}[/bold magenta]")
            
            if choice_idx == 0:
                run_organization_flow(organizer, "category")
            elif choice_idx == 1:
                run_organization_flow(organizer, "date")
            elif choice_idx == 2:
                run_organization_flow(organizer, "extension")
            elif choice_idx == 3:
                run_organization_flow(organizer, "hybrid")
            elif choice_idx == 4:
                run_undo(organizer)
            elif choice_idx == 5:
                run_duplicates_flow(organizer)
            elif choice_idx == 6:
                run_cleanup_flow(organizer)
            elif choice_idx == 7:
                run_smart_rules_flow()
            elif choice_idx == 8:
                run_stats_flow(organizer)
            elif choice_idx == 9:
                # Dynamic language selection sub-menu
                lang_options = ["English", "Français"]
                lang_choice = interactive_select(lang_options, "Select language / Sélectionnez la langue :")
                if lang_choice == 0:
                    set_language("en")
                elif lang_choice == 1:
                    set_language("fr")
            elif choice_idx == 10:
                console.print(f"\n[bold green]{t('quit_goodbye')}[/bold green]")
                logging.info("Graceful shutdown of Cabinet CLI.")
                break
            
            console.print("\n" + "─" * 50 + "\n")
    except KeyboardInterrupt:
        logging.info("Session interrupted by user (Ctrl+C)")
        console.print(f"\n\n[bold yellow]{t('cabinet_interrupted')}[/bold yellow]")
        try:
            console.show_cursor(True)
        except Exception:
            pass
        sys.exit(0)
    except Exception as e:
        logging.exception("An unexpected critical error occurred in main():")
        console.print(Panel(
            f"[bold red]{t('unexpected_error')} :[/bold red] {str(e)}\n\n"
            f"{t('technical_details')} :\n"
            f"[bold cyan]{LOG_FILE}[/bold cyan]\n\n"
            f"{t('submit_for_debugging')}",
            title=f"[bold red]{t('critical_error_title')}[/bold red]",
            border_style="red"
        ))
        try:
            console.show_cursor(True)
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
