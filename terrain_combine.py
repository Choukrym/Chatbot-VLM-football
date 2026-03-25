"""
Voronoï 2 couleurs + flèches — 3 modes
  'snapshot'  → une frame à une minute précise
  'animation' → animation live sur un intervalle (zones qui bougent)
  'scanner'   → grille des N moments de pressing les plus intenses
"""

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import matplotlib.animation as animation
import numpy as np
from scipy.spatial import KDTree

FICHIER_TRACKING = r"C:\Users\chouk\Documents\tactical_pipeline\L1 J14 RCL MHSC 2-3 FRAN_RAW_GAME_OPT_TGV_25FPS$2248298.txt"
FICHIER_JOUEURS  = r"C:\Users\chouk\Documents\tactical_pipeline\L1 J14 RCL MHSC 2-3 FRAN_RAW_PLAYERS_OPT_TGV$2248298.csv"

TS_DEBUT = 1607803200000
FPS      = 25

GRIS_BG  = '#1a1a2e'
TEXTE    = '#eaeaea'

# ════════════════════════════════════════════════════════
# Config — CHANGE CES VALEURS
# ════════════════════════════════════════════════════════
MODE          = 'scanner'    # 'snapshot' | 'animation' | 'scanner'
MINUTE        = 23           # mode snapshot
PERIODE       = 1
MINUTE_DEBUT  = 61           # mode animation / scanner
MINUTE_FIN    = 61.333       # 61 min 20 sec
VITESSE       = 1            # 1=temps réel, 2=accéléré x2, 0.5=ralenti
NB_FRAMES     = 12           # mode scanner uniquement
DELTA_FLECHES = 10           # frames en avant pour les flèches (10 = 0.4 s)
RESOLUTION    = 130          # résolution grille animation (↓ = plus rapide)
RESOLUTION_HD = 220          # résolution snapshot / scanner
PAS_ANIM      = 3            # 1 frame affichée sur PAS_ANIM (3 = ~8fps fluide)
# ════════════════════════════════════════════════════════

# Couleurs Voronoï
RGBA_LENS = [0.90, 0.22, 0.27, 0.45]   # rouge  #E63946
RGBA_MHSC = [0.27, 0.48, 0.62, 0.45]   # bleu   #457B9D


# ── Parsers ───────────────────────────────────────────────────────────────────

def charger_joueurs(f):
    joueurs = {}
    with open(f, 'r', encoding='utf-8') as fh:
        for ligne in fh:
            ligne = ligne.strip().rstrip(';')
            if not ligne: continue
            c = ligne.split(',')
            if len(c) < 10: continue
            joueurs[int(c[9])] = {
                'nom':     f"{c[2].strip()} {c[3].strip()}",
                'maillot': int(c[0]),
                'poste':   int(c[4]),
                'team':    int(c[1]),
            }
    return joueurs


def parser_frame(ligne):
    ligne = ligne.strip()
    if '→' in ligne: _, reste = ligne.split('→', 1)
    else: reste = ligne
    p = reste.split(':')
    if len(p) < 3: return None
    try:
        ts  = int(p[0].split(';')[0])
        per = int(p[0].split(';')[1].split(',')[1])
    except: return None
    joueurs = []
    for j in p[1].split(';'):
        d = j.split(',')
        if len(d) < 5: continue
        try:
            joueurs.append({'team': int(d[0]), 'pid': int(d[1]),
                            'maillot': int(d[2]), 'x': float(d[3]), 'y': float(d[4])})
        except: continue
    ballon = None
    bd = p[2].rstrip(';').split(',')
    if len(bd) >= 2:
        try: ballon = (float(bd[0]), float(bd[1]))
        except: pass
    return ts, per, joueurs, ballon


def minute_vers_frame(minute, periode=1):
    if periode == 2: return int(45*60*FPS) + int(minute*60*FPS)
    return int(minute * 60 * FPS)


def positions_frame(toutes_lignes, frame_num):
    if frame_num < 0 or frame_num >= len(toutes_lignes): return {}
    r = parser_frame(toutes_lignes[frame_num])
    if r is None: return {}
    _, _, joueurs, _ = r
    return {j['pid']: (j['x'], j['y']) for j in joueurs}


