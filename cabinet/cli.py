import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm
from rich.align import Align
from rich.text import Text

from cabinet.config import DEFAULT_TARGET_DIR, load_rules, save_rules
from cabinet.organizer import CabinetOrganizer
from cabinet.history import save_session, get_last_session, pop_last_session

console = Console()

BANNER = """
   ______      __     _                 __ 
  / ____/___ _/ /_   (_)___  ___  _____/ /_
 / /   / __ `/ __ \ / / __ \/ _ \/ ___/ __/
/ /___/ /_/ / /_/ // / / / /  __/ /__/ /_  
\____/\__,_/_.___//_/_/ /_/\___/\___/\__/  
"""

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
    
    confirm = Confirm.ask("[bold]Voulez-vous restaurer ces fichiers à leur emplacement d'origine ?[/bold]")
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
    
    confirm = Confirm.ask("[bold]Confirmer le rangement ?[/bold]")
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

def run_duplicates_flow(organizer: CabinetOrganizer):
    """Gère la recherche et le nettoyage des doublons."""
    mode = Prompt.ask(
        "[bold]Portée de la recherche[/bold]", 
        choices=["Racine", "Récursif"], 
        default="Racine"
    )
    recursive = (mode == "Récursif")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task("[cyan]Recherche de doublons en cours...", total=None)
        duplicate_groups = organizer.find_duplicates(recursive=recursive)
        
    if not duplicate_groups:
        console.print(Panel(
            "[bold green]Aucun fichier en doublon n'a été détecté ![/bold green]", 
            border_style="green"
        ))
        return
        
    # Présentation des doublons
    table = Table(title=f"Doublons détectés ({mode})", border_style="yellow")
    table.add_column("Groupe", justify="center", style="bold yellow")
    table.add_column("Fichiers correspondants (Le 1er est conservé, les autres seront supprimés)", style="cyan")
    table.add_column("Taille", justify="right", style="magenta")
    
    total_redundant_size = 0
    files_to_delete = []
    group_idx = 1
    
    for file_hash, paths in duplicate_groups.items():
        try:
            # On conserve le premier fichier, on supprime les suivants
            keep_file = paths[0]
            del_files = paths[1:]
            
            size = keep_file.stat().st_size
            group_redundant_size = size * len(del_files)
            total_redundant_size += group_redundant_size
            
            files_to_delete.extend(del_files)
            
            # Formatage de la ligne de texte
            file_lines = [f"[bold green]➔ Conserver :[/bold green] {keep_file.name}"]
            for df in del_files:
                try:
                    rel_df = df.relative_to(organizer.target_dir)
                except ValueError:
                    rel_df = df
                file_lines.append(f"[red]✕ Supprimer :[/red] {rel_df}")
                
            table.add_row(
                str(group_idx), 
                "\n".join(file_lines), 
                format_size(size)
            )
            group_idx += 1
        except Exception:
            continue
            
    console.print(table)
    console.print(
        f"\n[bold yellow]Attention :[/bold yellow] [cyan]{len(files_to_delete)}[/cyan] fichiers doublons détectés. "
        f"Espace récupérable : [bold magenta]{format_size(total_redundant_size)}[/bold magenta]\n"
    )
    
    confirm = Confirm.ask("[bold]Voulez-vous envoyer les doublons à la Corbeille macOS ?[/bold]")
    if not confirm:
        console.print("[dim]Action annulée.[/dim]")
        return
        
    trash_dir = Path.home() / ".Trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    
    deleted_count = 0
    errors = []
    
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40, complete_style="red"),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("[red]Déplacement vers la Corbeille...", total=len(files_to_delete))
        
        for file in files_to_delete:
            try:
                if file.exists():
                    dest = organizer.resolve_conflict(trash_dir / file.name)
                    shutil.move(str(file), str(dest))
                    deleted_count += 1
                progress.advance(task, 1)
            except Exception as e:
                errors.append(f"Erreur avec {file.name} : {str(e)}")
                progress.advance(task, 1)
                
    console.print(Panel(
        f"[bold green]Nettoyage terminé ! {deleted_count} fichiers envoyés à la Corbeille.[/bold green]\n"
        f"Espace disque libéré : [bold magenta]{format_size(total_redundant_size)}[/bold magenta]",
        border_style="green"
    ))
    
    if errors:
        console.print("[bold red]Certaines erreurs sont survenues :[/bold red]")
        for err in errors:
            console.print(f"[red]• {err}[/red]")

