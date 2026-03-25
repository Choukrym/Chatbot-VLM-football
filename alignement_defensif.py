import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.animation as animation
import numpy as np

# ─── Fichiers ───────────────────────────────────────────────────────────────
FICHIER_TRACKING = r"C:\Users\chouk\Documents\tactical_pipeline\L1 J14 RCL MHSC 2-3 FRAN_RAW_GAME_OPT_TGV_25FPS$2248298.txt"
FICHIER_JOUEURS  = r"C:\Users\chouk\Documents\tactical_pipeline\L1 J14 RCL MHSC 2-3 FRAN_RAW_PLAYERS_OPT_TGV$2248298.csv"

# ─── Seuil de désalignement (en mètres) ─────────────────────────────────────
# Si un défenseur est à plus de SEUIL mètres de la ligne moyenne → alerte
SEUIL_METRES = 3.0

# ─── Equipe à analyser (0 = Lens, 1 = Montpellier) ──────────────────────────
EQUIPE_DEFENSIVE = 0

# ─── Flèches de déplacement : combien de frames en avant (10 = 0.4 s) ────────
DELTA_FLECHES = 10


# ════════════════════════════════════════════════════════════════════════════
# 1. Chargement des métadonnées joueurs
# ════════════════════════════════════════════════════════════════════════════
def charger_joueurs(fichier_csv):
    """Retourne un dict {player_id_tgv: {nom, maillot, poste, team}}"""
    joueurs = {}
    with open(fichier_csv, 'r', encoding='utf-8') as f:
        for ligne in f:
            ligne = ligne.strip().rstrip(';')
            if not ligne:
                continue
            cols = ligne.split(',')
            if len(cols) < 10:
                continue
            maillot   = int(cols[0])
            team      = int(cols[1])
            prenom    = cols[2].strip()
            nom       = cols[3].strip()
            poste     = int(cols[4])   # 1=ATT 2=MIL 3=DEF 4=GK
            pid_tgv   = int(cols[9])
            joueurs[pid_tgv] = {
                'nom':     f"{prenom} {nom}",
                'maillot': maillot,
                'poste':   poste,
                'team':    team,
            }
    return joueurs


# ════════════════════════════════════════════════════════════════════════════
# 2. Parse d'une ligne de tracking
# ════════════════════════════════════════════════════════════════════════════
def parser_frame(ligne):
    """
    Retourne (timestamp_ms, periode, joueurs_list, ballon)
    joueurs_list = liste de dict {team, pid, maillot, x, y}
    ballon = (x, y, z) ou None
    """
    ligne = ligne.strip()
    # Séparer l'en-tête du contenu : "N→header;elapsed,periode,live:joueurs:ballon"
    if '→' in ligne:
        _, reste = ligne.split('→', 1)
    else:
        reste = ligne

    parties = reste.split(':')
    if len(parties) < 3:
        return None

    entete   = parties[0]   # "timestamp;elapsed,periode,live"
    joueurs_str = parties[1]
    ballon_str  = parties[2]

    # En-tête
    meta = entete.split(';')
    timestamp_ms = int(meta[0])
    periode      = int(meta[1].split(',')[1])

    # Joueurs
    joueurs = []
    for j in joueurs_str.split(';'):
        d = j.split(',')
        if len(d) < 5:
            continue
        joueurs.append({
            'team':    int(d[0]),
            'pid':     int(d[1]),
            'maillot': int(d[2]),
            'x':       float(d[3]),
            'y':       float(d[4]),
        })

    # Ballon
    ballon = None
    bd = ballon_str.rstrip(';').split(',')
    if len(bd) >= 2:
        try:
            ballon = (float(bd[0]), float(bd[1]), float(bd[2]) if len(bd) > 2 else 0.0)
        except ValueError:
            pass

    return timestamp_ms, periode, joueurs, ballon


# ════════════════════════════════════════════════════════════════════════════
# 3. Analyse d'alignement défensif sur une frame
# ════════════════════════════════════════════════════════════════════════════
def analyser_alignement(joueurs_frame, meta_joueurs, equipe, seuil):
    """
    Retourne:
      - defenseurs : liste des joueurs défenseurs de l'équipe
      - ligne_moyenne : coordonnée x moyenne de la ligne
      - desalignes : defenseurs dont |x - ligne_moyenne| > seuil
      - ecart_max : écart maximal observé
    """
    defenseurs = [
        j for j in joueurs_frame
        if j['team'] == equipe
        and meta_joueurs.get(j['pid'], {}).get('poste') == 3  # poste=3 → DEF
    ]

    if len(defenseurs) < 2:
        return defenseurs, None, [], 0.0

    xs = np.array([d['x'] for d in defenseurs])
    ligne_moyenne = float(np.mean(xs))
    ecarts = np.abs(xs - ligne_moyenne)
    ecart_max = float(np.max(ecarts))

    desalignes = [d for d, e in zip(defenseurs, ecarts) if e > seuil]
    return defenseurs, ligne_moyenne, desalignes, ecart_max


