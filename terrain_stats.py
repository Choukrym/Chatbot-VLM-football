"""
Terrain (trajectoires séquence) + heatmap + stats côte à côte
"""

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import numpy as np

FICHIER_TRACKING = r"C:\Users\chouk\Documents\tactical_pipeline\L1 J14 RCL MHSC 2-3 FRAN_RAW_GAME_OPT_TGV_25FPS$2248298.txt"
FICHIER_JOUEURS  = r"C:\Users\chouk\Documents\tactical_pipeline\L1 J14 RCL MHSC 2-3 FRAN_RAW_PLAYERS_OPT_TGV$2248298.csv"

TS_DEBUT = 1607803200000
FPS      = 25
DT       = 1.0 / FPS

GRIS_BG    = '#1a1a2e'
GRIS_PANEL = '#16213e'
TEXTE      = '#eaeaea'

# ════════════════════════════════════════════════════════
# Config — CHANGE CES VALEURS
# ════════════════════════════════════════════════════════
MINUTE_DEBUT   = 63     # début de la séquence affichée à gauche
MINUTE_FIN     = 78       # fin de la séquence
PERIODE        = 1
JOUEUR_MAILLOT = 11       # numéro de maillot pour la heatmap
EQUIPE_JOUEUR  = 0        # 0=Lens, 1=Montpellier
# ════════════════════════════════════════════════════════


