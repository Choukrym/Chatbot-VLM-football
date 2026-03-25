"""
Visualisation neutre du match — déplacements + flèches
Pas d'analyse défensive, juste regarder le match.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.animation as animation
import numpy as np

# ─── Fichiers ────────────────────────────────────────────────────────────────
FICHIER_TRACKING = r"C:\Users\chouk\Documents\tactical_pipeline\L1 J14 RCL MHSC 2-3 FRAN_RAW_GAME_OPT_TGV_25FPS$2248298.txt"
FICHIER_JOUEURS  = r"C:\Users\chouk\Documents\tactical_pipeline\L1 J14 RCL MHSC 2-3 FRAN_RAW_PLAYERS_OPT_TGV$2248298.csv"

TS_DEBUT = 1607803200000
FPS      = 25

# ════════════════════════════════════════════════════════════════════════════
# Config — CHANGE CES VALEURS
# ════════════════════════════════════════════════════════════════════════════
MODE         = 'scanner'    # 'minute' | 'sequence' | 'scanner'

MINUTE       = 23           # mode 'minute' uniquement
PERIODE      = 1

MINUTE_DEBUT = 61           # mode 'sequence' et 'scanner'
MINUTE_FIN   = 61.333       # 61 min 20 sec
VITESSE      = 1            # 1=temps réel, 0.5=ralenti, 2=accéléré (mode 'sequence')

NB_SNAPSHOTS = 12           # mode 'scanner' : combien de snapshots à afficher

DELTA_FLECHES = 10          # frames en avance pour les flèches (10 = 0.4 s)
# ════════════════════════════════════════════════════════════════════════════

# Couleurs équipes
COULEUR_LENS  = '#E63946'   # rouge
COULEUR_MHSC  = '#457B9D'   # bleu
COULEUR_ARBIT = '#888888'   # gris


# ── Parsers ──────────────────────────────────────────────────────────────────

def charger_joueurs(fichier_csv):
    joueurs = {}
    with open(fichier_csv, 'r', encoding='utf-8') as f:
        for ligne in f:
            ligne = ligne.strip().rstrip(';')
            if not ligne:
                continue
            cols = ligne.split(',')
            if len(cols) < 10:
                continue
            joueurs[int(cols[9])] = {
                'nom':     f"{cols[2].strip()} {cols[3].strip()}",
                'maillot': int(cols[0]),
                'poste':   int(cols[4]),
                'team':    int(cols[1]),
            }
    return joueurs


def parser_frame(ligne):
    ligne = ligne.strip()
    if '→' in ligne:
        _, reste = ligne.split('→', 1)
    else:
        reste = ligne
    parties = reste.split(':')
    if len(parties) < 3:
        return None
    meta = parties[0].split(';')
    try:
        timestamp_ms = int(meta[0])
        periode      = int(meta[1].split(',')[1])
    except (IndexError, ValueError):
        return None
    joueurs = []
    for j in parties[1].split(';'):
        d = j.split(',')
        if len(d) < 5:
            continue
        try:
            joueurs.append({'team': int(d[0]), 'pid': int(d[1]),
                            'maillot': int(d[2]), 'x': float(d[3]), 'y': float(d[4])})
        except ValueError:
            continue
    ballon = None
    bd = parties[2].rstrip(';').split(',')
    if len(bd) >= 2:
        try:
            ballon = (float(bd[0]), float(bd[1]))
        except ValueError:
            pass
    return timestamp_ms, periode, joueurs, ballon


def minute_vers_frame(minute, periode=1):
    if periode == 2:
        return int(45 * 60 * FPS) + int(minute * 60 * FPS)
    return int(minute * 60 * FPS)


def positions_frame(toutes_lignes, frame_num):
    """Retourne {pid: (x, y)} pour une frame, ou {} si invalide."""
    if frame_num < 0 or frame_num >= len(toutes_lignes):
        return {}
    r = parser_frame(toutes_lignes[frame_num])
    if r is None:
        return {}
    _, _, joueurs, _ = r
    return {j['pid']: (j['x'], j['y']) for j in joueurs}


# ── Dessin ───────────────────────────────────────────────────────────────────

def dessiner_terrain(ax):
    ax.set_facecolor('#2d6a4f')
    ax.set_xlim(0, 105)
    ax.set_ylim(0, 68)
    ax.plot([0, 105, 105, 0, 0], [0, 0, 68, 68, 0], 'w', lw=1.8)
    ax.axvline(52.5, color='w', lw=1.4)
    ax.add_patch(plt.Circle((52.5, 34), 9.15, fill=False, color='w', lw=1.4))
    ax.plot([0, 16.5, 16.5, 0],       [13.84, 13.84, 54.16, 54.16], 'w', lw=1.4)
    ax.plot([105, 88.5, 88.5, 105],    [13.84, 13.84, 54.16, 54.16], 'w', lw=1.4)
    ax.set_xticks([])
    ax.set_yticks([])


def couleur_joueur(team):
    if team == 0:
        return COULEUR_LENS
    elif team == 1:
        return COULEUR_MHSC
    return COULEUR_ARBIT


def dessiner_joueurs(ax, joueurs, meta_joueurs):
    for j in joueurs:
        color = couleur_joueur(j['team'])
        size  = 180 if j['team'] in (0, 1) else 60
        ax.scatter(j['x'], j['y'], c=color, s=size,
                   edgecolors='white', zorder=5, linewidths=1.4)
        if j['team'] in (0, 1):
            info = meta_joueurs.get(j['pid'], {})
            ax.annotate(str(info.get('maillot', '')),
                        (j['x'], j['y']),
                        textcoords='offset points', xytext=(0, 7),
                        ha='center', fontsize=7, color='white', fontweight='bold', zorder=6)


def dessiner_fleches(ax, joueurs, pos_future):
    """Flèches de déplacement : or pour Lens, bleu clair pour Montpellier."""
    couleurs_fleches = {0: '#FFD700', 1: '#aaddff'}
    for j in joueurs:
        if j['team'] not in (0, 1):
            continue
        if j['pid'] not in pos_future:
            continue
        dx = pos_future[j['pid']][0] - j['x']
        dy = pos_future[j['pid']][1] - j['y']
        if np.hypot(dx, dy) > 0.1:
            ax.quiver(j['x'], j['y'], dx, dy,
                      color=couleurs_fleches[j['team']],
                      scale=1, scale_units='xy', angles='xy',
                      width=0.003, headwidth=8, headlength=8,
                      alpha=0.85, zorder=9)


def dessiner_ballon(ax, ballon):
    if ballon:
        ax.scatter(ballon[0], ballon[1], c='white', s=80,
                   edgecolors='black', zorder=8, linewidths=1.2)


def legende(ax):
    patches = [
        mpatches.Patch(color=COULEUR_LENS, label='RC Lens'),
        mpatches.Patch(color=COULEUR_MHSC, label='Montpellier HSC'),
        mpatches.Patch(color='white',      label='Ballon'),
    ]
    ax.legend(handles=patches, loc='lower left', fontsize=8,
              facecolor='#1a2035', labelcolor='white', framealpha=0.85)


# ── Modes ────────────────────────────────────────────────────────────────────

def mode_minute(minute, periode=1):
    """Affiche une frame à un instant précis."""
    meta_joueurs = charger_joueurs(FICHIER_JOUEURS)
    with open(FICHIER_TRACKING, 'r', encoding='utf-8') as f:
        lignes = f.readlines()

    frame_num = min(minute_vers_frame(minute, periode), len(lignes) - 1)
    r = parser_frame(lignes[frame_num])
    if r is None:
        print("Frame non parseable.")
        return

    timestamp_ms, per, joueurs, ballon = r
    pos_future = positions_frame(lignes, frame_num + DELTA_FLECHES)

    mins = int((timestamp_ms - TS_DEBUT) / 60000)
    secs = int(((timestamp_ms - TS_DEBUT) % 60000) / 1000)

    fig, ax = plt.subplots(figsize=(12, 7.5))
    fig.patch.set_facecolor('#1a2035')
    dessiner_terrain(ax)
    dessiner_joueurs(ax, joueurs, meta_joueurs)
    dessiner_fleches(ax, joueurs, pos_future)
    dessiner_ballon(ax, ballon)
    legende(ax)

    ax.set_title(f"P{per}  {mins}'{secs:02d}\"  —  RC Lens vs Montpellier HSC",
                 color='white', fontsize=11, fontweight='bold', pad=8)
    fig.tight_layout()
    plt.show()


def mode_sequence(minute_debut, minute_fin, periode=1, vitesse=1):
    """Animation fluide d'une séquence de jeu."""
    meta_joueurs = charger_joueurs(FICHIER_JOUEURS)

    print("Chargement tracking...", end='', flush=True)
    with open(FICHIER_TRACKING, 'r', encoding='utf-8') as f:
        toutes_lignes = f.readlines()
    print(f" {len(toutes_lignes)} frames")

    f_debut = max(0, min(minute_vers_frame(minute_debut, periode), len(toutes_lignes) - 1))
    f_fin   = max(0, min(minute_vers_frame(minute_fin,   periode), len(toutes_lignes) - 1))

    pas_anim = max(1, int(1 / vitesse))
    indices  = list(range(f_debut, f_fin, pas_anim))
    print(f"Animation {minute_debut}'→{minute_fin}' ({len(indices)} frames, pas={pas_anim})")

    fig, ax = plt.subplots(figsize=(12, 7.5))
    fig.patch.set_facecolor('#1a2035')
    plt.tight_layout()

    patches = [
        mpatches.Patch(color=COULEUR_LENS, label='RC Lens'),
        mpatches.Patch(color=COULEUR_MHSC, label='Montpellier HSC'),
    ]

    def _draw(frame_num):
        ax.clear()
        dessiner_terrain(ax)

        r = parser_frame(toutes_lignes[frame_num])
        if r is None:
            return

        timestamp_ms, per, joueurs, ballon = r
        pos_future = positions_frame(toutes_lignes, frame_num + DELTA_FLECHES)

        dessiner_joueurs(ax, joueurs, meta_joueurs)
        dessiner_fleches(ax, joueurs, pos_future)
        dessiner_ballon(ax, ballon)

        ax.legend(handles=patches, loc='lower left', fontsize=8,
                  facecolor='#1a2035', labelcolor='white', framealpha=0.85)

        mins = int((timestamp_ms - TS_DEBUT) / 60000)
        secs = int(((timestamp_ms - TS_DEBUT) % 60000) / 1000)
        ax.set_title(f"P{per}  {mins}'{secs:02d}\"  —  RC Lens vs Montpellier HSC",
                     color='white', fontsize=11, fontweight='bold', pad=8)
        ax.set_xlim(0, 105)
        ax.set_ylim(0, 68)

    intervalle_ms = int(40 / vitesse)
    ani = animation.FuncAnimation(fig, _draw, frames=indices,
                                   interval=intervalle_ms, repeat=False)
    plt.show()
    return ani