# ════════════════════════════════════════════════════════════════════════════
# 4. Visualisation d'une frame avec analyse
# ════════════════════════════════════════════════════════════════════════════
def dessiner_terrain(ax):
    ax.set_facecolor('#4a7c4e')
    ax.set_xlim(0, 105)
    ax.set_ylim(0, 68)
    # Contour
    ax.plot([0,105,105,0,0], [0,0,68,68,0], 'w', lw=2)
    # Ligne médiane
    ax.axvline(52.5, color='w', lw=1.5)
    ax.add_patch(plt.Circle((52.5, 34), 9.15, fill=False, color='w', lw=1.5))
    # Surface de réparation gauche
    ax.plot([0,16.5,16.5,0], [13.84,13.84,54.16,54.16], 'w', lw=1.5)
    # Surface de réparation droite
    ax.plot([105,88.5,88.5,105], [13.84,13.84,54.16,54.16], 'w', lw=1.5)


def visualiser_frame(frame_num=500):
    meta_joueurs = charger_joueurs(FICHIER_JOUEURS)

    with open(FICHIER_TRACKING, 'r', encoding='utf-8') as f:
        lignes = f.readlines()

    if frame_num >= len(lignes):
        print(f"Frame {frame_num} inexistante (max {len(lignes)-1})")
        return

    pos_future = positions_frame(lignes, frame_num + DELTA_FLECHES)
    resultat   = parser_frame(lignes[frame_num])
    if resultat is None:
        print("Frame non parseable")
        return

    timestamp_ms, periode, joueurs, ballon = resultat

    defenseurs, ligne_moy, desalignes, ecart_max = analyser_alignement(
        joueurs, meta_joueurs, EQUIPE_DEFENSIVE, SEUIL_METRES
    )
    ids_desalignes = {d['pid'] for d in desalignes}

    fig, ax = plt.subplots(figsize=(12, 7.5))
    dessiner_terrain(ax)

    for j in joueurs:
        info = meta_joueurs.get(j['pid'], {})
        team = j['team']
        pid  = j['pid']

        if team == EQUIPE_DEFENSIVE:  # Lens
            if pid in ids_desalignes:
                color, edge = 'red', 'white'      # désaligné → rouge
            else:
                color, edge = 'yellow', '#cc0000'
        elif team == 1 - EQUIPE_DEFENSIVE:  # adversaire
            color, edge = '#3399ff', 'white'
        else:
            color, edge = 'black', 'white'        # arbitre/GK

        ax.scatter(j['x'], j['y'], c=color, s=180, edgecolors=edge, zorder=5, linewidths=1.5)
        label = info.get('maillot', '')
        ax.annotate(str(label), (j['x'], j['y']), textcoords='offset points',
                    xytext=(0, 7), ha='center', fontsize=7, color='white', fontweight='bold')

    # Flèches de déplacement
    dessiner_fleches(ax, joueurs, pos_future, EQUIPE_DEFENSIVE)

    # Ligne défensive moyenne
    if ligne_moy is not None:
        ax.axvline(ligne_moy, color='orange', lw=2, linestyle='--', alpha=0.8, label=f'Ligne déf. moy. ({ligne_moy:.1f}m)')
        # Zone ± seuil
        ax.axvspan(ligne_moy - SEUIL_METRES, ligne_moy + SEUIL_METRES,
                   alpha=0.12, color='orange', label=f'Zone ±{SEUIL_METRES}m')

    # Ballon
    if ballon:
        ax.scatter(ballon[0], ballon[1], c='white', s=80, edgecolors='black',
                   zorder=6, marker='o', label='Ballon')

    # Légende et infos
    patches = [
        mpatches.Patch(color='yellow', label='Lens (aligné)'),
        mpatches.Patch(color='red',    label=f'Lens (désaligné > {SEUIL_METRES}m)'),
        mpatches.Patch(color='#3399ff',label='Montpellier'),
    ]
    ax.legend(handles=patches, loc='lower left', fontsize=8, framealpha=0.7)

    titre = f"Frame {frame_num} | Période {periode} | Écart max: {ecart_max:.1f}m"
    if desalignes:
        noms = ', '.join(meta_joueurs.get(d['pid'], {}).get('nom', '?') for d in desalignes)
        titre += f"\n⚠ Désaligné(s): {noms}"
    ax.set_title(titre, fontsize=10, pad=10)
    ax.set_xlabel('Longueur (m)')
    ax.set_ylabel('Largeur (m)')

    plt.tight_layout()
    plt.show()