def charger_joueurs(f):
    joueurs = {}
    with open(f, 'r', encoding='utf-8') as fh:
        for ligne in fh:
            ligne = ligne.strip().rstrip(';')
            if not ligne: continue
            c = ligne.split(',')
            if len(c) < 10: continue
            joueurs[int(c[9])] = {
                'nom': f"{c[2].strip()} {c[3].strip()}",
                'maillot': int(c[0]), 'poste': int(c[4]), 'team': int(c[1])
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
        try: joueurs.append({'team':int(d[0]),'pid':int(d[1]),'maillot':int(d[2]),'x':float(d[3]),'y':float(d[4])})
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


def dessiner_terrain(ax, facecolor='#2d6a4f'):
    ax.set_facecolor(facecolor)
    ax.set_xlim(0, 105); ax.set_ylim(0, 68)
    ax.plot([0,105,105,0,0],[0,0,68,68,0],'w',lw=1.5)
    ax.axvline(52.5, color='w', lw=1.2)
    ax.add_patch(plt.Circle((52.5,34), 9.15, fill=False, color='w', lw=1.2))
    ax.plot([0,16.5,16.5,0],[13.84,13.84,54.16,54.16],'w',lw=1.2)
    ax.plot([105,88.5,88.5,105],[13.84,13.84,54.16,54.16],'w',lw=1.2)
    ax.set_xticks([]); ax.set_yticks([])


def collecter_sequence(f_debut, f_fin, toutes_lignes, pas=10):
    """Collecte les trajectoires de tous les joueurs sur une séquence."""
    trajectoires = {}  # pid -> {'xs', 'ys', 'team', 'maillot'}
    ballon_seq   = []
    for i in range(f_debut, min(f_fin + 1, len(toutes_lignes)), pas):
        r = parser_frame(toutes_lignes[i])
        if r is None: continue
        _, _, joueurs, ballon = r
        for j in joueurs:
            pid = j['pid']
            if pid not in trajectoires:
                trajectoires[pid] = {'xs': [], 'ys': [], 'team': j['team'], 'maillot': j['maillot']}
            trajectoires[pid]['xs'].append(j['x'])
            trajectoires[pid]['ys'].append(j['y'])
        if ballon:
            ballon_seq.append(ballon)
    return trajectoires, ballon_seq


def collecter_joueur(pid, toutes_lignes, pas=5):
    """Collecte x, y, vitesse (m/s) de toutes les frames pour un joueur."""
    xs, ys, vs = [], [], []
    prev = None
    for i, ligne in enumerate(toutes_lignes):
        if i % pas != 0: continue
        r = parser_frame(ligne)
        if r is None: continue
        _, _, joueurs, _ = r
        for j in joueurs:
            if j['pid'] == pid:
                x, y = j['x'], j['y']
                v = np.hypot(x - prev[0], y - prev[1]) / (DT * pas) if prev else 0.0
                v = min(v, 10.0)
                xs.append(x); ys.append(y); vs.append(v)
                prev = (x, y)
                break
    return np.array(xs), np.array(ys), np.array(vs)


def main():
    meta = charger_joueurs(FICHIER_JOUEURS)

    # Trouver le pid du joueur cible
    pid_cible = None
    for pid, info in meta.items():
        if info['maillot'] == JOUEUR_MAILLOT and info['team'] == EQUIPE_JOUEUR:
            pid_cible = pid
            break
    if pid_cible is None:
        print(f"Joueur #{JOUEUR_MAILLOT} équipe {EQUIPE_JOUEUR} introuvable.")
        return
    nom_joueur = meta[pid_cible]['nom']

    print(f"Chargement tracking...", end='', flush=True)
    with open(FICHIER_TRACKING, 'r', encoding='utf-8') as f:
        toutes_lignes = f.readlines()
    print(f" {len(toutes_lignes)} frames")

    # ── Séquence terrain ──────────────────────────────────────────────────
    f_debut = max(0, min(minute_vers_frame(MINUTE_DEBUT, PERIODE), len(toutes_lignes) - 1))
    f_fin   = max(0, min(minute_vers_frame(MINUTE_FIN,   PERIODE), len(toutes_lignes) - 1))

    print(f"Collecte trajectoires {MINUTE_DEBUT}'→{MINUTE_FIN}'...", end='', flush=True)
    trajectoires, ballon_seq = collecter_sequence(f_debut, f_fin, toutes_lignes, pas=10)
    print(" OK")

    # ── Heatmap + stats match entier ──────────────────────────────────────
    print(f"Calcul heatmap #{JOUEUR_MAILLOT} {nom_joueur}...", end='', flush=True)
    xs, ys, vs = collecter_joueur(pid_cible, toutes_lignes, pas=5)
    print(" OK")

    # Seuils en m/s → conversion km/h pour l'affichage
    SPRINT_MS  = 7.0
    COURSE_MS  = 4.0

    dist_km     = float(np.sum(vs) * DT * 5 / 1000)
    v_max_ms    = float(np.max(vs)) if len(vs) else 0.0
    v_moy_ms    = float(np.mean(vs)) if len(vs) else 0.0
    nb_sprints  = int(np.sum(np.diff((vs > SPRINT_MS).astype(int)) == 1))
    dist_course = float(np.sum(vs[vs > COURSE_MS]) * DT * 5)

    # km/h
    v_max_kmh = v_max_ms * 3.6
    v_moy_kmh = v_moy_ms * 3.6

    # ════════════════════════════════════════════════════════════════════════
    # FIGURE
    # ════════════════════════════════════════════════════════════════════════
    fig = plt.figure(figsize=(16, 7), facecolor=GRIS_BG)
    fig.suptitle(
        f"RC Lens vs Montpellier HSC — #{JOUEUR_MAILLOT} {nom_joueur}",
        fontsize=13, color=TEXTE, fontweight='bold', y=0.98
    )

    gs = gridspec.GridSpec(2, 3, figure=fig,
                           width_ratios=[2, 2, 1],
                           height_ratios=[3, 1],
                           hspace=0.35, wspace=0.3,
                           left=0.04, right=0.97, top=0.92, bottom=0.06)

    # ── [0,0] Trajectoires séquence ───────────────────────────────────────
    ax_terrain = fig.add_subplot(gs[0, 0])
    dessiner_terrain(ax_terrain)

    for pid, traj in trajectoires.items():
        team   = traj['team']
        maillot = traj['maillot']
        xs_t   = traj['xs']
        ys_t   = traj['ys']
        if len(xs_t) < 2: continue

        est_cible = (pid == pid_cible)

        if team == 0:      # Lens
            color = '#FFD700' if est_cible else '#E63946'
            lw    = 2.5 if est_cible else 1.0
            alpha = 0.95 if est_cible else 0.55
            zorder = 6 if est_cible else 3
        elif team == 1:    # Montpellier
            color, lw, alpha, zorder = '#457B9D', 1.0, 0.55, 3
        else:              # arbitre / GK-side
            color, lw, alpha, zorder = '#888888', 0.7, 0.35, 2

        ax_terrain.plot(xs_t, ys_t, color=color, lw=lw, alpha=alpha, zorder=zorder)
        # Dot de début (○) et fin (●)
        ax_terrain.scatter(xs_t[0],  ys_t[0],  c=color, s=20, alpha=alpha, zorder=zorder, marker='o')
        ax_terrain.scatter(xs_t[-1], ys_t[-1], c=color, s=50, alpha=min(alpha+0.1, 1.0), zorder=zorder+1,
                           edgecolors='white' if est_cible else 'none', linewidths=0.8)
        # Numéro au dernier point
        if team in (0, 1):
            ax_terrain.annotate(str(maillot), (xs_t[-1], ys_t[-1]),
                                textcoords='offset points', xytext=(0, 5),
                                ha='center', fontsize=5, color='white', fontweight='bold', zorder=zorder+2)

    # Ballon (quelques points clés)
    if ballon_seq:
        bx = [b[0] for b in ballon_seq[::max(1, len(ballon_seq)//15)]]
        by = [b[1] for b in ballon_seq[::max(1, len(ballon_seq)//15)]]
        ax_terrain.scatter(bx, by, c='white', s=18, edgecolors='black', zorder=7, linewidths=0.5, alpha=0.7)

    patches = [
        mpatches.Patch(color='#E63946', label='Lens'),
        mpatches.Patch(color='#FFD700', label=f'#{JOUEUR_MAILLOT} {nom_joueur.split()[-1]}'),
        mpatches.Patch(color='#457B9D', label='Montpellier'),
    ]
    ax_terrain.legend(handles=patches, loc='lower left', fontsize=6,
                      facecolor=GRIS_PANEL, labelcolor=TEXTE, framealpha=0.8)
    ax_terrain.set_title(f"Trajectoires {MINUTE_DEBUT}'→{MINUTE_FIN}'",
                         color=TEXTE, fontsize=9, fontweight='bold')

    # ── [0,1] Heatmap du joueur ───────────────────────────────────────────
    ax_heat = fig.add_subplot(gs[0, 1])
    dessiner_terrain(ax_heat, facecolor='#0d1b0d')

    if len(xs) > 10:
        h, _, _ = np.histogram2d(xs, ys, bins=[42, 27], range=[[0,105],[0,68]])
        ax_heat.imshow(h.T, extent=[0,105,0,68], origin='lower',
                       cmap='YlOrRd', alpha=0.8, aspect='auto',
                       vmin=0, vmax=np.percentile(h[h>0], 95))

    ax_heat.set_title(f"Heatmap — {nom_joueur.split()[-1]} (match entier)",
                      color=TEXTE, fontsize=9, fontweight='bold')

    # ── [0,2] Stats texte ─────────────────────────────────────────────────
    ax_stats = fig.add_subplot(gs[0, 2])
    ax_stats.set_facecolor(GRIS_PANEL)
    ax_stats.set_xticks([]); ax_stats.set_yticks([])
    for spine in ax_stats.spines.values(): spine.set_color('#444')
    ax_stats.set_title('Stats match', color=TEXTE, fontsize=9, fontweight='bold')

    poste_label = {1:'Attaquant', 2:'Milieu', 3:'Défenseur', 4:'Gardien'}
    poste = meta[pid_cible].get('poste', 0)

    lignes = [
        ('Poste',         poste_label.get(poste, '—')),
        ('',              ''),
        ('Distance tot.', f"{dist_km:.1f} km"),
        ('Dist. course',  f"{dist_course:.0f} m"),
        ('Sprints',       f"{nb_sprints}"),
        ('Vmax',          f"{v_max_kmh:.1f} km/h"),
        ('V. moyenne',    f"{v_moy_kmh:.1f} km/h"),
    ]
    for i, (label, val) in enumerate(lignes):
        y = 0.90 - i * 0.12
        ax_stats.text(0.05, y, label, transform=ax_stats.transAxes,
                      fontsize=8, color='#aaaaaa')
        color_val = '#FFD700' if label in ('Vmax', 'Sprints') else TEXTE
        ax_stats.text(0.95, y, val, transform=ax_stats.transAxes,
                      fontsize=9, color=color_val, ha='right', fontweight='bold')

    # ── [1, :2] Profil de vitesse (km/h) ──────────────────────────────────
    ax_v = fig.add_subplot(gs[1, :2])
    ax_v.set_facecolor(GRIS_PANEL)
    for spine in ax_v.spines.values(): spine.set_color('#444')

    minutes_v  = np.linspace(0, 90, len(vs))
    vs_kmh     = vs * 3.6
    if len(vs_kmh) > 100:
        kernel    = np.ones(100) / 100
        vs_smooth = np.convolve(vs_kmh, kernel, mode='same')
    else:
        vs_smooth = vs_kmh

    # Zone séquence en surbrillance
    ax_v.axvspan(MINUTE_DEBUT, MINUTE_FIN, color='cyan', alpha=0.08, zorder=0)
    ax_v.fill_between(minutes_v, vs_smooth, alpha=0.3, color='#FFD700')
    ax_v.plot(minutes_v, vs_smooth, color='#FFD700', lw=1.2)

    seuil_course_kmh = COURSE_MS * 3.6   # 14.4 km/h
    seuil_sprint_kmh = SPRINT_MS  * 3.6  # 25.2 km/h
    ax_v.axhline(seuil_course_kmh, color='white', lw=0.8, linestyle='--', alpha=0.4)
    ax_v.axhline(seuil_sprint_kmh, color='#E63946', lw=0.8, linestyle='--', alpha=0.5)
    ax_v.text(1, seuil_course_kmh + 0.5, 'Course', color='white', fontsize=7, alpha=0.5)
    ax_v.text(1, seuil_sprint_kmh + 0.5, 'Sprint',  color='#E63946', fontsize=7, alpha=0.7)

    # Repères début / fin séquence
    ax_v.axvline(MINUTE_DEBUT, color='cyan', lw=1.0, linestyle=':')
    ax_v.axvline(MINUTE_FIN,   color='cyan', lw=1.0, linestyle=':')
    y_label = vs_smooth.max() * 0.85 if vs_smooth.max() > 0 else seuil_sprint_kmh
    ax_v.text((MINUTE_DEBUT + MINUTE_FIN) / 2, y_label,
              f"{MINUTE_DEBUT}'–{MINUTE_FIN}'", color='cyan', fontsize=7, ha='center')

    ax_v.set_xlabel('Minute', color=TEXTE, fontsize=8)
    ax_v.set_ylabel('Vitesse (km/h)', color=TEXTE, fontsize=8)
    ax_v.set_title(f"Profil de vitesse — {nom_joueur.split()[-1]}", color=TEXTE, fontsize=9, fontweight='bold')
    ax_v.tick_params(colors=TEXTE)
    ax_v.set_xlim(0, 90)
    ax_v.set_ylim(0)

    # ── [1, 2] Bar intensités ─────────────────────────────────────────────
    ax_int = fig.add_subplot(gs[1, 2])
    ax_int.set_facecolor(GRIS_PANEL)
    for spine in ax_int.spines.values(): spine.set_color('#444')

    zones  = ['Marche\n(<7)', 'Trot\n(7–14)', 'Course\n(14–25)', 'Sprint\n(>25)']
    # seuils en m/s pour le calcul (vs est en m/s)
    seuils = [(0, 2), (2, 4), (4, 7), (7, 99)]
    colors = ['#457B9D', '#2a9d8f', '#e9c46a', '#E63946']
    dists  = [float(np.sum(vs[(vs >= lo) & (vs < hi)]) * DT * 5) for lo, hi in seuils]

    bars = ax_int.bar(zones, dists, color=colors, edgecolor='none', width=0.6)
    for bar, d in zip(bars, dists):
        ax_int.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                    f'{d:.0f}m', ha='center', fontsize=7, color=TEXTE)

    ax_int.set_title('Répartition intensités', color=TEXTE, fontsize=9, fontweight='bold')
    ax_int.tick_params(colors=TEXTE, labelsize=7)
    ax_int.set_ylabel('Distance (m)', color=TEXTE, fontsize=7)

    equipe_str = "Lens" if EQUIPE_JOUEUR == 0 else "Montpellier"
    plt.savefig(
        fr"C:\Users\chouk\Documents\tactical_pipeline\terrain_stats_{equipe_str}_{JOUEUR_MAILLOT}.png",
        dpi=140, bbox_inches='tight', facecolor=GRIS_BG
    )
    print(f"Sauvegardé → terrain_stats_{equipe_str}_{JOUEUR_MAILLOT}.png")
    plt.show()


if __name__ == '__main__':
    main()