def mode_scanner(minute_debut, minute_fin, periode=1, nb_snapshots=8):
    """
    Affiche NB_SNAPSHOTS instantanés régulièrement espacés
    entre minute_debut et minute_fin.
    """
    meta_joueurs = charger_joueurs(FICHIER_JOUEURS)

    print("Chargement tracking...", end='', flush=True)
    with open(FICHIER_TRACKING, 'r', encoding='utf-8') as f:
        toutes_lignes = f.readlines()
    print(f" {len(toutes_lignes)} frames")

    f_debut = max(0, min(minute_vers_frame(minute_debut, periode), len(toutes_lignes) - 1))
    f_fin   = max(0, min(minute_vers_frame(minute_fin,   periode), len(toutes_lignes) - 1))
    indices = np.linspace(f_debut, f_fin, nb_snapshots, dtype=int)

    ncols = 4
    nrows = int(np.ceil(nb_snapshots / ncols))
    fig   = plt.figure(figsize=(ncols * 4.5, nrows * 3.2))
    fig.patch.set_facecolor('#1a2035')
    fig.suptitle(f"RC Lens vs Montpellier HSC  —  {minute_debut}'→{minute_fin}'  P{periode}",
                 color='white', fontsize=13, fontweight='bold')

    for i, frame_num in enumerate(indices):
        r = parser_frame(toutes_lignes[frame_num])
        if r is None:
            continue
        timestamp_ms, per, joueurs, ballon = r
        pos_future = positions_frame(toutes_lignes, int(frame_num) + DELTA_FLECHES)

        ax = fig.add_subplot(nrows, ncols, i + 1)
        ax.set_facecolor('#1a2035')
        dessiner_terrain(ax)
        dessiner_joueurs(ax, joueurs, meta_joueurs)
        dessiner_fleches(ax, joueurs, pos_future)
        dessiner_ballon(ax, ballon)

        mins = int((timestamp_ms - TS_DEBUT) / 60000)
        secs = int(((timestamp_ms - TS_DEBUT) % 60000) / 1000)
        ax.set_title(f"{mins}'{secs:02d}\"", color='white', fontsize=8, fontweight='bold', pad=3)
        print(f"  ✓ {mins}'{secs:02d}\"")

    patches = [
        mpatches.Patch(color=COULEUR_LENS, label='RC Lens'),
        mpatches.Patch(color=COULEUR_MHSC, label='Montpellier HSC'),
    ]
    fig.legend(handles=patches, loc='lower center', ncol=2, fontsize=9,
               facecolor='#1a2035', labelcolor='white', framealpha=0.85)
    plt.tight_layout(rect=[0, 0.04, 1, 0.95])
    plt.show()


# ── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':

    if MODE == 'minute':
        frame = minute_vers_frame(MINUTE, PERIODE)
        print(f"Affichage à {MINUTE}' P{PERIODE} → frame {frame}")
        mode_minute(MINUTE, PERIODE)

    elif MODE == 'sequence':
        mode_sequence(MINUTE_DEBUT, MINUTE_FIN, PERIODE, VITESSE)

    elif MODE == 'scanner':
        mode_scanner(MINUTE_DEBUT, MINUTE_FIN, PERIODE, NB_SNAPSHOTS)