# ════════════════════════════════════════════════════════════════════════════
# 5. Scanner tout le match → moments critiques
# ════════════════════════════════════════════════════════════════════════════
def scanner_match(top_n=10, pas=25):
    """
    Parcourt le fichier toutes les `pas` frames.
    Affiche les TOP N frames avec le plus grand désalignement.
    """
    meta_joueurs = charger_joueurs(FICHIER_JOUEURS)
    resultats = []

    with open(FICHIER_TRACKING, 'r', encoding='utf-8') as f:
        for i, ligne in enumerate(f):
            if i % pas != 0:
                continue
            r = parser_frame(ligne)
            if r is None:
                continue
            timestamp_ms, periode, joueurs, ballon = r
            _, ligne_moy, desalignes, ecart_max = analyser_alignement(
                joueurs, meta_joueurs, EQUIPE_DEFENSIVE, SEUIL_METRES
            )
            if ecart_max > 0:
                resultats.append((ecart_max, i, periode, desalignes, timestamp_ms))

    resultats.sort(reverse=True)
    print(f"\n{'='*60}")
    print(f" TOP {top_n} moments de désalignement défensif (Lens)")
    print(f"{'='*60}")
    for ecart, frame, periode, desalignes, ts in resultats[:top_n]:
        noms = ', '.join(meta_joueurs.get(d['pid'], {}).get('nom', '?') for d in desalignes)
        mins = int((ts - 1607803200000) / 60000)
        print(f"  Frame {frame:5d} | P{periode} ~{mins}'  | Écart: {ecart:.1f}m | ⚠ {noms if noms else 'aucun'}")

    return resultats


# ════════════════════════════════════════════════════════════════════════════
# 6. Convertir minutes → numéro de frame
# ════════════════════════════════════════════════════════════════════════════
def positions_frame(toutes_lignes, frame_num):
    """Retourne {pid: (x, y)} pour une frame, ou {} si invalide."""
    if frame_num < 0 or frame_num >= len(toutes_lignes):
        return {}
    r = parser_frame(toutes_lignes[frame_num])
    if r is None:
        return {}
    _, _, joueurs, _ = r
    return {j['pid']: (j['x'], j['y']) for j in joueurs}


def dessiner_fleches(ax, joueurs, pos_future, equipe_def):
    """Dessine les flèches de déplacement prévu pour chaque joueur."""
    for team_id, arrow_color in [(equipe_def, '#FFD700'), (1 - equipe_def, '#aaddff')]:
        xs_q, ys_q, dxs_q, dys_q = [], [], [], []
        for j in joueurs:
            if j['team'] != team_id or j['pid'] not in pos_future:
                continue
            dx = pos_future[j['pid']][0] - j['x']
            dy = pos_future[j['pid']][1] - j['y']
            if np.hypot(dx, dy) > 0.1:   # ignorer les joueurs quasi-immobiles
                xs_q.append(j['x']); ys_q.append(j['y'])
                dxs_q.append(dx);    dys_q.append(dy)
        if xs_q:
            ax.quiver(xs_q, ys_q, dxs_q, dys_q,
                      color=arrow_color, scale=1, scale_units='xy', angles='xy',
                      width=0.003, headwidth=8, headlength=8,
                      alpha=0.85, zorder=9)


def minute_vers_frame(minute, periode=1):
    """
    Convertit une minute de jeu en numéro de frame.
    Période 1 commence à 0', période 2 à ~45'.
    25 fps → 1 frame = 40ms → 1500 frames par minute.
    """
    if periode == 2:
        # La P2 commence après la P1 dans le fichier, offset ~45 min
        offset_frames = 45 * 60 * 25
        return offset_frames + int(minute * 60 * 25)
    return int(minute * 60 * 25)