# ── Terrain ───────────────────────────────────────────────────────────────────

def dessiner_terrain(ax):
    ax.set_facecolor('#1a3320')
    ax.set_xlim(0, 105); ax.set_ylim(0, 68)
    ax.plot([0, 105, 105, 0, 0], [0, 0, 68, 68, 0], 'w', lw=1.2, zorder=5)
    ax.axvline(52.5, color='w', lw=1.0, zorder=5)
    ax.add_patch(plt.Circle((52.5, 34), 9.15, fill=False, color='w', lw=1.0, zorder=5))
    ax.plot([0, 16.5, 16.5, 0],    [13.84, 13.84, 54.16, 54.16], 'w', lw=1.0, zorder=5)
    ax.plot([105, 88.5, 88.5, 105],[13.84, 13.84, 54.16, 54.16], 'w', lw=1.0, zorder=5)
    ax.set_xticks([]); ax.set_yticks([])


# ── Voronoï 2 couleurs avec zones individuelles visibles ─────────────────────

def dessiner_voronoi(ax, joueurs, resolution=130):
    """
    Rouge = Lens, Bleu = Montpellier.
    Les contours blancs séparent les zones individuelles de chaque joueur.
    """
    joueurs_champ = [j for j in joueurs if j['team'] in (0, 1)]
    if not joueurs_champ:
        return 0.0, 0.0

    positions  = np.array([[j['x'], j['y']] for j in joueurs_champ])
    teams_arr  = np.array([j['team'] for j in joueurs_champ])

    nx = resolution
    ny = int(resolution * 68 / 105)
    xs = np.linspace(0, 105, nx)
    ys = np.linspace(0, 68,  ny)
    xx, yy = np.meshgrid(xs, ys)
    grid   = np.c_[xx.ravel(), yy.ravel()]

    tree = KDTree(positions)
    _, idx_flat = tree.query(grid)

    # Couleur par équipe
    team_grid = teams_arr[idx_flat].reshape(ny, nx)
    img = np.zeros((ny, nx, 4))
    img[team_grid == 0] = RGBA_LENS
    img[team_grid == 1] = RGBA_MHSC
    ax.imshow(img, extent=[0, 105, 0, 68], origin='lower', aspect='auto', zorder=2)

    # Contours entre zones individuelles (même équipe ou non)
    idx_grid = idx_flat.reshape(ny, nx).astype(float)
    levels   = np.arange(-0.5, len(joueurs_champ))
    ax.contour(xs, ys, idx_grid, levels=levels,
               colors='white', linewidths=0.5, alpha=0.40, zorder=3)

    total    = nx * ny
    pct_lens = float((team_grid == 0).sum()) / total * 100
    pct_mhsc = float((team_grid == 1).sum()) / total * 100
    return pct_lens, pct_mhsc


# ── Flèches ───────────────────────────────────────────────────────────────────

def dessiner_fleches(ax, joueurs, pos_future):
    for j in joueurs:
        if j['team'] not in (0, 1) or j['pid'] not in pos_future:
            continue
        dx = pos_future[j['pid']][0] - j['x']
        dy = pos_future[j['pid']][1] - j['y']
        if np.hypot(dx, dy) > 0.1:
            color = '#FFD700' if j['team'] == 0 else '#aaddff'
            ax.quiver(j['x'], j['y'], dx, dy,
                      color=color, scale=1, scale_units='xy', angles='xy',
                      width=0.004, headwidth=4, headlength=4,
                      alpha=0.90, zorder=9)


# ── Dessin d'une frame complète sur un ax ─────────────────────────────────────

