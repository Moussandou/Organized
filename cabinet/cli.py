import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

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

# Compatibilité système pour la lecture brute des touches
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
    """Lit un caractère depuis le terminal en mode brut (Unix/macOS)."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x03':  # Ctrl+C
            raise KeyboardInterrupt
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def interactive_select(options: List[str], header: str = "") -> int:
    """Affiche un menu interactif avec navigation par flèches du clavier."""
    if not UNIX_SYSTEM:
        # Fallback pour les systèmes non-Unix (ex: Windows)
        if header:
            console.print(header)
        for idx, opt in enumerate(options, start=1):
            console.print(f"  [bold cyan]{idx}[/bold cyan]. {opt}")
        choice = Prompt.ask("\n[bold]Votre choix[/bold]", choices=[str(i) for i in range(1, len(options) + 1)], default="1")
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
            title="[bold]Navigation : ⇅ | Validation : Entrée[/bold]",
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
                elif ch == '\x1b':  # Code d'échappement pour les flèches
                    ch2 = get_char()
                    ch3 = get_char()
                    if ch2 == '[':
                        if ch3 == 'A':    # Flèche Haut
                            selected_idx = (selected_idx - 1) % len(options)
                        elif ch3 == 'B':  # Flèche Bas
                            selected_idx = (selected_idx + 1) % len(options)
    finally:
        console.show_cursor(True)

def interactive_confirm(question: str) -> bool:
    """Affiche une boîte de dialogue interactive Oui/Non avec déplacement horizontal."""
    if not UNIX_SYSTEM:
        return Confirm.ask(question)
        
    selected_idx = 0  # 0 = Oui, 1 = Non
    options = ["Oui", "Non"]
    
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
            title="[bold]Confirmation[/bold]",
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
                        if ch3 in ('C', 'D'):  # Flèches Gauche/Droite
                            selected_idx = 1 - selected_idx
    finally:
        console.show_cursor(True)

def welcome_animation():
    """Affiche un effet lumineux de chargement multicolore pour la bannière."""
    console.clear()
    colors = ["cyan", "magenta", "blue", "green"]
    for color in colors:
        console.clear()
        styled_banner = Text(BANNER, style=f"bold {color}")
        console.print(Align.center(styled_banner))
        console.print(Align.center(f"[bold white]Démarrage de Cabinet CLI...[/bold white]"))
        time.sleep(0.1)
    console.clear()

def format_size(size_in_bytes: int) -> str:
    """Formatte une taille d'octets en version lisible (Ko, Mo, Go)."""
    val = float(size_in_bytes)
    for unit in ['o', 'Ko', 'Mo', 'Go']:
        if val < 1024.0:
            return f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} To"

def get_tree_preview(preview_dict: Dict[str, List[Tuple[Path, Path]]], root_dir: Path) -> Tree:
    """Construit une arborescence visuelle des déplacements prévus."""
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
                size_str = "Taille inconnue"
            leaf_node.add(f"[green]📄 {src.name}[/green] [dim]({size_str})[/dim]")
            
    return tree

