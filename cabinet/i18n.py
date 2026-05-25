import sys
import json
import locale
from pathlib import Path

# Path to local user config files
CONFIG_DIR = Path.home() / ".config" / "cabinet"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# Localized translation dictionary for French and English support
TRANSLATIONS = {
    "en": {
        "welcome_banner": "─── Your virtual cabinet for Downloads folder ───",
        "created_by": "Created with passion by",
        "monitored_folder": "Monitored folder",
        "ready_to_organize": "Ready to smartly organize your files!",
        "menu_title": "Main Menu:",
        "menu_category": "Organize by Category (e.g. Images, Documents, Code...)",
        "menu_date": "Organize by Date (e.g. Year-Month/)",
        "menu_extension": "Organize by Extension (e.g. PNG/, PDF/, ZIP/)",
        "menu_hybrid": "Organize by Hybrid mode (e.g. Images/Year-Month/)",
        "menu_undo": "Undo last organization",
        "menu_duplicates": "Find and remove duplicates",
        "menu_cleanup": "Clean/Archive old files",
        "menu_rules": "Manage custom rules (Smart Rules)",
        "menu_stats": "Disk space statistics (Graph)",
        "menu_language": "Change language / Changer de langue (Current: English)",
        "menu_quit": "Quit",
        "quit_goodbye": "Goodbye! Thank you for using Cabinet.",
        "session_interrupted": "Session interrupted by user (Ctrl+C)",
        "cabinet_interrupted": "Cabinet interrupted (Ctrl+C). Goodbye!",
        "unexpected_error": "An unexpected error occurred",
        "technical_details": "Technical details of the crash were recorded in",
        "submit_for_debugging": "Please submit this file for debugging.",
        "critical_error_title": "Cabinet Critical Error",
        "starting_cli": "Starting Cabinet CLI...",
        "your_choice": "Your choice",
        "nav_help": "Navigation: ⇅ | Confirm: Enter",
        "confirm_title": "Confirmation",
        "yes": "Yes",
        "no": "No",
        "press_enter": "Press Enter to continue",
        "scanning_folder": "Scanning folder...",
        "folder_clean": "Your Downloads folder ({name}) is already clean! No files to organize.",
        "preview_title": "=== Organization Preview ===",
        "total_files_to_organize": "Total: {count} file(s) to organize.",
        "confirm_organization": "Confirm organization?",
        "organization_canceled": "Organization canceled.",
        "moving_files": "Moving files...",
        "organization_success": "✓ Organization completed successfully!",
        "summary_title": "Organized files summary",
        "summary_file": "File",
        "summary_dest": "Destination",
        "summary_size": "Size",
        "summary_moved_count": "Moved files: {count} | Organized space: {size}",
        "cannot_move_errors": "Some files could not be moved:",
        "error_restoring_session": "Error retrieving session.",
        "restored_success": "Success! {count} file(s) have been restored.",
        "some_errors_occurred": "Some errors occurred:",
        "no_history_found": "No organization history found.",
        "last_session_found": "Last session found:",
        "date_label": "Date",
        "strategy_label": "Strategy",
        "files_to_restore": "Files to restore",
        "undo_title": "Undo Organization",
        "confirm_restore": "Do you want to restore these files to their original location?",
        "undo_canceled": "Undo canceled.",
        "restoring_files": "Restoring files...",
        "unknown": "unknown",
        "at": "at",
        "size_unknown": "Size unknown",
        "kb": "KB",
        "mb": "MB",
        "gb": "GB",
        "tb": "TB",
        "b": "B",
        # Duplicate flow keys
        "dup_scope_root": "Root folder only (Downloads)",
        "dup_scope_rec": "Recursive (Include all subfolders)",
        "dup_scope_select": "Choose the duplicate search scope:",
        "duplicate_scan": "Scanning for duplicates...",
        "duplicate_no_files": "No duplicate files found.",
        "dup_scan_finished": "Scan complete: {count} duplicate group(s) detected.",
        "dup_keep_only": "Keep only: [bold green]{path}[/bold green]",
        "dup_compare_files": "🔍 [cyan]Open all files in the group to compare them[/cyan]",
        "dup_skip_group": "⏩ [yellow]Skip this group (delete nothing)[/yellow]",
        "dup_group_header": "[bold cyan]Group {idx}/{total}[/bold cyan] - Size per file: [bold magenta]{size}[/bold magenta]\nContent validated 100% identical by cryptographic signature.\n\nChoose which file to [bold green]KEEP[/bold green] (others will be moved to Trash):",
        "dup_opening_files": "[cyan]Opening files with default system applications...[/cyan]",
        "dup_group_ignored": "[dim]Group ignored.[/dim]",
        "dup_summary": "[bold green]Operation complete![/bold green]\n• Cleaned duplicates: [cyan]{count}[/cyan]\n• Recovered disk space: [bold magenta]{size}[/bold magenta]",
        "dup_summary_title": "Duplicate Cleanup Summary",
        "open_file_error": "Could not open file {name}: {err}",
        "dup_action_select": "Choose how to handle duplicates:",
        "dup_action_review": "Review each duplicate group one by one",
        "dup_action_auto": "Automatically delete all duplicates (keep first copy of each)",
        "dup_confirm_auto": "Are you sure you want to automatically delete all duplicates (keeping the first copy of each group)?",
        "dup_auto_cleaning": "Deleting duplicates automatically...",
        # Cleanup flow keys
        "cleanup_age_prompt": "Select minimum file age to clean/archive (in days, or 'q' to cancel)",
        "cleanup_canceled_msg": "Action canceled. Returning to main menu.",
        "cleanup_opt_zip": "Compress into a ZIP archive (Recommended)",
        "cleanup_opt_trash": "Move directly to Trash",
        "cleanup_action_select": "Choose the cleanup action:",
        "cleanup_scanning": "Scanning for old files...",
        "cleanup_no_old": "No files older than {days} days found in your folders.",
        "cleanup_found_title": "Files found (>= {days} days)",
        "cleanup_total": "\n[bold yellow]Total:[/bold yellow] [cyan]{count}[/cyan] old files detected. Global size: [bold magenta]{size}[/bold magenta]\n",
        "cleanup_confirm": "Confirm execution ({action})?",
        "action_canceled": "Action canceled.",
        "processing": "Processing...",
        "cleanup_success_trash": "Success! {count} file(s) moved to macOS Trash.",
        "cleanup_success_archive": "Success! {count} file(s) archived in ZIP:\n[bold cyan]{path}[/bold cyan]\nOriginals have been moved to Trash.",
        # Smart rules flow keys
        "rules_banner": "Custom sorting rules (Smart Rules)\nAssociate keywords in file names with specific target folders.\nThese rules have absolute priority during organization.",
        "rules_opt_list": "List active rules",
        "rules_opt_add": "Add a new rule",
        "rules_opt_delete": "Delete a rule",
        "rules_opt_back": "Back to main menu",
        "rules_select_option": "Select an option:",
        "rules_none_active": "\n[yellow]No custom rules active.[/yellow]",
        "rules_table_title": "Custom sorting rules",
        "rules_table_pattern": "Keyword (Pattern)",
        "rules_table_folder": "Destination folder",
        "rules_enter_pattern": "Enter keyword (e.g. invoice, report, zoom) (or 'q' to cancel)",
        "rules_add_canceled": "Adding canceled.",
        "rules_enter_folder": "Enter target folder (e.g. Documents/Invoices, Videos/Meetings) (or 'q' to cancel)",
        "rules_already_exists": "[red]A rule already exists for this keyword.[/red]",
        "rules_added_success": "[green]Rule added: [bold]{pattern}[/bold] ➔ [bold]{folder}[/bold][/green]",
        "rules_none_to_delete": "\n[yellow]No rules to delete.[/yellow]",
        "rules_delete_title": "Delete a rule",
        "rules_num_col": "No.",
        "rules_keyword_col": "Keyword",
        "rules_target_col": "Target folder",
        "rules_enter_number_to_delete": "Enter the number of the rule to delete (or Enter to cancel)",
        "rules_delete_canceled": "Deletion canceled.",
        "rules_deleted_success": "[green]Rule [bold]{pattern}[/bold] deleted.[/green]",
        "rules_invalid_number": "[red]Invalid number.[/red]",
        "rules_invalid_input": "[red]Invalid input.[/red]",
        # Stats flow keys
        "stats_scanning": "Analyzing disk space...",
        "stats_no_files": "No files found in the target directory to generate statistics.",
        "stats_root_label": "Root",
        "stats_table_title": "Disk space distribution by category",
        "stats_col_folder": "Folder / Category",
        "stats_col_files": "Files",
        "stats_col_size": "Occupied space",
        "stats_col_ratio": "Ratio",
        "stats_col_visual": "Gauge (Graph)",
        "stats_total": "Total",
        "press_enter_continue": "\nPress Enter to continue"
    },
    "fr": {
        "welcome_banner": "─── Votre classeur virtuel pour dossier Downloads ───",
        "created_by": "Créé avec passion par",
        "monitored_folder": "Dossier surveillé",
        "ready_to_organize": "Prêt à trier et organiser intelligemment vos fichiers !",
        "menu_title": "Menu Principal :",
        "menu_category": "Classer par Catégorie (ex: Images, Documents, Code...)",
        "menu_date": "Classer par Date (ex: Année-Mois/)",
        "menu_extension": "Classer par Extension (ex: PNG/, PDF/, ZIP/)",
        "menu_hybrid": "Classer en mode Hybride (ex: Images/Année-Mois/)",
        "menu_undo": "Annuler le dernier rangement (Undo)",
        "menu_duplicates": "Trouver et supprimer les doublons",
        "menu_cleanup": "Nettoyer/Archiver les vieux fichiers",
        "menu_rules": "Gérer les règles personnalisées (Smart Rules)",
        "menu_stats": "Statistiques de l'espace disque (Graphique)",
        "menu_language": "Change language / Changer de langue (Actuelle : Français)",
        "menu_quit": "Quitter",
        "quit_goodbye": "Au revoir ! Merci d'avoir utilisé Cabinet.",
        "session_interrupted": "Session interrompue par l'utilisateur (Ctrl+C)",
        "cabinet_interrupted": "Cabinet interrompu (Ctrl+C). Au revoir !",
        "unexpected_error": "Une erreur inattendue est survenue",
        "technical_details": "Les détails techniques du crash ont été enregistrés dans",
        "submit_for_debugging": "Veuillez soumettre ce fichier pour débogage.",
        "critical_error_title": "Erreur Critique de Cabinet",
        "starting_cli": "Démarrage de Cabinet CLI...",
        "your_choice": "Votre choix",
        "nav_help": "Navigation : ⇅ | Validation : Entrée",
        "confirm_title": "Confirmation",
        "yes": "Oui",
        "no": "Non",
        "press_enter": "Appuyez sur Entrée pour continuer",
        "scanning_folder": "Scan du dossier...",
        "folder_clean": "Votre dossier Téléchargements ({name}) est déjà propre ! Aucun fichier à ranger.",
        "preview_title": "=== Prévisualisation du Rangement ===",
        "total_files_to_organize": "Total : {count} fichier(s) à organiser.",
        "confirm_organization": "Confirmer le rangement ?",
        "organization_canceled": "Rangement annulé.",
        "moving_files": "Déplacement des fichiers...",
        "organization_success": "✓ Rangement terminé avec succès !",
        "summary_title": "Résumé des fichiers rangés",
        "summary_file": "Fichier",
        "summary_dest": "Destination",
        "summary_size": "Taille",
        "summary_moved_count": "Fichiers déplacés : {count} | Espace organisé : {size}",
        "cannot_move_errors": "Certains fichiers n'ont pas pu être déplacés :",
        "error_restoring_session": "Erreur lors de la récupération de la session.",
        "restored_success": "Succès ! {count} fichier(s) ont été restaurés.",
        "some_errors_occurred": "Certaines erreurs sont survenues :",
        "no_history_found": "Aucun historique de rangement trouvé.",
        "last_session_found": "Dernière session trouvée :",
        "date_label": "Date",
        "strategy_label": "Stratégie",
        "files_to_restore": "Fichiers à restaurer",
        "undo_title": "Annulation du rangement",
        "confirm_restore": "Voulez-vous restaurer ces fichiers à leur emplacement d'origine ?",
        "undo_canceled": "Annulation annulée.",
        "restoring_files": "Restauration des fichiers en cours...",
        "unknown": "inconnue",
        "at": "à",
        "size_unknown": "Taille inconnue",
        "kb": "Ko",
        "mb": "Mo",
        "gb": "Go",
        "tb": "To",
        "b": "o",
        # Duplicate flow keys
        "dup_scope_root": "Dossier racine uniquement (Téléchargements)",
        "dup_scope_rec": "Récursif (Tous les sous-dossiers compris)",
        "dup_scope_select": "Choisissez la portée de la recherche de doublons :",
        "duplicate_scan": "Recherche de doublons en cours...",
        "duplicate_no_files": "Aucun fichier en doublon trouvé.",
        "dup_scan_finished": "Analyse terminée : {count} groupe(s) de doublons détecté(s).",
        "dup_keep_only": "Conserver uniquement : [bold green]{path}[/bold green]",
        "dup_compare_files": "🔍 [cyan]Ouvrir tous les fichiers du groupe pour les comparer[/cyan]",
        "dup_skip_group": "⏩ [yellow]Ignorer ce groupe (ne rien supprimer)[/yellow]",
        "dup_group_header": "[bold cyan]Groupe {idx}/{total}[/bold cyan] - Taille par fichier : [bold magenta]{size}[/bold magenta]\nContenu validé à 100% identique par signature cryptographique.\n\nChoisissez le fichier à [bold green]CONSERVER[/bold green] (les autres seront envoyés à la Corbeille) :",
        "dup_opening_files": "[cyan]Ouverture des fichiers avec les applications système par défaut...[/cyan]",
        "dup_group_ignored": "[dim]Groupe ignoré.[/dim]",
        "dup_summary": "[bold green]Opération terminée ![/bold green]\n• Doublons nettoyés : [cyan]{count}[/cyan]\n• Espace disque récupéré : [bold magenta]{size}[/bold magenta]",
        "dup_summary_title": "Bilan Nettoyage Doublons",
        "open_file_error": "Impossible d'ouvrir le fichier {name} : {err}",
        "dup_action_select": "Choisissez comment traiter les doublons :",
        "dup_action_review": "Passer en revue chaque groupe de doublons un par un",
        "dup_action_auto": "Supprimer automatiquement tous les doublons (conserver la première copie)",
        "dup_confirm_auto": "Voulez-vous vraiment supprimer automatiquement tous les doublons (en conservant la première copie de chaque groupe) ?",
        "dup_auto_cleaning": "Suppression automatique des doublons...",
        # Cleanup flow keys
        "cleanup_age_prompt": "Entrez l'âge minimal des fichiers à nettoyer (en jours, ou 'q' pour annuler)",
        "cleanup_canceled_msg": "Action annulée. Retour au menu principal.",
        "cleanup_opt_zip": "Compacter dans une archive ZIP (Recommandé)",
        "cleanup_opt_trash": "Déplacer directement vers la Corbeille",
        "cleanup_action_select": "Choisissez l'action de nettoyage :",
        "cleanup_scanning": "Recherche des vieux fichiers...",
        "cleanup_no_old": "Aucun fichier plus vieux de {days} jours trouvé dans vos dossiers.",
        "cleanup_found_title": "Fichiers trouvés (>= {days} jours)",
        "cleanup_total": "\n[bold yellow]Total :[/bold yellow] [cyan]{count}[/cyan] fichiers anciens détectés. Taille globale : [bold magenta]{size}[/bold magenta]\n",
        "cleanup_confirm": "Confirmer le traitement ({action})?",
        "action_canceled": "Action annulée.",
        "processing": "Traitement en cours...",
        "cleanup_success_trash": "Succès ! {count} fichier(s) déplacé(s) vers la Corbeille macOS.",
        "cleanup_success_archive": "Succès ! {count} fichier(s) archivé(s) dans le ZIP :\n[bold cyan]{path}[/bold cyan]\nLes originaux ont été déplacés vers la Corbeille.",
        # Smart rules flow keys
        "rules_banner": "Règles de Tri Personnalisées (Smart Rules)\nAssociez des mots-clés dans les noms de fichiers à des dossiers cibles spécifiques.\nCes règles s'appliquent en priorité absolue sur le rangement.",
        "rules_opt_list": "Lister les règles actives",
        "rules_opt_add": "Ajouter une nouvelle règle",
        "rules_opt_delete": "Supprimer une règle",
        "rules_opt_back": "Retour au menu principal",
        "rules_select_option": "Sélectionnez une option :",
        "rules_none_active": "\n[yellow]Aucune règle personnalisée active.[/yellow]",
        "rules_table_title": "Règles de tri personnalisées",
        "rules_table_pattern": "Mot-clé (Pattern)",
        "rules_table_folder": "Dossier de destination",
        "rules_enter_pattern": "Entrez le mot-clé (ex: facture, devis, zoom) (ou 'q' pour annuler)",
        "rules_add_canceled": "Ajout annulé.",
        "rules_enter_folder": "Entrez le dossier cible (ex: Documents/Factures, Vidéos/Reunions) (ou 'q' pour annuler)",
        "rules_already_exists": "[red]Une règle existe déjà pour ce mot-clé.[/red]",
        "rules_added_success": "[green]Règle ajoutée : [bold]{pattern}[/bold] ➔ [bold]{folder}[/bold][/green]",
        "rules_none_to_delete": "\n[yellow]Aucune règle à supprimer.[/yellow]",
        "rules_delete_title": "Supprimer une règle",
        "rules_num_col": "N°",
        "rules_keyword_col": "Mot-clé",
        "rules_target_col": "Dossier cible",
        "rules_enter_number_to_delete": "Entrez le numéro de la règle à supprimer (ou Entrée pour annuler)",
        "rules_delete_canceled": "Suppression annulée.",
        "rules_deleted_success": "[green]Règle [bold]{pattern}[/bold] supprimée.[/green]",
        "rules_invalid_number": "[red]Numéro invalide.[/red]",
        "rules_invalid_input": "[red]Entrée invalide.[/red]",
        # Stats flow keys
        "stats_scanning": "Analyse de l'espace en cours...",
        "stats_no_files": "Aucun fichier trouvé dans le répertoire cible pour générer des statistiques.",
        "stats_root_label": "Racine",
        "stats_table_title": "Répartition de l'espace disque par catégorie",
        "stats_col_folder": "Dossier / Catégorie",
        "stats_col_files": "Fichiers",
        "stats_col_size": "Espace occupé",
        "stats_col_ratio": "Part",
        "stats_col_visual": "Jauge (Graphique)",
        "stats_total": "Total",
        "press_enter_continue": "\nAppuyez sur Entrée pour continuer"
    }
}

_current_lang = None

def get_current_language() -> str:
    """Retrieve user language settings from config file or fallback to locale auto-detection."""
    global _current_lang
    if _current_lang is not None:
        return _current_lang

    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                lang = data.get("language")
                if lang in TRANSLATIONS:
                    _current_lang = lang
                    return _current_lang
        except Exception:
            pass

    try:
        sys_lang, _ = locale.getlocale()
        if sys_lang and sys_lang.lower().startswith("fr"):
            _current_lang = "fr"
        else:
            _current_lang = "en"
    except Exception:
        _current_lang = "en"

    return _current_lang

def set_language(lang: str):
    """Save the user preferred language selection to the settings file."""
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump({"language": lang}, f, indent=4)
        except Exception:
            pass

def t(key: str, **kwargs) -> str:
    """Translate a given key using the active language choice."""
    lang = get_current_language()
    text = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text
