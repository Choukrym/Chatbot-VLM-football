"""
Détection et analyse des remontées de bloc défensif
────────────────────────────────────────────────────
Détecte automatiquement les séquences où :
  1. Le ballon est dans le camp défensif
  2. La ligne défensive monte collectivement (x moyen progresse)
  3. Mesure la coordination pendant ce mouvement (écart-type des x défenseurs)

3 modes :
  'scanner'   → détecte toutes les remontées du match et les classe
  'sequence'  → visualise une remontée spécifique en animation interactive
  'rapport'   → produit une figure résumé pour le rapport
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.widgets import Button, Slider
import numpy as np

# ─── Fichiers ────────────────────────────────────────────────────────────────
FICHIER_TRACKING = r"C:\Users\chouk\Documents\tactical_pipeline\L1 J14 RCL MHSC 2-3 FRAN_RAW_GAME_OPT_TGV_25FPS$2248298.txt"
FICHIER_JOUEURS  = r"C:\Users\chouk\Documents\tactical_pipeline\L1 J14 RCL MHSC 2-3 FRAN_RAW_PLAYERS_OPT_TGV$2248298.csv"

TS_DEBUT = 1607803200000
FPS      = 25

# ════════════════════════════════════════════════════════════════════════════
# Config
# ════════════════════════════════════════════════════════════════════════════
MODE          = 'sequence'    # 'scanner' | 'sequence' | 'rapport'

EQUIPE        = 0           # équipe dont on analyse la ligne défensive
                            # 0 = RC Lens, 1 = Montpellier

# Paramètres de détection
SEUIL_MONTEE  = 3.0         # mètres : montée minimale du x moyen des DEF
DUREE_MIN     = 15          # frames minimum (~0.6 s)
DUREE_MAX     = 300         # frames maximum (~12 s)
PAS_SCAN      = 3           # analyser 1 frame sur 3

# Mode 'sequence' — deux façons de choisir la séquence :
#   Option A : par plage de minutes (si MINUTE_DEBUT > 0)
#   Option B : par index de remontée détectée (si MINUTE_DEBUT = 0)
MINUTE_DEBUT   = 55         # ← mets 0 pour utiliser INDEX_REMONTEE
MINUTE_FIN     = 61.333     # 61 min 20 sec
PERIODE        = 1
INDEX_REMONTEE = 0
VITESSE        = 1          # 1=temps réel, 2=accéléré, 0.5=ralenti

# Mode 'rapport'
TOP_N         = 6

# Mode 'scanner'
NB_SNAPSHOTS  = 12          # nombre de snapshots

# ─── Score ───────────────────────────────────────────────────────────────────
SCORE_LENS    = 2
SCORE_MHSC    = 3
# Timestamps (ms) de chaque but — laisse vide [] pour score fixe
# ex : TS_BUTS_LENS = [TS_DEBUT + 23*60000, TS_DEBUT + 78*60000]
TS_BUTS_LENS  = []
TS_BUTS_MHSC  = []
# ════════════════════════════════════════════════════════════════════════════

COULEUR_DEF   = '#E63946' if EQUIPE == 0 else '#457B9D'
COULEUR_ADV   = '#457B9D' if EQUIPE == 0 else '#E63946'
NOM_EQUIPE    = 'RC Lens' if EQUIPE == 0 else 'Montpellier'
NOM_ADV       = 'Montpellier' if EQUIPE == 0 else 'RC Lens'
GRIS_BG       = '#1a1a2e'
TEXTE         = '#eaeaea'

# ─── Dimensions terrain (FIFA standard) ──────────────────────────────────────
Y_BUT_BAS   = (68 - 7.32) / 2    # 30.34 m
Y_BUT_HAUT  = (68 + 7.32) / 2    # 37.66 m
Y_6M_BAS    = (68 - 18.32) / 2   # 24.84 m  (surface de but)
Y_6M_HAUT   = (68 + 18.32) / 2   # 43.16 m


# ── Score helper ──────────────────────────────────────────────────────────────

def score_a_linstant(ts):
    """Retourne (buts_lens, buts_mhsc) au timestamp ts."""
    if TS_BUTS_LENS or TS_BUTS_MHSC:
        return (sum(1 for t in TS_BUTS_LENS if t <= ts),
                sum(1 for t in TS_BUTS_MHSC if t <= ts))
    return SCORE_LENS, SCORE_MHSC


# ── Parsers ───────────────────────────────────────────────────────────────────

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
                'poste':   int(cols[4]),   # 1=ATT 2=MIL 3=DEF 4=GK
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
        ts      = int(meta[0])
        periode = int(meta[1].split(',')[1])
    except (IndexError, ValueError):
        return None
    joueurs = []
    for j in parties[1].split(';'):
        d = j.split(',')
        if len(d) < 5:
            continue
        try:
            joueurs.append({'team': int(d[0]), 'pid': int(d[1]),
                            'maillot': int(d[2]),
                            'x': float(d[3]), 'y': float(d[4])})
        except ValueError:
            continue
    ballon = None
    bd = parties[2].rstrip(';').split(',')
    if len(bd) >= 2:
        try:
            ballon = (float(bd[0]), float(bd[1]))
        except ValueError:
            pass
    return ts, periode, joueurs, ballon


def minute_vers_frame(minute, periode=1):
    if periode == 2:
        return int(45 * 60 * FPS) + int(minute * 60 * FPS)
    return int(minute * 60 * FPS)


def ts_vers_min_sec(ts):
    elapsed = ts - TS_DEBUT
    return int(elapsed / 60000), int((elapsed % 60000) / 1000)


# ── Métriques défensives ──────────────────────────────────────────────────────

def metriques_def(joueurs, meta_joueurs, equipe):
    defenseurs = [
        j for j in joueurs
        if j['team'] == equipe
        and meta_joueurs.get(j['pid'], {}).get('poste') == 3
    ]
    if len(defenseurs) < 3:
        return None, None, 0
    xs = np.array([d['x'] for d in defenseurs])
    return float(np.mean(xs)), float(np.std(xs)), len(defenseurs)


# ── Détection des remontées ───────────────────────────────────────────────────

def detecter_remontees(toutes_lignes, meta_joueurs):
    remontees   = []
    en_remontee = False
    x_debut     = None
    frame_debut = None
    ts_debut_r  = None
    per_debut   = None
    std_pendant = []

    print(f"Scan du match ({len(toutes_lignes)} frames, pas={PAS_SCAN})...", end='', flush=True)

    for i in range(0, len(toutes_lignes), PAS_SCAN):
        r = parser_frame(toutes_lignes[i])
        if r is None:
            continue
        ts, periode, joueurs, ballon = r

        x_moy, std_x, nb_def = metriques_def(joueurs, meta_joueurs, EQUIPE)
        if x_moy is None:
            continue

        if EQUIPE == 0:
            ballon_dans_camp = (ballon is not None and
                                (ballon[0] < 52.5 if periode == 1 else ballon[0] > 52.5))
        else:
            ballon_dans_camp = (ballon is not None and
                                (ballon[0] > 52.5 if periode == 1 else ballon[0] < 52.5))

        if not en_remontee:
            if ballon_dans_camp:
                en_remontee = True
                x_debut     = x_moy
                frame_debut = i
                ts_debut_r  = ts
                per_debut   = periode
                std_pendant = [std_x]
        else:
            std_pendant.append(std_x)
            duree = i - frame_debut
            if EQUIPE == 0:
                montee = (x_moy - x_debut) if per_debut == 1 else (x_debut - x_moy)
            else:
                montee = (x_debut - x_moy) if per_debut == 1 else (x_moy - x_debut)

            if not ballon_dans_camp or duree > DUREE_MAX:
                if duree >= DUREE_MIN and montee >= SEUIL_MONTEE:
                    mins, secs = ts_vers_min_sec(ts_debut_r)
                    remontees.append({
                        'frame_debut':  frame_debut,
                        'frame_fin':    i,
                        'ts_debut':     ts_debut_r,
                        'periode':      per_debut,
                        'minute':       f"{mins}'{secs:02d}\"",
                        'duree_frames': duree,
                        'duree_sec':    round(duree / FPS, 1),
                        'montee_m':     round(montee, 2),
                        'std_moy':      round(float(np.mean(std_pendant)), 2),
                        'std_min':      round(float(np.min(std_pendant)),  2),
                        'std_max':      round(float(np.max(std_pendant)),  2),
                    })
                en_remontee = False
                x_debut     = None
                std_pendant = []

    remontees.sort(key=lambda r: r['montee_m'], reverse=True)
    print(f" {len(remontees)} remontées détectées")
    return remontees


def afficher_resultats(remontees, top_n=10):
    print(f"\n{'═'*72}")
    print(f"  TOP {top_n} remontées de bloc — {NOM_EQUIPE}")
    print(f"  Seuil : ≥ {SEUIL_MONTEE}m | Durée min : {DUREE_MIN} frames")
    print(f"{'═'*72}")
    print(f"  {'#':>2}  {'Minute':>8}  {'P':>2}  {'Montée':>8}  {'Durée':>7}  {'Coord. moy':>10}  {'Coord. min':>10}")
    print(f"  {'─'*66}")
    for k, r in enumerate(remontees[:top_n]):
        coord_label = "✓ bonne" if r['std_moy'] < 3.0 else ("△ moy." if r['std_moy'] < 5.0 else "✗ faible")
        print(f"  {k+1:>2}  {r['minute']:>8}  P{r['periode']}  "
              f"{r['montee_m']:>6.1f}m  {r['duree_sec']:>5.1f}s  "
              f"{r['std_moy']:>8.2f}m  {coord_label}")
    print(f"{'═'*72}")
    if remontees:
        moy_montee = np.mean([r['montee_m'] for r in remontees])
        moy_std    = np.mean([r['std_moy']  for r in remontees])
        moy_duree  = np.mean([r['duree_sec'] for r in remontees])
        print(f"\n  Résumé global sur {len(remontees)} remontées :")
        print(f"    Montée moyenne      : {moy_montee:.1f} m")
        print(f"    Durée moyenne       : {moy_duree:.1f} s")
        print(f"    Coordination moy.   : {moy_std:.2f} m (écart-type x défenseurs)")
        print(f"    → Plus l'écart-type est faible, plus la ligne monte en bloc coordonné")


# ── Visualisation terrain ─────────────────────────────────────────────────────

def dessiner_terrain(ax):
    ax.set_facecolor('#1a3320')
    ax.set_xlim(-3, 108)
    ax.set_ylim(-1, 69)

    # ── Contour + ligne médiane + cercle central ──
    ax.plot([0, 105, 105, 0, 0], [0, 0, 68, 68, 0], 'w', lw=1.5)
    ax.axvline(52.5, color='w', lw=1.2)
    ax.add_patch(plt.Circle((52.5, 34), 9.15, fill=False, color='w', lw=1.2))
    ax.scatter([52.5], [34], c='white', s=14, zorder=5)

    # ── Surfaces de réparation (16.5 m) ──
    ax.plot([0,   16.5, 16.5,  0],    [13.84, 13.84, 54.16, 54.16], 'w', lw=1.2)
    ax.plot([105, 88.5, 88.5, 105],   [13.84, 13.84, 54.16, 54.16], 'w', lw=1.2)

    # ── Surfaces de but (6 m) ──
    ax.plot([0,   5.5, 5.5,  0],      [Y_6M_BAS, Y_6M_BAS, Y_6M_HAUT, Y_6M_HAUT], 'w', lw=1.0)
    ax.plot([105, 99.5, 99.5, 105],   [Y_6M_BAS, Y_6M_BAS, Y_6M_HAUT, Y_6M_HAUT], 'w', lw=1.0)

    # ── Points de penalty ──
    ax.scatter([11, 94], [34, 34], c='white', s=16, zorder=5)

    # ── Arcs de cercle des surfaces (arc de 9.15m autour du point de penalty) ──
    theta = np.linspace(-np.radians(53), np.radians(53), 30)
    ax.plot(11 + 9.15 * np.cos(theta), 34 + 9.15 * np.sin(theta), 'w', lw=1.0)
    theta2 = np.linspace(np.radians(127), np.radians(233), 30)
    ax.plot(94 + 9.15 * np.cos(theta2), 34 + 9.15 * np.sin(theta2), 'w', lw=1.0)

    # ── Cages (en dehors de la ligne de but, profondeur ~2 m) ──
    ax.plot([0, -2, -2,  0],          [Y_BUT_BAS, Y_BUT_BAS, Y_BUT_HAUT, Y_BUT_HAUT], 'w', lw=2.2)
    ax.plot([105, 107, 107, 105],     [Y_BUT_BAS, Y_BUT_BAS, Y_BUT_HAUT, Y_BUT_HAUT], 'w', lw=2.2)

    ax.set_xticks([])
    ax.set_yticks([])


def positions_frame(toutes_lignes, frame_num):
    if frame_num < 0 or frame_num >= len(toutes_lignes):
        return {}
    r = parser_frame(toutes_lignes[frame_num])
    if r is None:
        return {}
    _, _, joueurs, _ = r
    return {j['pid']: (j['x'], j['y']) for j in joueurs}


def dessiner_fleches(ax, joueurs, pos_future, meta_joueurs):
    for j in joueurs:
        if j['team'] not in (0, 1, 3, 4) or j['pid'] not in pos_future:
            continue
        dx = pos_future[j['pid']][0] - j['x']
        dy = pos_future[j['pid']][1] - j['y']
        if np.hypot(dx, dy) > 0.1:
            color = '#FFD700' if j['team'] == 0 else '#aaddff'
            ax.quiver(j['x'], j['y'], dx, dy,
                      color=color, scale=1, scale_units='xy', angles='xy',
                      width=0.003, headwidth=8, headlength=8,
                      alpha=0.85, zorder=9)


def dessiner_ligne_defensive(ax, defenseurs, joueurs_adv):
    """
    Relie les défenseurs triés par y, couleur = pression adverse.
    Vert(>20m) / Jaune(12-20m) / Orange(5-12m) / Rouge(<5m)
    """
    if len(defenseurs) < 2:
        return

    defs_tries = sorted(defenseurs, key=lambda d: d['y'])
    xs = [d['x'] for d in defs_tries]
    ys = [d['y'] for d in defs_tries]
    x_moy = float(np.mean(xs))

    if joueurs_adv:
        dists   = sorted([abs(j['x'] - x_moy) for j in joueurs_adv])
        pression = float(np.mean(dists[:3])) if len(dists) >= 3 else float(np.mean(dists))
    else:
        pression = 30.0

    if pression < 5:
        couleur = '#ff3333'
    elif pression < 12:
        couleur = '#ff9900'
    elif pression < 20:
        couleur = '#ffee00'
    else:
        couleur = '#44ff88'

    epaisseur = max(1.5, min(6.0, 6.0 - pression * 0.15))
    ax.plot(xs, ys, color=couleur, lw=epaisseur, alpha=0.90,
            solid_capstyle='round', solid_joinstyle='round', zorder=8)
    ax.annotate(f'↔ {pression:.1f}m',
                xy=(x_moy, max(ys) + 1.5),
                ha='center', fontsize=6, color=couleur,
                fontweight='bold', zorder=10)


def draw_frame_annote(ax, frame_n, toutes_lignes, meta_joueurs, remontee):
    """Dessine une frame complète avec score, gardiens distincts et ligne défensive."""
    r = parser_frame(toutes_lignes[frame_n])
    if r is None:
        return
    ts, periode, joueurs, ballon = r
    mins, secs = ts_vers_min_sec(ts)

    dessiner_terrain(ax)

    defenseurs = [j for j in joueurs
                  if j['team'] == EQUIPE
                  and meta_joueurs.get(j['pid'], {}).get('poste') == 3]
    x_moy = np.mean([d['x'] for d in defenseurs]) if defenseurs else None
    std_x = np.std([d['x'] for d in defenseurs]) if len(defenseurs) > 1 else 0

    # Ligne défensive moyenne ± σ
    if x_moy is not None:
        ax.axvline(x_moy, color='#FFD700', lw=2, linestyle='--', alpha=0.85, zorder=4)
        ax.axvspan(x_moy - std_x, x_moy + std_x,
                   alpha=0.15, color='#FFD700', zorder=3)

    # Camp défensif (zone rouge selon période)
    if EQUIPE == 0:
        xmin_camp, xmax_camp = (0, 52.5) if periode == 1 else (52.5, 105)
    else:
        xmin_camp, xmax_camp = (52.5, 105) if periode == 1 else (0, 52.5)
    ax.axvspan(xmin_camp, xmax_camp, alpha=0.04, color='red', zorder=1)

    pos_future = positions_frame(toutes_lignes, frame_n + 10)
    dessiner_fleches(ax, joueurs, pos_future, meta_joueurs)

    # ── Joueurs ──
    for j in joueurs:
        poste = meta_joueurs.get(j['pid'], {}).get('poste')
        is_gk = (poste == 4)

        if j['team'] == EQUIPE or j['team'] == EQUIPE + 3:
            if poste == 3:       # Défenseur
                color, edge, size, marker = COULEUR_DEF, '#FFD700', 200, 'o'
            elif is_gk or j['team'] == EQUIPE + 3:  # Gardien équipe analysée
                color, edge, size, marker = COULEUR_DEF, '#00ff88',  230, 's'
            else:                # Mil / Att
                color, edge, size, marker = COULEUR_DEF, 'white',    130, 'o'
        elif j['team'] == (1 - EQUIPE) or j['team'] == (1 - EQUIPE) + 3:
            if is_gk or j['team'] == (1 - EQUIPE) + 3:  # Gardien adverse
                color, edge, size, marker = COULEUR_ADV, '#00ff88',  230, 's'
            else:
                color, edge, size, marker = COULEUR_ADV, 'white',    130, 'o'
        else:
            continue             # arbitre

        ax.scatter(j['x'], j['y'], c=color, s=size, marker=marker,
                   edgecolors=edge, zorder=5, linewidths=1.5)
        info = meta_joueurs.get(j['pid'], {})
        ax.annotate(str(info.get('maillot', '')), (j['x'], j['y']),
                    textcoords='offset points', xytext=(0, 7),
                    ha='center', fontsize=6.5, color='white',
                    fontweight='bold', zorder=6)

    if ballon:
        ax.scatter(ballon[0], ballon[1], c='white', s=70,
                   edgecolors='black', zorder=8, linewidths=1.0)

    # Ligne défensive colorée selon pression adverse
    joueurs_adv = [j for j in joueurs if j['team'] == (1 - EQUIPE)]
    dessiner_ligne_defensive(ax, defenseurs, joueurs_adv)


    # Progression remontée
    try:
        r0 = parser_frame(toutes_lignes[remontee['frame_debut']])
        x_moy_0, _, _ = metriques_def(r0[2], meta_joueurs, EQUIPE)
        montee_actuelle = x_moy - x_moy_0 if x_moy and x_moy_0 else 0
    except Exception:
        montee_actuelle = 0

    ax.set_title(
        f"P{periode}  {mins}'{secs:02d}\"  —  "
        f"Ligne déf. : {x_moy:.1f}m  |  σ = {std_x:.1f}m  |  "
        f"Montée : +{montee_actuelle:.1f}m",
        color=TEXTE, fontsize=8.5, fontweight='bold', pad=4
    )
    ax.set_xlim(-3, 108)
    ax.set_ylim(-1, 69)


# ── Mode sequence — animation interactive ─────────────────────────────────────

def mode_sequence(remontee, toutes_lignes, meta_joueurs, vitesse=1):
    mins, secs = ts_vers_min_sec(remontee['ts_debut'])
    print(f"\nAnimation {mins}'{secs:02d}\" | +{remontee['montee_m']}m | "
          f"{remontee['duree_sec']}s | σ moy = {remontee['std_moy']}m")

    f_debut = remontee['frame_debut']
    f_fin   = remontee['frame_fin']
    indices = list(range(f_debut, f_fin + 1, max(1, PAS_SCAN)))
    n       = len(indices)

    # ── Figure ──
    fig, ax = plt.subplots(figsize=(13, 9.5), facecolor=GRIS_BG)
    fig.patch.set_facecolor(GRIS_BG)
    fig.subplots_adjust(bottom=0.13, top=0.92, left=0.02, right=0.98)
    fig.suptitle(
        f"Remontée de bloc — {NOM_EQUIPE}  |  {mins}'{secs:02d}\"  "
        f"|  +{remontee['montee_m']}m en {remontee['duree_sec']}s",
        color=TEXTE, fontsize=11, fontweight='bold'
    )

    patches_leg = [
        mpatches.Patch(color=COULEUR_DEF, label=f'{NOM_EQUIPE} (○ DEF=contour or)'),
        mpatches.Patch(color=COULEUR_ADV, label=NOM_ADV),
        mpatches.Patch(color='#FFD700',   label='Ligne déf. ± σ', alpha=0.6),
        mpatches.Patch(color='#00ff88',   label='Gardien (carré ■)', alpha=0.8),
    ]

    # ── Slider de progression ──
    col_w = '#16213e'
    ax_slide = fig.add_axes([0.08, 0.058, 0.65, 0.022], facecolor='#0d1117')
    slider_pos = Slider(ax_slide, '', 0, max(n - 1, 1), valinit=0,
                        valstep=1, color='#457B9D', track_color='#0d1117')
    slider_pos.valtext.set_visible(False)
    slider_pos.label.set_visible(False)

    # Labels temps début / fin sous le slider
    r_s = parser_frame(toutes_lignes[indices[0]])
    r_e = parser_frame(toutes_lignes[indices[-1]])
    t0  = ts_vers_min_sec(r_s[0]) if r_s else (mins, secs)
    t1  = ts_vers_min_sec(r_e[0]) if r_e else (mins, secs)
    ax_slide.set_xlabel(
        f"{t0[0]}'{t0[1]:02d}\"  ──────────── ▶  {t1[0]}'{t1[1]:02d}\"",
        fontsize=7, color='#777777', labelpad=1
    )

    # ── Bouton Play / Pause ──
    ax_pp = fig.add_axes([0.75, 0.045, 0.06, 0.042], facecolor=col_w)
    btn_pp = Button(ax_pp, '⏸', color=col_w, hovercolor='#2a3a5e')
    btn_pp.label.set_color(TEXTE)
    btn_pp.label.set_fontsize(14)

    # ── Bouton Retour au début ──
    ax_rw = fig.add_axes([0.82, 0.045, 0.06, 0.042], facecolor=col_w)
    btn_rw = Button(ax_rw, '⏮', color=col_w, hovercolor='#2a3a5e')
    btn_rw.label.set_color(TEXTE)
    btn_rw.label.set_fontsize(14)

    # ── Bouton Fin ──
    ax_fw = fig.add_axes([0.89, 0.045, 0.06, 0.042], facecolor=col_w)
    btn_fw = Button(ax_fw, '⏭', color=col_w, hovercolor='#2a3a5e')
    btn_fw.label.set_color(TEXTE)
    btn_fw.label.set_fontsize(14)

    # ── État ──
    state = {'paused': False, 'idx': 0, 'lock': False}

    def render(idx):
        ax.clear()
        draw_frame_annote(ax, indices[idx], toutes_lignes, meta_joueurs, remontee)
        ax.legend(handles=patches_leg, loc='lower left', fontsize=7.5,
                  facecolor='#16213e', labelcolor=TEXTE, framealpha=0.9)
        fig.canvas.draw_idle()

    def tick(event=None):
        if state['paused']:
            return
        state['idx'] = (state['idx'] + 1) % n
        state['lock'] = True
        slider_pos.set_val(state['idx'])
        state['lock'] = False
        render(state['idx'])

    def on_slider(val):
        if state['lock']:
            return
        state['idx'] = int(val)
        render(state['idx'])

    def on_play_pause(_):
        state['paused'] = not state['paused']
        btn_pp.label.set_text('▶' if state['paused'] else '⏸')
        fig.canvas.draw_idle()

    def on_rewind(_):
        state['paused'] = True
        btn_pp.label.set_text('▶')
        state['idx'] = 0
        state['lock'] = True
        slider_pos.set_val(0)
        state['lock'] = False
        render(0)

    def on_forward(_):
        state['paused'] = True
        btn_pp.label.set_text('▶')
        state['idx'] = n - 1
        state['lock'] = True
        slider_pos.set_val(n - 1)
        state['lock'] = False
        render(n - 1)

    slider_pos.on_changed(on_slider)
    btn_pp.on_clicked(on_play_pause)
    btn_rw.on_clicked(on_rewind)
    btn_fw.on_clicked(on_forward)

    # Première frame
    render(0)

    # Timer — remplace FuncAnimation pour permettre le seek
    interval_ms = max(20, int(40 * PAS_SCAN / vitesse))
    timer = fig.canvas.new_timer(interval=interval_ms)
    timer.add_callback(tick)
    timer.start()

    plt.show()
    return timer   # garde une référence pour éviter le garbage collector


# ── Mode rapport (planche synthèse) ──────────────────────────────────────────

def mode_rapport(remontees, toutes_lignes, meta_joueurs, top_n=6):
    ncols = 3
    nrows = int(np.ceil(top_n / ncols))
    fig1  = plt.figure(figsize=(ncols * 5.5, nrows * 3.8), facecolor=GRIS_BG)
    fig1.suptitle(
        f"Top {top_n} remontées de bloc — {NOM_EQUIPE}  "
        f"(seuil ≥ {SEUIL_MONTEE}m, durée ≥ {DUREE_MIN/FPS:.1f}s)",
        color=TEXTE, fontsize=12, fontweight='bold', y=0.99
    )
    gs = gridspec.GridSpec(nrows, ncols, figure=fig1,
                           hspace=0.30, wspace=0.04,
                           left=0.02, right=0.98, top=0.93, bottom=0.03)

    for i, rem in enumerate(remontees[:top_n]):
        row, col = divmod(i, ncols)
        ax = fig1.add_subplot(gs[row, col])
        ax.set_facecolor(GRIS_BG)
        frame_mid = (rem['frame_debut'] + rem['frame_fin']) // 2
        draw_frame_annote(ax, frame_mid, toutes_lignes, meta_joueurs, rem)
        print(f"  ✓ remontée {i+1} — {rem['minute']}")

    patches = [
        mpatches.Patch(color=COULEUR_DEF, label=NOM_EQUIPE),
        mpatches.Patch(color=COULEUR_ADV, label=NOM_ADV),
        mpatches.Patch(color='#FFD700',   label='Ligne déf. ± σ', alpha=0.5),
        mpatches.Patch(color='#00ff88',   label='Gardien'),
    ]
    fig1.get_axes()[-1].legend(handles=patches, loc='lower left', fontsize=6,
                                facecolor='#16213e', labelcolor=TEXTE, framealpha=0.9)

    fname1 = r"C:\Users\chouk\Documents\tactical_pipeline\remontees_snapshots.png"
    plt.savefig(fname1, dpi=140, bbox_inches='tight', facecolor=GRIS_BG)
    print(f"Sauvegardé → {fname1}")

    # ── Figure 2 : scatter montée vs coordination ──────────────────────────────
    fig2, axes = plt.subplots(1, 2, figsize=(14, 5.5), facecolor=GRIS_BG)
    fig2.suptitle(
        f"Analyse des remontées de bloc — {NOM_EQUIPE}  ({len(remontees)} remontées détectées)",
        color=TEXTE, fontsize=12, fontweight='bold'
    )

    montees  = [r['montee_m']  for r in remontees]
    coords   = [r['std_moy']   for r in remontees]
    periodes = [r['periode']   for r in remontees]
    colors_pt = ['#E63946' if p == 1 else '#f4a261' for p in periodes]

    ax1 = axes[0]
    ax1.set_facecolor('#16213e')
    ax1.scatter(montees, coords, c=colors_pt, s=80, alpha=0.8, edgecolors='white', lw=0.5)
    ax1.set_xlabel('Amplitude de la montée (m)', color=TEXTE, fontsize=10)
    ax1.set_ylabel('Écart-type x défenseurs — σ (m)\n← Meilleure coordination', color=TEXTE, fontsize=10)
    ax1.set_title('Montée vs Coordination', color=TEXTE, fontsize=10, fontweight='bold')
    ax1.tick_params(colors=TEXTE)
    ax1.spines[:].set_color('#444')
    if len(montees) > 2:
        z = np.polyfit(montees, coords, 1)
        p = np.poly1d(z)
        xs_fit = np.linspace(min(montees), max(montees), 100)
        ax1.plot(xs_fit, p(xs_fit), '--', color='#aaaaaa', lw=1.2, alpha=0.7)
    ax1.legend(handles=[mpatches.Patch(color='#E63946', label='Période 1'),
                         mpatches.Patch(color='#f4a261', label='Période 2')],
               fontsize=8, facecolor='#1a1a2e', labelcolor=TEXTE, framealpha=0.8)

    ax2 = axes[1]
    ax2.set_facecolor('#16213e')
    ax2.hist(coords, bins=12, color=COULEUR_DEF, alpha=0.75, edgecolor='white', lw=0.5)
    ax2.axvline(np.mean(coords), color='#FFD700', lw=2, linestyle='--',
                label=f'Moyenne : {np.mean(coords):.2f}m')
    ax2.axvline(np.median(coords), color='white', lw=1.5, linestyle=':',
                label=f'Médiane : {np.median(coords):.2f}m')
    ax2.set_xlabel('Écart-type x défenseurs — σ (m)', color=TEXTE, fontsize=10)
    ax2.set_ylabel('Nombre de remontées', color=TEXTE, fontsize=10)
    ax2.set_title('Distribution de la coordination', color=TEXTE, fontsize=10, fontweight='bold')
    ax2.tick_params(colors=TEXTE)
    ax2.spines[:].set_color('#444')
    ax2.legend(fontsize=8, facecolor='#1a1a2e', labelcolor=TEXTE, framealpha=0.8)

    plt.tight_layout()
    fname2 = r"C:\Users\chouk\Documents\tactical_pipeline\remontees_analyse.png"
    plt.savefig(fname2, dpi=140, bbox_inches='tight', facecolor=GRIS_BG)
    print(f"Sauvegardé → {fname2}")
    plt.show()


# ── Mode scanner ─────────────────────────────────────────────────────────────

def mode_scanner_frames(toutes_lignes, meta_joueurs, minute_debut, minute_fin, periode, nb_snapshots):
    """Snapshots régulièrement espacés avec analyse défensive."""
    f_debut = max(0, min(minute_vers_frame(minute_debut, periode), len(toutes_lignes) - 1))
    f_fin   = max(0, min(minute_vers_frame(minute_fin,   periode), len(toutes_lignes) - 1))
    indices = np.linspace(f_debut, f_fin, nb_snapshots, dtype=int)

    ncols = 4
    nrows = int(np.ceil(nb_snapshots / ncols))
    fig   = plt.figure(figsize=(ncols * 5, nrows * 3.5))
    fig.patch.set_facecolor(GRIS_BG)
    fig.suptitle(
        f"{NOM_EQUIPE} vs {NOM_ADV}  —  {minute_debut}'→{minute_fin}'  P{periode}",
        color=TEXTE, fontsize=13, fontweight='bold'
    )

    remontee_vide = {'frame_debut': f_debut, 'frame_fin': f_fin,
                     'ts_debut': 0, 'periode': periode,
                     'minute': f"{minute_debut}'", 'montee_m': 0,
                     'duree_sec': 0, 'std_moy': 0}

    for i, frame_num in enumerate(indices):
        ax = fig.add_subplot(nrows, ncols, i + 1)
        ax.set_facecolor(GRIS_BG)
        draw_frame_annote(ax, int(frame_num), toutes_lignes, meta_joueurs, remontee_vide)
        print(f"  ✓ frame {frame_num}")

    patches = [
        mpatches.Patch(color=COULEUR_DEF, label=f'{NOM_EQUIPE} (○ DEF=contour or)'),
        mpatches.Patch(color=COULEUR_ADV, label=NOM_ADV),
        mpatches.Patch(color='#FFD700',   label='Ligne déf. ± σ', alpha=0.6),
        mpatches.Patch(color='#00ff88',   label='Gardien (carré ■)', alpha=0.8),
    ]
    fig.legend(handles=patches, loc='lower center', ncol=4, fontsize=8,
               facecolor='#16213e', labelcolor=TEXTE, framealpha=0.85)
    plt.tight_layout(rect=[0, 0.04, 1, 0.95])
    plt.show()


# ── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    meta_joueurs = charger_joueurs(FICHIER_JOUEURS)

    print("Chargement tracking...", end='', flush=True)
    with open(FICHIER_TRACKING, 'r', encoding='utf-8') as f:
        toutes_lignes = f.readlines()
    print(f" {len(toutes_lignes)} frames")

    remontees = detecter_remontees(toutes_lignes, meta_joueurs)
    afficher_resultats(remontees, top_n=10)

    if not remontees:
        print("Aucune remontée détectée. Essaie de baisser SEUIL_MONTEE ou DUREE_MIN.")
    elif MODE == 'sequence':
        if MINUTE_DEBUT > 0:
            f_debut = minute_vers_frame(MINUTE_DEBUT, PERIODE)
            f_fin   = minute_vers_frame(MINUTE_FIN,   PERIODE)
            f_debut = max(0, min(f_debut, len(toutes_lignes) - 1))
            f_fin   = max(0, min(f_fin,   len(toutes_lignes) - 1))
            r0 = parser_frame(toutes_lignes[f_debut])
            remontee_custom = {
                'frame_debut': f_debut,
                'frame_fin':   f_fin,
                'ts_debut':    r0[0] if r0 else TS_DEBUT,
                'periode':     PERIODE,
                'minute':      f"{MINUTE_DEBUT}'",
                'montee_m':    0,
                'duree_sec':   round((f_fin - f_debut) / FPS, 1),
                'std_moy':     0,
            }
            print(f"Séquence manuelle : {MINUTE_DEBUT}'→{MINUTE_FIN}' P{PERIODE} "
                  f"(frames {f_debut}–{f_fin})")
            mode_sequence(remontee_custom, toutes_lignes, meta_joueurs, VITESSE)
        else:
            idx = min(INDEX_REMONTEE, len(remontees) - 1)
            mode_sequence(remontees[idx], toutes_lignes, meta_joueurs, VITESSE)
    elif MODE == 'rapport':
        mode_rapport(remontees, toutes_lignes, meta_joueurs, TOP_N)
    elif MODE == 'scanner':
        mode_scanner_frames(toutes_lignes, meta_joueurs,
                            MINUTE_DEBUT, MINUTE_FIN, PERIODE, NB_SNAPSHOTS)
