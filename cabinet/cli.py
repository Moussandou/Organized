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

from cabinet.config import DEFAULT_TARGET_DIR
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
    
    # Dictionnaire temporaire pour retrouver les nœuds de dossiers créés
    node_map = {"": tree}
    
    for folder_path_str in sorted(preview_dict.keys()):
        parts = folder_path_str.split(os.sep)
        current_path = ""
        
        # Construction récursive de l'arborescence des dossiers
        for part in parts:
            parent_path = current_path
            current_path = os.path.join(current_path, part) if current_path else part
            
            if current_path not in node_map:
                parent_node = node_map[parent_path]
                node_map[current_path] = parent_node.add(f"[bold yellow]📁 {part}[/bold yellow]")
                
        # Ajout des fichiers sous le dossier final
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
        
    # Infos sur la session précédente
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
        
    # Lancement de la restauration
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task("[yellow]Restauration des fichiers en cours...", total=None)
        # On extrait la session et lance la restauration
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
    # Scan
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
        
    # Simulation/Prévisualisation
    preview = organizer.preview_organization(files, strategy)
    
    console.print("\n[bold cyan]=== Prévisualisation du Rangement ===[/bold cyan]")
    tree_preview = get_tree_preview(preview, organizer.target_dir)
    console.print(tree_preview)
    console.print(f"\n[bold]Total : {len(files)} fichier(s) à organiser.[/bold]\n")
    
    confirm = Confirm.ask("[bold]Confirmer le rangement ?[/bold]")
    if not confirm:
        console.print("[dim]Rangement annulé.[/dim]")
        return
        
    # Exécution réelle
    moves = []
    errors = []
    
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40, complete_style="green", finished_style="bold green"),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("[cyan]Déplacement des fichiers...", total=len(files))
        
        # Pour une belle animation, on déplace les fichiers un à un en mettant à jour la barre
        for file in files:
            file_moves, file_errors = organizer.organize([file], strategy)
            moves.extend(file_moves)
            errors.extend(file_errors)
            progress.advance(task, 1)
            
    # Enregistrement dans l'historique si des fichiers ont bougé
    if moves:
        save_session(moves, strategy)
        
    # Rapport final
    console.print("\n[bold green]✓ Rangement terminé avec succès ![/bold green]\n")
    
    # Création du tableau de résumé
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
            
        # Affiche le chemin de destination relatif pour la lisibilité
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

def main():
    """Point d'entrée principal de l'application Cabinet CLI."""
    # Nettoyage console
    console.clear()
    
    # Affichage de la bannière de bienvenue
    styled_banner = Text(BANNER, style="bold cyan")
    console.print(Align.center(styled_banner))
    console.print(Align.center("[bold magenta]─── Votre classeur virtuel pour dossier Downloads ───[/bold magenta]\n"))
    
    organizer = CabinetOrganizer(DEFAULT_TARGET_DIR)
    
    # Message d'accueil indiquant le dossier cible
    console.print(Panel(
        f"Dossier surveillé : [bold cyan]{organizer.target_dir}[/bold cyan]\n"
        "Prêt à trier et organiser intelligemment vos fichiers !",
        border_style="magenta",
        title="[bold]Cabinet CLI[/bold]"
    ))
    
    while True:
        console.print("[bold magenta]Options de rangement :[/bold magenta]")
        console.print("  [bold cyan]1[/bold cyan]. Classer par [bold]Catégorie[/bold] (ex: Images, Documents, Code...)")
        console.print("  [bold cyan]2[/bold cyan]. Classer par [bold]Date[/bold] (ex: Année-Mois/)")
        console.print("  [bold cyan]3[/bold cyan]. Classer par [bold]Extension[/bold] (ex: PNG/, PDF/, ZIP/)")
        console.print("  [bold cyan]4[/bold cyan]. Classer en mode [bold]Hybride[/bold] (ex: Images/Année-Mois/)")
        console.print("  [bold cyan]5[/bold cyan]. [bold yellow]Annuler[/bold yellow] le dernier rangement (Undo)")
        console.print("  [bold cyan]6[/bold cyan]. Quitter")
        
        choice = Prompt.ask("\n[bold]Votre choix[/bold]", choices=["1", "2", "3", "4", "5", "6"], default="1")
        
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
            console.print("\n[bold green]Au revoir ! Merci d'avoir utilisé Cabinet.[/bold green]")
            break
        
        console.print("\n" + "─" * 50 + "\n")

if __name__ == "__main__":
    main()