def run_cleanup_flow(organizer: CabinetOrganizer):
    """Gère le nettoyage et l'archivage par âge."""
    days_str = Prompt.ask("[bold]Âge minimal des fichiers à nettoyer (en jours)[/bold]", default="30")
    try:
        days = int(days_str)
    except ValueError:
        days = 30
        
    action_choice = Prompt.ask(
        "[bold]Action à effectuer[/bold]", 
        choices=["Corbeille", "Archive ZIP"], 
        default="Archive ZIP"
    )
    action = "trash" if action_choice == "Corbeille" else "archive"
    
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
        
    # Liste des vieux fichiers
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
    
    confirm = Confirm.ask(f"[bold]Voulez-vous procéder à l'action [magenta]{action_choice}[/magenta] ?[/bold]")
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
            "[bold cyan]Configuration des Règles de Tri Personnalisées (Smart Rules)[/bold cyan]\n"
            "Associez des mots-clés dans les noms de fichiers à des dossiers cibles spécifiques.\n"
            "Ces règles s'appliquent en priorité absolue sur le rangement.",
            border_style="cyan"
        ))
        
        rules = load_rules()
        
        console.print("[bold magenta]Options :[/bold magenta]")
        console.print("  [bold cyan]1[/bold cyan]. Lister les règles actives")
        console.print("  [bold cyan]2[/bold cyan]. Ajouter une nouvelle règle")
        console.print("  [bold cyan]3[/bold cyan]. Supprimer une règle")
        console.print("  [bold cyan]4[/bold cyan]. Retour au menu principal")
        
        choice = Prompt.ask("\n[bold]Votre choix[/bold]", choices=["1", "2", "3", "4"], default="1")
        
        if choice == "1":
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
            
        elif choice == "2":
            pattern = Prompt.ask("\n[bold]Entrez le mot-clé (ex: facture, devis, zoom)[/bold]").strip()
            if not pattern:
                continue
                
            folder = Prompt.ask("[bold]Entrez le dossier cible (ex: Documents/Factures, Vidéos/Reunions)[/bold]").strip()
            if not folder:
                continue
                
            # Vérification des doublons de motifs
            if any(r.get("pattern", "").lower() == pattern.lower() for r in rules):
                console.print("[red]Une règle existe déjà pour ce mot-clé.[/red]")
                Prompt.ask("\nAppuyez sur Entrée pour continuer")
                continue
                
            rules.append({"pattern": pattern, "folder": folder})
            save_rules(rules)
            console.print(f"[green]Règle ajoutée : [bold]{pattern}[/bold] ➔ [bold]{folder}[/bold][/green]")
            Prompt.ask("\nAppuyez sur Entrée pour continuer")
            
        elif choice == "3":
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
            )
            if not del_idx_str:
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
            
        elif choice == "4":
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
        
    # Calcul des tailles par sous-dossier ou dossier racine
    stats: Dict[str, Dict[str, any]] = {}
    total_size = 0
    total_files = len(files)
    
    for file in files:
        try:
            size = file.stat().st_size
            total_size += size
            
            # Détermine la catégorie (le dossier parent le plus proche du dossier Downloads)
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
            
    # Construction de la table
    table = Table(title="Répartition de l'espace disque par catégorie", border_style="cyan")
    table.add_column("Dossier / Catégorie", style="bold green")
    table.add_column("Fichiers", justify="right", style="cyan")
    table.add_column("Espace occupé", justify="right", style="magenta")
    table.add_column("Part", justify="right", style="yellow")
    table.add_column("Jauge (Graphique)", style="white")
    
    # Tri par taille décroissante
    sorted_stats = sorted(stats.items(), key=lambda item: item[1]["size"], reverse=True)
    
    # Nombre max de caractères pour la jauge graphique
    max_bar_width = 25
    
    for cat, data in sorted_stats:
        cat_size = data["size"]
        count = data["count"]
        percentage = (cat_size / total_size) * 100 if total_size > 0 else 0
        
        # Création de la barre graphique textuelle
        num_blocks = int((percentage / 100) * max_bar_width)
        bar = "█" * num_blocks + "░" * (max_bar_width - num_blocks)
        
        # Couleur dynamique pour la jauge
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
    console.clear()
    styled_banner = Text(BANNER, style="bold cyan")
    console.print(Align.center(styled_banner))
    console.print(Align.center("[bold magenta]─── Votre classeur virtuel pour dossier Downloads ───[/bold magenta]\n"))
    
    organizer = CabinetOrganizer(DEFAULT_TARGET_DIR)
    
    console.print(Panel(
        f"Dossier surveillé : [bold cyan]{organizer.target_dir}[/bold cyan]\n"
        "Prêt à trier et organiser intelligemment vos fichiers !",
        border_style="magenta",
        title="[bold]Cabinet CLI[/bold]"
    ))
    
    while True:
        console.print("[bold magenta]Menu Principal :[/bold magenta]")
        console.print("  [bold cyan]1[/bold cyan]. Classer par [bold]Catégorie[/bold] (ex: Images, Documents, Code...)")
        console.print("  [bold cyan]2[/bold cyan]. Classer par [bold]Date[/bold] (ex: Année-Mois/)")
        console.print("  [bold cyan]3[/bold cyan]. Classer par [bold]Extension[/bold] (ex: PNG/, PDF/, ZIP/)")
        console.print("  [bold cyan]4[/bold cyan]. Classer en mode [bold]Hybride[/bold] (ex: Images/Année-Mois/)")
        console.print("  [bold cyan]5[/bold cyan]. [bold yellow]Annuler[/bold yellow] le dernier rangement (Undo)")
        console.print("  [bold cyan]6[/bold cyan]. [bold red]Trouver et supprimer les doublons[/bold red]")
        console.print("  [bold cyan]7[/bold cyan]. [bold yellow]Nettoyer/Archiver les vieux fichiers[/bold yellow]")
        console.print("  [bold cyan]8[/bold cyan]. [bold cyan]Gérer les règles personnalisées (Smart Rules)[/bold cyan]")
        console.print("  [bold cyan]9[/bold cyan]. [bold green]Statistiques de l'espace disque (Graphique)[/bold green]")
        console.print("  [bold cyan]10[/bold cyan]. Quitter")
        
        choice = Prompt.ask("\n[bold]Votre choix[/bold]", choices=[str(i) for i in range(1, 11)], default="1")
        
        if choice == "1":
            run_organization_flow(organizer, "category")
        elif choice == "2":
            run_organization_flow(organizer, "date")
        elif choice == "3":
            run_organization_flow(organizer, "extension")
        elif choice == "4":
            run_organization_flow(organizer, "hybrid")
        elif choice == "5":
            run_undo(organizer)
        elif choice == "6":
            run_duplicates_flow(organizer)
        elif choice == "7":
            run_cleanup_flow(organizer)
        elif choice == "8":
            run_smart_rules_flow()
        elif choice == "9":
            run_stats_flow(organizer)
        elif choice == "10":
            console.print("\n[bold green]Au revoir ! Merci d'avoir utilisé Cabinet.[/bold green]")
            break
        
        console.print("\n" + "─" * 50 + "\n")

if __name__ == "__main__":
    main()