# ════════════════════════════════════════════════════════════════════════════
# 7. Animation d'une séquence
# ════════════════════════════════════════════════════════════════════════════
def animer_sequence(frame_debut, frame_fin, vitesse=1, sauvegarder=None):
    """
    Anime les frames entre frame_debut et frame_fin.
    vitesse : 1=temps réel, 2=x2, 0.5=ralenti
    sauvegarder : chemin .mp4 ou .gif, ou None pour afficher
    """
    meta_joueurs = charger_joueurs(FICHIER_JOUEURS)

    with open(FICHIER_TRACKING, 'r', encoding='utf-8') as f:
        toutes_lignes = f.readlines()

    frame_debut = max(0, frame_debut)
    frame_fin   = min(frame_fin, len(toutes_lignes) - 1)

    # On garde 1 frame sur 2 pour ne pas surcharger (ajustable)
    pas_anim = max(1, int(1 / vitesse))
    indices  = list(range(frame_debut, frame_fin, pas_anim))

    fig, ax = plt.subplots(figsize=(12, 7.5))
    plt.tight_layout()

    def _draw(frame_num):
        ax.clear()
        dessiner_terrain(ax)

        ligne = toutes_lignes[frame_num]
        r = parser_frame(ligne)
        if r is None:
            return

        timestamp_ms, periode, joueurs, ballon = r
        _, ligne_moy, desalignes, ecart_max = analyser_alignement(
            joueurs, meta_joueurs, EQUIPE_DEFENSIVE, SEUIL_METRES
        )
        ids_desalignes = {d['pid'] for d in desalignes}

        for j in joueurs:
            info = meta_joueurs.get(j['pid'], {})
            team = j['team']
            pid  = j['pid']
            if team == EQUIPE_DEFENSIVE:
                color, edge = ('red', 'white') if pid in ids_desalignes else ('yellow', '#cc0000')
            elif team == 1 - EQUIPE_DEFENSIVE:
                color, edge = '#3399ff', 'white'
            else:
                color, edge = 'black', 'white'
            ax.scatter(j['x'], j['y'], c=color, s=180, edgecolors=edge, zorder=5, linewidths=1.5)
            ax.annotate(str(info.get('maillot', '')), (j['x'], j['y']),
                        textcoords='offset points', xytext=(0, 7),
                        ha='center', fontsize=7, color='white', fontweight='bold')

        # Flèches de déplacement
        pos_future = positions_frame(toutes_lignes, frame_num + DELTA_FLECHES)
        dessiner_fleches(ax, joueurs, pos_future, EQUIPE_DEFENSIVE)

        if ligne_moy is not None:
            ax.axvline(ligne_moy, color='orange', lw=2, linestyle='--', alpha=0.8)
            ax.axvspan(ligne_moy - SEUIL_METRES, ligne_moy + SEUIL_METRES,
                       alpha=0.12, color='orange')

        if ballon:
            ax.scatter(ballon[0], ballon[1], c='white', s=80, edgecolors='black', zorder=6)

        mins  = int((timestamp_ms - 1607803200000) / 60000)
        secs  = int(((timestamp_ms - 1607803200000) % 60000) / 1000)
        alerte = f" | ⚠ Désaligné !" if desalignes else ""
        ax.set_title(f"P{periode}  {mins}'{secs:02d}\"  — Frame {frame_num}  |  Écart: {ecart_max:.1f}m{alerte}",
                     fontsize=10)
        ax.set_xlim(0, 105)
        ax.set_ylim(0, 68)

    intervalle_ms = int(40 / vitesse)   # 40ms = 25fps, divisé par la vitesse
    ani = animation.FuncAnimation(fig, _draw, frames=indices,
                                   interval=intervalle_ms, repeat=False)

    if sauvegarder:
        print(f"Sauvegarde en cours → {sauvegarder}")
        ani.save(sauvegarder, fps=int(25 * vitesse), dpi=100)
        print("Sauvegardé !")
    else:
        plt.show()

    return ani


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':

    # ════════════════════════════════════════════
    # CHOIX DU MODE  ← change juste cette valeur
    #   'scanner'  → trouve les 10 pires moments du match
    #   'minute'   → affiche une frame à une minute précise
    #   'sequence' → anime un intervalle de minutes
    # ════════════════════════════════════════════
    MODE = 'sequence'

    # Paramètres pour MODE = 'minute'
    MINUTE  = 23
    PERIODE = 1

    # Paramètres pour MODE = 'sequence'
    MINUTE_DEBUT = 28
    MINUTE_FIN   = 22
    VITESSE      = 1   # 1=temps réel, 0.5=ralenti x2, 2=accéléré x2

    # ────────────────────────────────────────────
    if MODE == 'scanner':
        resultats = scanner_match(top_n=10, pas=25)
        if resultats:
            print(f"\nVisualisation du pire moment (frame {resultats[0][1]})...")
            visualiser_frame(resultats[0][1])

    elif MODE == 'minute':
        frame = minute_vers_frame(MINUTE, PERIODE)
        print(f"Affichage à {MINUTE}' P{PERIODE} → frame {frame}")
        visualiser_frame(frame)

    elif MODE == 'sequence':
        f_debut = minute_vers_frame(MINUTE_DEBUT, PERIODE)
        f_fin   = minute_vers_frame(MINUTE_FIN,   PERIODE)
        print(f"Animation de {MINUTE_DEBUT}' à {MINUTE_FIN}' → frames {f_debut}–{f_fin}")
        animer_sequence(f_debut, f_fin, vitesse=VITESSE)
