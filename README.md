# 🗄️ Cabinet - Organisateur de Téléchargements CLI

**Cabinet** est un outil en ligne de commande (CLI) élégant, ultra-rapide et sécurisé écrit en Python. Il vous permet de désencombrer et d'organiser automatiquement votre dossier `Downloads` (Téléchargements) en un clic.

Doté d'une interface graphique en ligne de commande moderne et colorée propulsée par `rich`, Cabinet vous permet de trier vos fichiers selon plusieurs stratégies, de prévisualiser l'arborescence finale avant tout déplacement, et même d'annuler la dernière opération si vous changez d'avis.

---

## ✨ Fonctionnalités

*   **⚡ Rangement en 1 clic :** Plus besoin de trier manuellement vos fichiers téléchargés.
*   **👁️ Prévisualisation Intégrée :** Affiche une arborescence claire (`rich.tree`) de la structure cible avant de déplacer le moindre fichier.
*   **🛡️ Option d'Annulation (Undo) :** Enregistre un historique local sécurisé permettant de restaurer vos fichiers à leur place initiale.
*   **🔀 4 Stratégies de Tri :**
    1.  **Par Catégorie** (Images, Documents, Code, Archives, Vidéos, etc.)
    2.  **Par Date** (Rangement automatique par `Année-Mois/`)
    3.  **Par Extension** (Tri direct par extension de fichier : `PNG/`, `PDF/`, `ZIP/`...)
    4.  **Mode Hybride** (Classement par Catégories, puis sous-dossiers par `Année-Mois/`)
*   **🎨 Esthétique Premium :** Des couleurs vibrantes, des spinners animés et des barres de progression fluides.
*   **🛠️ Gestion de Conflits :** Si un fichier existe déjà dans le dossier cible, Cabinet le renomme intelligemment (`fichier (1).pdf`) pour ne rien écraser.

---

## 🚀 Installation rapide

Cabinet est conçu pour être installé et exécuté très simplement.

### Option 1 : Installation Globale avec Pip (Recommandé)

Vous pouvez installer Cabinet directement à partir du dossier du projet. Ouvrez votre terminal à la racine de ce dossier et lancez :

```bash
pip install .
```

*Une fois installé, vous pouvez lancer l'outil de n'importe où dans votre terminal en tapant simplement :*

```bash
cabinet
```

*(Si vous préférez installer l'outil en mode développement pour pouvoir modifier le code source en temps réel, utilisez `pip install -e .`)*

### Option 2 : Utilisation avec un environnement virtuel (Isolé)

Si vous préférez ne pas installer de paquets globalement sur votre système :

1.  **Créez et activez un environnement virtuel :**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
2.  **Installez les dépendances et Cabinet :**
    ```bash
    pip install .
    ```
3.  **Lancez l'outil :**
    ```bash
    cabinet
    ```

---

## 📖 Utilisation

Lancez simplement la commande `cabinet` dans votre terminal. L'interface interactive s'affiche :

1.  **Sélectionnez une option** en entrant son numéro (1 à 6).
2.  **Visualisez l'arborescence** simulée dans la console.
3.  **Confirmez le déplacement** (`y` pour Oui, `n` pour Non).
4.  Une barre de progression s'affiche pendant le déplacement, suivie d'un **tableau récapitulatif détaillé** affichant le nom des fichiers déplacés, leur destination finale et leur taille individuelle.

### Annulation d'un rangement (Undo)

Si vous avez fait une erreur de rangement :
1. Relancez `cabinet`.
2. Choisissez l'option **5. Annuler le dernier rangement**.
3. Confirmez la restauration. Les fichiers seront instantanément replacés à la racine de votre dossier `Downloads`.

---

## 🔧 Personnalisation

Vous pouvez modifier les extensions associées à chaque dossier cible dans le fichier [`cabinet/config.py`](file:///Users/moussandou/Code/Organized/cabinet/config.py). 

Par exemple, pour ajouter une nouvelle extension d'image :
```python
"Images": [
    ".jpg", ".jpeg", ".png", ... , ".new_extension"
]
```