def _draw_frame(ax, frame_n, toutes_lignes, meta, resolution=130):
    r = parser_frame(toutes_lignes[frame_n])
    if r is None: return
    ts, periode, joueurs, ballon = r
    mins = int((ts - TS_DEBUT) / 60000)
    secs = int(((ts - TS_DEBUT) % 60000) / 1000)

    dessiner_terrain(ax)
    pct_l, pct_m = dessiner_voronoi(ax, joueurs, resolution)

    pos_future = positions_frame(toutes_lignes, frame_n + DELTA_FLECHES)

    for j in joueurs:
        if j['team'] == 0:   color, edge = '#E63946', 'white'
        elif j['team'] == 1: color, edge = '#457B9D', 'white'
        else: continue
        ax.scatter(j['x'], j['y'], c=color, s=130,
                   edgecolors=edge, zorder=6, linewidths=1.2)
        info = meta.get(j['pid'], {})
        ax.annotate(str(info.get('maillot', '')), (j['x'], j['y']),
                    textcoords='offset points', xytext=(0, 6),
                    ha='center', fontsize=6, color='white',
                    fontweight='bold', zorder=7)

    if ballon:
        ax.scatter(ballon[0], ballon[1], c='white', s=55,
                   edgecolors='black', zorder=8, linewidths=0.8)

    dessiner_fleches(ax, joueurs, pos_future)

    ax.set_title(
        f"P{periode}  {mins}'{secs:02d}\"  —  Lens {pct_l:.0f}%  •  MHSC {pct_m:.0f}%",
        color=TEXTE, fontsize=9, fontweight='bold', pad=3
    )
    ax.set_xlim(0, 105); ax.set_ylim(0, 68)


# ── MODE ANIMATION ────────────────────────────────────────────────────────────

def animer(f_debut, f_fin, toutes_lignes, meta, vitesse=1):
    pas     = max(1, PAS_ANIM)
    indices = list(range(f_debut, f_fin + 1, pas))

    fig, ax = plt.subplots(figsize=(13, 8.5), facecolor=GRIS_BG)
    fig.patch.set_facecolor(GRIS_BG)
    fig.suptitle("RC Lens vs Montpellier HSC  —  Voronoï + déplacements",
                 color=TEXTE, fontsize=11, fontweight='bold')

    patches = [
        mpatches.Patch(color='#E63946', alpha=0.8, label='RC Lens'),
        mpatches.Patch(color='#457B9D', alpha=0.8, label='Montpellier HSC'),
    ]
    ax.legend(handles=patches, loc='lower left', fontsize=8,
              facecolor='#16213e', labelcolor=TEXTE, framealpha=0.9)

    def _update(frame_n):
        ax.clear()
        ax.legend(handles=patches, loc='lower left', fontsize=8,
                  facecolor='#16213e', labelcolor=TEXTE, framealpha=0.9)
        _draw_frame(ax, frame_n, toutes_lignes, meta, RESOLUTION)

    interval_ms = int(40 * pas / vitesse)
    ani = animation.FuncAnimation(fig, _update, frames=indices,
                                  interval=interval_ms, repeat=False)
    plt.show()
    return ani


# ── MODE SCANNER ──────────────────────────────────────────────────────────────

def scanner_pressing(toutes_lignes, top_n=6, pas=50):
    resultats = []
    print("Scan du match...", end='', flush=True)
    for i, ligne in enumerate(toutes_lignes):
        if i % pas != 0: continue
        r = parser_frame(ligne)
        if r is None: continue
        _, _, joueurs, _ = r
        lens = np.array([[j['x'], j['y']] for j in joueurs if j['team'] == 0])
        mhsc = np.array([[j['x'], j['y']] for j in joueurs if j['team'] == 1])
        if len(lens) == 0 or len(mhsc) == 0: continue
        dists    = np.linalg.norm(lens[:, None] - mhsc[None, :], axis=2)
        mean_min = float(dists.min(axis=1).mean())
        resultats.append((mean_min, i))
    resultats.sort()
    print(f" {len(resultats)} frames scannées")
    return [r[1] for r in resultats[:top_n]]