def run_undo(organizer: CabinetOrganizer):
    """Gère l'action d'annulation du dernier rangement."""
    last_session = get_last_session()
    
    if not last_session:
        console.print(Panel("[bold red]Aucun historique de rangement trouvé.[/bold red]", border_style="red"))
        return
        
    timestamp_str = last_session.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(timestamp_str)
        date_formatted = dt.strftime("%d/%m/%Y à %H:%M:%S")
    except Exception:
        date_formatted = timestamp_str
        
    strategy = last_session.get("strategy", "inconnue")
    moves = last_session.get("moves", [])
    
    console.print(Panel(
        f"[bold yellow]Dernière session trouvée :[/bold yellow]\n"
        f"• Date : [cyan]{date_formatted}[/cyan]\n"
        f"• Stratégie : [cyan]{strategy}[/cyan]\n"
        f"• Fichiers à restaurer : [cyan]{len(moves)}[/cyan]",
        title="[bold]Annulation du rangement[/bold]",
        border_style="yellow"
    ))
    
    confirm = interactive_confirm("Voulez-vous restaurer ces fichiers à leur emplacement d'origine ?")
    if not confirm:
        console.print("[dim]Annulation annulée.[/dim]")
        return
        
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task("[yellow]Restauration des fichiers en cours...", total=None)
        popped_session = pop_last_session()
        if not popped_session:
            console.print("[bold red]Erreur lors de la récupération de la session.[/bold red]")
            return
            
        reverted_count, errors = organizer.revert_moves(popped_session["moves"])
        
    if reverted_count > 0:
        console.print(Panel(
            f"[bold green]Succès ! {reverted_count} fichier(s) ont été restaurés.[/bold green]",
            border_style="green"
        ))
    
    if errors:
        console.print("[bold red]Certaines erreurs sont survenues :[/bold red]")
        for err in errors:
            console.print(f"[red]• {err}[/red]")

def run_organization_flow(organizer: CabinetOrganizer, strategy: str):
    """Gère le workflow complet pour une stratégie de rangement."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task("[cyan]Scan du dossier...", total=None)
        files = organizer.scan_files()
        
    if not files:
        console.print(Panel(
            f"[bold green]Votre dossier Téléchargements ({organizer.target_dir.name}) est déjà propre ! Aucun fichier à ranger.[/bold green]",
            border_style="green"
        ))
        return
        
    preview = organizer.preview_organization(files, strategy)
    
    console.print("\n[bold cyan]=== Prévisualisation du Rangement ===[/bold cyan]")
    tree_preview = get_tree_preview(preview, organizer.target_dir)
    console.print(tree_preview)
    console.print(f"\n[bold]Total : {len(files)} fichier(s) à organiser.[/bold]\n")
    
    confirm = interactive_confirm("Confirmer le rangement ?")
    if not confirm:
        console.print("[dim]Rangement annulé.[/dim]")
        return
        
    moves = []
    errors = []
    
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40, complete_style="green", finished_style="bold green"),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("[cyan]Déplacement des fichiers...", total=len(files))
        
        for file in files:
            file_moves, file_errors = organizer.organize([file], strategy)
            moves.extend(file_moves)
            errors.extend(file_errors)
            progress.advance(task, 1)
            time.sleep(0.02)  # Petite pause pour l'effet visuel fluide
            
    if moves:
        save_session(moves, strategy)
        
    console.print("\n[bold green]✓ Rangement terminé avec succès ![/bold green]\n")
    
    table = Table(title="Résumé des fichiers rangés", border_style="cyan")
    table.add_column("Fichier", style="green", no_wrap=True)
    table.add_column("Destination", style="yellow")
    table.add_column("Taille", justify="right", style="magenta")
    
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
    console.print(f"\n[bold]Fichiers déplacés : [cyan]{len(moves)}[/cyan] | Espace organisé : [magenta]{format_size(total_size)}[/magenta][/bold]\n")
    
    if errors:
        console.print("[bold red]Certains fichiers n'ont pas pu être déplacés :[/bold red]")
        for err in errors:
            console.print(f"[red]• {err}[/red]")

import subprocess

def open_file_system(path: Path):
    """Ouvre un fichier avec l'application par défaut du système."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=True)
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", str(path)], check=True)
        elif sys.platform == "win32":
            os.startfile(path)
    except Exception as e:
        console.print(f"[bold red]Impossible d'ouvrir le fichier : {str(e)}[/bold red]")

def run_duplicates_flow(organizer: CabinetOrganizer):
    """Gère la recherche, la comparaison et la suppression sélective des doublons."""
    choices = [
        "Dossier racine uniquement (Téléchargements)",
        "Récursif (Tous les sous-dossiers compris)"
    ]
    idx = interactive_select(choices, "[bold yellow]Choisissez la portée de la recherche de doublons :[/bold yellow]")
    recursive = (idx == 1)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task("[cyan]Analyse de l'espace et calcul des signatures (SHA-256)...", total=None)
        duplicate_groups = organizer.find_duplicates(recursive=recursive)
        
    if not duplicate_groups:
        console.print(Panel(
            "[bold green]Aucun fichier en doublon n'a été détecté ![/bold green]\n"
            "Chaque fichier possède une signature de contenu unique.", 
            border_style="green"
        ))
        return
        
    console.print(Panel(
        f"[bold yellow]Analyse terminée : {len(duplicate_groups)} groupe(s) de doublons détecté(s).[/bold yellow]\n"
        "Vous allez pouvoir passer en revue chaque groupe, comparer les fichiers et choisir celui à conserver.",
        border_style="yellow"
    ))
    
    deleted_count = 0
    total_freed_size = 0
    errors = []
    
    trash_dir = Path.home() / ".Trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    
    group_idx = 1
    for composite_key, paths in duplicate_groups.items():
        # Extraction de la taille à partir de la clé composite (format: "taille_hash")
        try:
            size = int(composite_key.split('_')[0])
        except Exception:
            size = paths[0].stat().st_size
            
        size_str = format_size(size)
        
        while True:
            # Construction des options d'interaction pour ce groupe
            options = []
            for p in paths:
                try:
                    rel_p = p.relative_to(organizer.target_dir)
                except ValueError:
                    rel_p = p
                options.append(f"Conserver uniquement : [bold green]{rel_p}[/bold green]")
                
            options.append("🔍 [cyan]Ouvrir tous les fichiers du groupe pour les comparer[/cyan]")
            options.append("⏩ [yellow]Ignorer ce groupe (ne rien supprimer)[/yellow]")
            
            header = (
                f"[bold cyan]Groupe {group_idx}/{len(duplicate_groups)}[/bold cyan] - "
                f"Taille par fichier : [bold magenta]{size_str}[/bold magenta]\n"
                f"Contenu validé à 100% identique par signature cryptographique.\n\n"
                f"Choisissez le fichier à [bold green]CONSERVER[/bold green] (les autres seront envoyés à la Corbeille) :"
            )
            
            choice_idx = interactive_select(options, header)
            
            if choice_idx < len(paths):
                # L'utilisateur choisit d'en garder un
                keep_path = paths[choice_idx]
                del_paths = [p for p in paths if p != keep_path]
                
                # Déplacement des autres vers la Corbeille
                for dp in del_paths:
                    try:
                        if dp.exists():
                            dest = organizer.resolve_conflict(trash_dir / dp.name)
                            shutil.move(str(dp), str(dest))
                            deleted_count += 1
                            total_freed_size += size
                    except Exception as e:
                        errors.append(f"Erreur de mise à la Corbeille pour {dp.name} : {str(e)}")
                break
                
            elif choice_idx == len(paths):
                # Ouvrir les fichiers pour les comparer
                console.print("[cyan]Ouverture des fichiers avec les applications système par défaut...[/cyan]")
                for p in paths:
                    open_file_system(p)
                time.sleep(0.8)
                continue
                
            else:
                # Ignorer ce groupe
                console.print("[dim]Groupe ignoré.[/dim]")
                break
                
        group_idx += 1
        console.print("─" * 40)
        
    console.print(Panel(
        f"[bold green]Opération terminée ![/bold green]\n"
        f"• Doublons nettoyés : [cyan]{deleted_count}[/cyan]\n"
        f"• Espace disque récupéré : [bold magenta]{format_size(total_freed_size)}[/bold magenta]",
        border_style="green",
        title="[bold]Bilan Nettoyage Doublons[/bold]"
    ))
    
    if errors:
        console.print("[bold red]Certaines erreurs sont survenues :[/bold red]")
        for err in errors:
            console.print(f"[red]• {err}[/red]")