def afficher_grille(indices, toutes_lignes, meta, titre=''):
    n     = len(indices)
    ncols = 3
    nrows = int(np.ceil(n / ncols))
    fig   = plt.figure(figsize=(ncols * 5.5, nrows * 3.8), facecolor=GRIS_BG)
    fig.suptitle(f"RC Lens vs Montpellier HSC  —  {titre}",
                 color=TEXTE, fontsize=12, fontweight='bold', y=0.99)
    gs = gridspec.GridSpec(nrows, ncols, figure=fig,
                           hspace=0.22, wspace=0.04,
                           left=0.02, right=0.98, top=0.94, bottom=0.03)
    for i, frame_n in enumerate(indices):
        row, col = divmod(i, ncols)
        ax = fig.add_subplot(gs[row, col])
        _draw_frame(ax, int(frame_n), toutes_lignes, meta, RESOLUTION_HD)
        print(f"  ✓ frame {frame_n}")

    patches = [
        mpatches.Patch(color='#E63946', alpha=0.8, label='RC Lens'),
        mpatches.Patch(color='#457B9D', alpha=0.8, label='Montpellier HSC'),
    ]
    fig.get_axes()[-1].legend(handles=patches, loc='lower left', fontsize=6,
                              facecolor='#16213e', labelcolor=TEXTE, framealpha=0.9)
    return fig


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    meta = charger_joueurs(FICHIER_JOUEURS)

    print("Chargement tracking...", end='', flush=True)
    with open(FICHIER_TRACKING, 'r', encoding='utf-8') as f:
        toutes_lignes = f.readlines()
    print(f" {len(toutes_lignes)} frames")

    if MODE == 'snapshot':
        frame_n = min(minute_vers_frame(MINUTE, PERIODE), len(toutes_lignes) - 1)
        fig, ax = plt.subplots(figsize=(13, 8.5), facecolor=GRIS_BG)
        fig.suptitle("RC Lens vs Montpellier HSC  —  Voronoï + déplacements",
                     color=TEXTE, fontsize=11, fontweight='bold')
        _draw_frame(ax, frame_n, toutes_lignes, meta, RESOLUTION_HD)
        patches = [
            mpatches.Patch(color='#E63946', alpha=0.8, label='RC Lens'),
            mpatches.Patch(color='#457B9D', alpha=0.8, label='Montpellier HSC'),
        ]
        ax.legend(handles=patches, loc='lower left', fontsize=8,
                  facecolor='#16213e', labelcolor=TEXTE, framealpha=0.9)
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        fname = fr"C:\Users\chouk\Documents\tactical_pipeline\terrain_combine_{MINUTE}.png"
        plt.savefig(fname, dpi=150, bbox_inches='tight', facecolor=GRIS_BG)
        print(f"Sauvegardé → {fname}")
        plt.show()

    elif MODE == 'animation':
        f_debut = max(0, min(minute_vers_frame(MINUTE_DEBUT, PERIODE), len(toutes_lignes) - 1))
        f_fin   = max(0, min(minute_vers_frame(MINUTE_FIN,   PERIODE), len(toutes_lignes) - 1))
        print(f"Animation {MINUTE_DEBUT}'→{MINUTE_FIN}' ({f_fin - f_debut} frames, pas={PAS_ANIM})")
        animer(f_debut, f_fin, toutes_lignes, meta, VITESSE)

    else:  # scanner
        f_debut  = max(0, min(minute_vers_frame(MINUTE_DEBUT, PERIODE), len(toutes_lignes) - 1))
        f_fin    = max(0, min(minute_vers_frame(MINUTE_FIN,   PERIODE), len(toutes_lignes) - 1))
        indices  = list(np.linspace(f_debut, f_fin, NB_FRAMES, dtype=int))
        print(f"Scanner {MINUTE_DEBUT}'→{MINUTE_FIN}' ({NB_FRAMES} snapshots)")
        fig      = afficher_grille(indices, toutes_lignes, meta,
                                   titre=f"{MINUTE_DEBUT}'→{MINUTE_FIN}'  P{PERIODE}")
        fname    = fr"C:\Users\chouk\Documents\tactical_pipeline\terrain_combine_scanner.png"
        plt.savefig(fname, dpi=140, bbox_inches='tight', facecolor=GRIS_BG)
        print(f"Sauvegardé → {fname}")
        plt.show()


if __name__ == '__main__':
    main()