def run_cleanup_flow(organizer: CabinetOrganizer):
    """Gère le nettoyage et l'archivage par âge."""
    days_str = Prompt.ask("[bold]Âge minimal des fichiers à nettoyer (en jours, ou 'q' pour annuler)[/bold]", default="30").strip()
    if days_str.lower() in ('q', 'quit', 'cancel', 'exit', 'back'):
        console.print("[dim]Action annulée. Retour au menu principal.[/dim]")
        return
        
    try:
        days = int(days_str)
    except ValueError:
        days = 30
        
    action_choices = [
        "Compacter dans une archive ZIP (Recommandé)",
        "Déplacer directement vers la Corbeille"
    ]
    action_idx = interactive_select(action_choices, "[bold yellow]Choisissez l'action de nettoyage :[/bold yellow]")
    action = "archive" if action_idx == 0 else "trash"
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task("[cyan]Recherche des vieux fichiers...", total=None)
        old_files = organizer.get_old_files(days)
        
    if not old_files:
        console.print(Panel(
            f"[bold green]Aucun fichier plus vieux de {days} jours trouvé dans vos dossiers.[/bold green]",
            border_style="green"
        ))
        return
        
    table = Table(title=f"Fichiers trouvés (>= {days} jours)", border_style="yellow")
    table.add_column("Fichier", style="cyan")
    table.add_column("Dernière modification", style="yellow")
    table.add_column("Taille", justify="right", style="magenta")
    
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
    console.print(
        f"\n[bold yellow]Total :[/bold yellow] [cyan]{len(old_files)}[/cyan] fichiers anciens détectés. "
        f"Taille globale : [bold magenta]{format_size(total_size)}[/bold magenta]\n"
    )
    
    confirm = interactive_confirm(f"Confirmer le traitement ({'Archive' if action == 'archive' else 'Corbeille'}) ?")
    if not confirm:
        console.print("[dim]Action annulée.[/dim]")
        return
        
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task("[cyan]Traitement en cours...", total=None)
        success_count, archive_path, errors = organizer.clean_old_files(days, action)
        
    if success_count > 0:
        if action == "trash":
            console.print(Panel(
                f"[bold green]Succès ! {success_count} fichier(s) déplacé(s) vers la Corbeille macOS.[/bold green]",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[bold green]Succès ! {success_count} fichier(s) archivé(s) dans le ZIP :[/bold green]\n"
                f"[bold cyan]{archive_path.name}[/bold cyan]\n"
                f"Les originaux ont été déplacés vers la Corbeille.",
                border_style="green"
            ))
            
    if errors:
        console.print("[bold red]Certaines erreurs sont survenues :[/bold red]")
        for err in errors:
            console.print(f"[red]• {err}[/red]")

def run_smart_rules_flow():
    """Gère le sous-menu de configuration des Smart Rules."""
    while True:
        console.clear()
        console.print(Panel(
            "[bold cyan]Règles de Tri Personnalisées (Smart Rules)[/bold cyan]\n"
            "Associez des mots-clés dans les noms de fichiers à des dossiers cibles spécifiques.\n"
            "Ces règles s'appliquent en priorité absolue sur le rangement.",
            border_style="cyan"
        ))
        
        rules = load_rules()
        options = [
            "Lister les règles actives",
            "Ajouter une nouvelle règle",
            "Supprimer une règle",
            "Retour au menu principal"
        ]
        choice_idx = interactive_select(options, "[bold magenta]Sélectionnez une option :[/bold magenta]")
        
        if choice_idx == 0:
            if not rules:
                console.print("\n[yellow]Aucune règle personnalisée active.[/yellow]")
            else:
                table = Table(title="Règles de tri personnalisées", border_style="cyan")
                table.add_column("Mot-clé (Pattern)", style="green", bold=True)
                table.add_column("Dossier de destination", style="yellow")
                for r in rules:
                    table.add_row(r.get("pattern", ""), r.get("folder", ""))
                console.print(table)
            Prompt.ask("\nAppuyez sur Entrée pour continuer")
            
        elif choice_idx == 1:
            pattern = Prompt.ask("\n[bold]Entrez le mot-clé (ex: facture, devis, zoom) [dim](ou 'q' pour annuler)[/dim][/bold]").strip()
            if not pattern or pattern.lower() in ('q', 'quit', 'cancel', 'exit', 'back'):
                console.print("[dim]Ajout annulé.[/dim]")
                Prompt.ask("\nAppuyez sur Entrée pour continuer")
                continue
                
            folder = Prompt.ask("[bold]Entrez le dossier cible (ex: Documents/Factures, Vidéos/Reunions) [dim](ou 'q' pour annuler)[/dim][/bold]").strip()
            if not folder or folder.lower() in ('q', 'quit', 'cancel', 'exit', 'back'):
                console.print("[dim]Ajout annulé.[/dim]")
                Prompt.ask("\nAppuyez sur Entrée pour continuer")
                continue
                
            if any(r.get("pattern", "").lower() == pattern.lower() for r in rules):
                console.print("[red]Une règle existe déjà pour ce mot-clé.[/red]")
                Prompt.ask("\nAppuyez sur Entrée pour continuer")
                continue
                
            rules.append({"pattern": pattern, "folder": folder})
            save_rules(rules)
            console.print(f"[green]Règle ajoutée : [bold]{pattern}[/bold] ➔ [bold]{folder}[/bold][/green]")
            Prompt.ask("\nAppuyez sur Entrée pour continuer")
            
        elif choice_idx == 2:
            if not rules:
                console.print("\n[yellow]Aucune règle à supprimer.[/yellow]")
                Prompt.ask("\nAppuyez sur Entrée pour continuer")
                continue
                
            table = Table(title="Supprimer une règle", border_style="red")
            table.add_column("N°", justify="center", style="bold red")
            table.add_column("Mot-clé", style="green")
            table.add_column("Dossier cible", style="yellow")
            
            for idx, r in enumerate(rules, start=1):
                table.add_row(str(idx), r.get("pattern", ""), r.get("folder", ""))
                
            console.print(table)
            
            del_idx_str = Prompt.ask(
                "[bold]Entrez le numéro de la règle à supprimer (ou Entrée pour annuler)[/bold]",
                default=""
            ).strip()
            if not del_idx_str or del_idx_str.lower() in ('q', 'quit', 'cancel', 'exit', 'back'):
                console.print("[dim]Suppression annulée.[/dim]")
                continue
                
            try:
                del_idx = int(del_idx_str) - 1
                if 0 <= del_idx < len(rules):
                    removed = rules.pop(del_idx)
                    save_rules(rules)
                    console.print(f"[green]Règle [bold]{removed['pattern']}[/bold] supprimée.[/green]")
                else:
                    console.print("[red]Numéro invalide.[/red]")
            except ValueError:
                console.print("[red]Entrée invalide.[/red]")
            Prompt.ask("\nAppuyez sur Entrée pour continuer")
            
        elif choice_idx == 3:
            break

def run_stats_flow(organizer: CabinetOrganizer):
    """Gère l'affichage graphique des statistiques d'espace."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task("[cyan]Analyse de l'espace disque...", total=None)
        files = organizer.scan_all_files_recursive()
        
    if not files:
        console.print(Panel(
            "[bold yellow]Aucun fichier trouvé dans le répertoire cible pour générer des statistiques.[/bold yellow]",
            border_style="yellow"
        ))
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
                category = rel.parts[0] if len(rel.parts) > 1 else "Racine"
            except ValueError:
                category = "Divers"
                
            if category not in stats:
                stats[category] = {"count": 0, "size": 0}
                
            stats[category]["count"] += 1
            stats[category]["size"] += size
        except Exception:
            continue
            
    table = Table(title="Répartition de l'espace disque par catégorie", border_style="cyan")
    table.add_column("Dossier / Catégorie", style="bold green")
    table.add_column("Fichiers", justify="right", style="cyan")
    table.add_column("Espace occupé", justify="right", style="magenta")
    table.add_column("Part", justify="right", style="yellow")
    table.add_column("Jauge (Graphique)", style="white")
    
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
        "Total",
        str(total_files),
        format_size(total_size),
        "100.0 %",
        "[bold cyan]" + "█" * max_bar_width + "[/bold cyan]"
    )
    
    console.print(table)
    Prompt.ask("\nAppuyez sur Entrée pour continuer")

def main():
    """Point d'entrée principal de l'application Cabinet CLI."""
    from cabinet.config import setup_logging, LOG_FILE
    import logging
    
    setup_logging()
    logging.info("=== Démarrage de la session Cabinet CLI ===")
    
    try:
        # Lancement de l'animation de démarrage colorée
        welcome_animation()
        
        organizer = CabinetOrganizer(DEFAULT_TARGET_DIR)
        
        while True:
            console.clear()
            
            # Titre et crédits du créateur Moussandou
            styled_banner = Text(BANNER, style="bold cyan")
            console.print(Align.center(styled_banner))
            console.print(Align.center("[bold magenta]─── Votre classeur virtuel pour dossier Downloads ───[/bold magenta]"))
            console.print(Align.center("[dim white]Créé avec passion par [bold cyan]Moussandou[/bold cyan][/dim white]\n"))
            
            console.print(Panel(
                f"Dossier surveillé : [bold cyan]{organizer.target_dir}[/bold cyan]\n"
                "Prêt à trier et organiser intelligemment vos fichiers !",
                border_style="magenta",
                title="[bold]Cabinet CLI[/bold]",
                title_align="center"
            ))
            
            options = [
                "Classer par Catégorie (ex: Images, Documents, Code...)",
                "Classer par Date (ex: Année-Mois/)",
                "Classer par Extension (ex: PNG/, PDF/, ZIP/)",
                "Classer en mode Hybride (ex: Images/Année-Mois/)",
                "Annuler le dernier rangement (Undo)",
                "Trouver et supprimer les doublons",
                "Nettoyer/Archiver les vieux fichiers",
                "Gérer les règles personnalisées (Smart Rules)",
                "Statistiques de l'espace disque (Graphique)",
                "Quitter"
            ]
            
            choice_idx = interactive_select(options, "[bold magenta]Menu Principal :[/bold magenta]")
            
            # Traitement de l'option choisie
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
                console.print("\n[bold green]Au revoir ! Merci d'avoir utilisé Cabinet.[/bold green]")
                logging.info("Fermeture propre de Cabinet CLI.")
                break
            
            console.print("\n" + "─" * 50 + "\n")
    except KeyboardInterrupt:
        logging.info("Session interrompue par l'utilisateur (Ctrl+C)")
        console.print("\n\n[bold yellow]Cabinet interrompu (Ctrl+C). Au revoir ![/bold yellow]")
        try:
            console.show_cursor(True)
        except Exception:
            pass
        sys.exit(0)
    except Exception as e:
        logging.exception("Une erreur inattendue et critique est survenue dans main() :")
        console.print(Panel(
            f"[bold red]Une erreur inattendue est survenue :[/bold red] {str(e)}\n\n"
            f"Les détails techniques du crash ont été enregistrés dans :\n"
            f"[bold cyan]{LOG_FILE}[/bold cyan]\n\n"
            "Veuillez soumettre ce fichier pour débogage.",
            title="[bold red]Erreur Critique de Cabinet[/bold red]",
            border_style="red"
        ))
        try:
            console.show_cursor(True)
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
