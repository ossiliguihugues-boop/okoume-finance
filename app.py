from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, GroupeTontine, MembreGroupe, Utilisateur, Cycle, Cotisation, JournalAudit
from datetime import date
import random
import string
import csv
import io
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tontine.db'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-moi-plus-tard')

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'connexion'

@login_manager.user_loader
def charger_utilisateur(user_id):
    return Utilisateur.query.get(int(user_id))


def enregistrer_action(action, details=''):
    entree = JournalAudit(
        utilisateur_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        details=details
    )
    db.session.add(entree)
    db.session.commit()


@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    if request.method == 'POST':
        nom = request.form['nom']
        telephone = request.form['telephone']
        mot_de_passe = request.form['mot_de_passe']

        if Utilisateur.query.filter_by(telephone=telephone).first():
            flash("Ce numero de telephone est deja utilise.")
            return redirect(url_for('inscription'))

        code = ''.join(random.choices(string.digits, k=6))

        utilisateur = Utilisateur(
            nom=nom,
            telephone=telephone,
            mot_de_passe_hash='',
            telephone_verifie=False,
            code_verification=code
        )
        utilisateur.definir_mot_de_passe(mot_de_passe)
        db.session.add(utilisateur)
        db.session.commit()

        enregistrer_action('inscription', f"{utilisateur.nom} a cree un compte, code envoye")
        flash(f"SIMULATION SMS : votre code de verification est {code}")
        return redirect(url_for('verifier_telephone', utilisateur_id=utilisateur.id))

    return render_template('inscription.html')


@app.route('/verifier-telephone/<int:utilisateur_id>', methods=['GET', 'POST'])
def verifier_telephone(utilisateur_id):
    utilisateur = Utilisateur.query.get_or_404(utilisateur_id)

    if request.method == 'POST':
        code_saisi = request.form['code']

        if code_saisi == utilisateur.code_verification:
            utilisateur.telephone_verifie = True
            utilisateur.code_verification = None
            db.session.commit()

            login_user(utilisateur)
            enregistrer_action('verification_telephone', f"{utilisateur.nom} a verifie son numero")
            flash("Numero verifie avec succes !")
            return redirect(url_for('accueil'))

        flash("Code incorrect, reessayez.")
        return redirect(url_for('verifier_telephone', utilisateur_id=utilisateur.id))

    return render_template('verifier_telephone.html', utilisateur=utilisateur)


@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if request.method == 'POST':
        telephone = request.form['telephone']
        mot_de_passe = request.form['mot_de_passe']

        utilisateur = Utilisateur.query.filter_by(telephone=telephone).first()

        if utilisateur and utilisateur.verifier_mot_de_passe(mot_de_passe):
            login_user(utilisateur)
            enregistrer_action('connexion', f"{utilisateur.nom} s'est connecte")
            return redirect(url_for('accueil'))

        flash("Telephone ou mot de passe incorrect.")
        return redirect(url_for('connexion'))

    return render_template('connexion.html')


@app.route('/deconnexion')
@login_required
def deconnexion():
    logout_user()
    return redirect(url_for('connexion'))


@app.route('/mon-compte', methods=['GET', 'POST'])
@login_required
def mon_compte():
    if request.method == 'POST':
        ancien = request.form['ancien_mot_de_passe']
        nouveau = request.form['nouveau_mot_de_passe']

        if not current_user.verifier_mot_de_passe(ancien):
            flash("Ancien mot de passe incorrect.")
            return redirect(url_for('mon_compte'))

        current_user.definir_mot_de_passe(nouveau)
        db.session.commit()
        flash("Mot de passe mis a jour avec succes.")
        return redirect(url_for('mon_compte'))

    return render_template('mon_compte.html')


@app.route('/profil/<int:utilisateur_id>', methods=['GET', 'POST'])
@login_required
def profil_membre(utilisateur_id):
    utilisateur = Utilisateur.query.get_or_404(utilisateur_id)

    if request.method == 'POST' and utilisateur.id == current_user.id:
        utilisateur.photo_url = request.form.get('photo_url', '')
        utilisateur.bio = request.form.get('bio', '')
        db.session.commit()
        flash("Profil mis a jour.")
        return redirect(url_for('profil_membre', utilisateur_id=utilisateur.id))

    return render_template('profil_membre.html', utilisateur=utilisateur)


@app.route('/journal')
@login_required
def journal():
    entrees = JournalAudit.query.order_by(JournalAudit.date_heure.desc()).limit(50).all()
    return render_template('journal.html', entrees=entrees)


@app.route('/admin')
@login_required
def admin():
    premier_utilisateur = Utilisateur.query.order_by(Utilisateur.id).first()
    if current_user.id != premier_utilisateur.id:
        flash("Acces reserve a l'administrateur.")
        return redirect(url_for('accueil'))

    nb_utilisateurs = Utilisateur.query.count()
    nb_groupes = GroupeTontine.query.count()
    nb_cycles_actifs = Cycle.query.filter_by(statut='en_cours').count()

    volume_total = 0
    for cotisation in Cotisation.query.filter_by(statut='paye').all():
        volume_total += cotisation.montant

    dernieres_actions = JournalAudit.query.order_by(JournalAudit.date_heure.desc()).limit(10).all()

    return render_template(
        'admin.html',
        nb_utilisateurs=nb_utilisateurs,
        nb_groupes=nb_groupes,
        nb_cycles_actifs=nb_cycles_actifs,
        volume_total=volume_total,
        dernieres_actions=dernieres_actions
    )


@app.route('/historique')
@login_required
def historique():
    mes_membres = MembreGroupe.query.filter_by(utilisateur_id=current_user.id).all()
    ids_membres = [m.id for m in mes_membres]

    transactions = Cotisation.query.filter(
        Cotisation.membre_id.in_(ids_membres),
        Cotisation.statut == 'paye'
    ).order_by(Cotisation.date_paiement.desc()).all()

    return render_template('historique.html', transactions=transactions)


@app.route('/historique/export')
@login_required
def export_historique():
    mes_membres = MembreGroupe.query.filter_by(utilisateur_id=current_user.id).all()
    ids_membres = [m.id for m in mes_membres]

    transactions = Cotisation.query.filter(
        Cotisation.membre_id.in_(ids_membres),
        Cotisation.statut == 'paye'
    ).order_by(Cotisation.date_paiement.desc()).all()

    sortie = io.StringIO()
    ecrivain = csv.writer(sortie)
    ecrivain.writerow(['Date', 'Groupe', 'Montant (FCFA)', 'Operateur', 'Reference'])

    for t in transactions:
        ecrivain.writerow([
            t.date_paiement.strftime('%d/%m/%Y') if t.date_paiement else '',
            t.cycle.groupe.nom,
            t.montant,
            t.operateur or 'Manuel',
            t.reference_transaction or '-'
        ])

    enregistrer_action('export_historique', f"{current_user.nom} a exporte son historique")

    reponse = Response(sortie.getvalue(), mimetype='text/csv')
    reponse.headers['Content-Disposition'] = 'attachment; filename=historique_okoume_finance.csv'
    return reponse


@app.route('/mentions-legales')
def mentions_legales():
    return render_template('mentions_legales.html')


@app.route('/')
@login_required
def accueil():
    groupes = GroupeTontine.query.all()

    mes_cotisations_en_attente = []
    for groupe in groupes:
        for membre in groupe.membres:
            if membre.utilisateur_id == current_user.id:
                for cycle in groupe.cycles:
                    if cycle.statut == 'en_cours':
                        for cotisation in cycle.cotisations:
                            if cotisation.membre_id == membre.id and cotisation.statut == 'en_attente':
                                mes_cotisations_en_attente.append({
                                    'groupe': groupe.nom,
                                    'montant': cotisation.montant,
                                    'depuis': cycle.date_debut
                                })

    return render_template('accueil.html', groupes=groupes, rappels=mes_cotisations_en_attente)


@app.route('/nouveau-groupe', methods=['GET', 'POST'])
@login_required
def nouveau_groupe():
    if request.method == 'POST':
        nom = request.form['nom']
        montant = request.form['montant']
        frequence = request.form['frequence']
        nb_membres = request.form['nb_membres']
        description = request.form.get('description', '')
        photo_url = request.form.get('photo_url', '')

        groupe = GroupeTontine(
            nom=nom,
            montant_cotisation=montant,
            frequence=frequence,
            nb_membres=nb_membres,
            description=description,
            photo_url=photo_url
        )
        db.session.add(groupe)
        db.session.commit()

        enregistrer_action('creation_groupe', f"Groupe '{nom}' cree")
        return redirect(url_for('accueil'))

    return render_template('nouveau_groupe.html')


@app.route('/groupe/<int:groupe_id>', methods=['GET', 'POST'])
@login_required
def detail_groupe(groupe_id):
    groupe = GroupeTontine.query.get_or_404(groupe_id)

    if request.method == 'POST':
        nom = request.form['nom']
        telephone = request.form['telephone']

        utilisateur = Utilisateur.query.filter_by(telephone=telephone).first()
        if not utilisateur:
            utilisateur = Utilisateur(nom=nom, telephone=telephone, mot_de_passe_hash='', telephone_verifie=True)
            utilisateur.definir_mot_de_passe('changer123')
            db.session.add(utilisateur)
            db.session.commit()

        ordre = len(groupe.membres) + 1
        membre = MembreGroupe(
            utilisateur_id=utilisateur.id,
            groupe_id=groupe.id,
            ordre_tour=ordre
        )
        db.session.add(membre)
        db.session.commit()

        enregistrer_action('ajout_membre', f"{nom} ajoute au groupe '{groupe.nom}'")
        return redirect(url_for('detail_groupe', groupe_id=groupe.id))

    cycle_actif = Cycle.query.filter_by(groupe_id=groupe.id, statut='en_cours').first()

    return render_template('detail_groupe.html', groupe=groupe, cycle_actif=cycle_actif)


@app.route('/groupe/<int:groupe_id>/supprimer', methods=['POST'])
@login_required
def supprimer_groupe(groupe_id):
    groupe = GroupeTontine.query.get_or_404(groupe_id)
    nom_groupe = groupe.nom

    for cycle in groupe.cycles:
        Cotisation.query.filter_by(cycle_id=cycle.id).delete()
    Cycle.query.filter_by(groupe_id=groupe.id).delete()

    for membre in groupe.membres:
        MembreGroupe.query.filter_by(id=membre.id).delete()

    db.session.delete(groupe)
    db.session.commit()

    enregistrer_action('suppression_groupe', f"Groupe '{nom_groupe}' supprime")
    return redirect(url_for('accueil'))


@app.route('/membre/<int:membre_id>/supprimer', methods=['POST'])
@login_required
def supprimer_membre(membre_id):
    membre = MembreGroupe.query.get_or_404(membre_id)
    groupe_id = membre.groupe_id
    nom_membre = membre.utilisateur.nom

    Cotisation.query.filter_by(membre_id=membre.id).delete()
    db.session.delete(membre)
    db.session.commit()

    enregistrer_action('retrait_membre', f"{nom_membre} retire du groupe")
    return redirect(url_for('detail_groupe', groupe_id=groupe_id))


@app.route('/groupe/<int:groupe_id>/nouveau-cycle', methods=['POST'])
@login_required
def nouveau_cycle(groupe_id):
    groupe = GroupeTontine.query.get_or_404(groupe_id)

    if len(groupe.membres) == 0:
        flash("Impossible de demarrer un cycle : ajoutez d'abord au moins un membre.")
        return redirect(url_for('detail_groupe', groupe_id=groupe.id))

    nb_cycles_passes = Cycle.query.filter_by(groupe_id=groupe.id).count()
    membres_tries = sorted(groupe.membres, key=lambda m: m.ordre_tour)
    beneficiaire = membres_tries[nb_cycles_passes % len(membres_tries)]

    cycle = Cycle(
        groupe_id=groupe.id,
        beneficiaire_id=beneficiaire.id,
        date_debut=date.today(),
        statut='en_cours'
    )
    db.session.add(cycle)
    db.session.commit()

    for membre in groupe.membres:
        cotisation = Cotisation(
            cycle_id=cycle.id,
            membre_id=membre.id,
            montant=groupe.montant_cotisation,
            statut='en_attente'
        )
        db.session.add(cotisation)
    db.session.commit()

    enregistrer_action('nouveau_cycle', f"Cycle demarre pour '{groupe.nom}', beneficiaire : {beneficiaire.utilisateur.nom}")
    return redirect(url_for('detail_groupe', groupe_id=groupe.id))


@app.route('/cotisation/<int:cotisation_id>/marquer-paye', methods=['POST'])
@login_required
def marquer_paye(cotisation_id):
    cotisation = Cotisation.query.get_or_404(cotisation_id)
    cotisation.statut = 'paye'
    cotisation.date_paiement = date.today()
    db.session.commit()

    cycle = cotisation.cycle
    toutes_payees = all(c.statut == 'paye' for c in cycle.cotisations)

    if toutes_payees:
        cycle.statut = 'termine'
        db.session.commit()

    enregistrer_action('paiement', f"Cotisation {cotisation.montant} FCFA marquee payee manuellement")
    return redirect(url_for('detail_groupe', groupe_id=cycle.groupe_id))


@app.route('/cotisation/<int:cotisation_id>/payer-mobile-money', methods=['GET', 'POST'])
@login_required
def payer_mobile_money(cotisation_id):
    cotisation = Cotisation.query.get_or_404(cotisation_id)

    if request.method == 'POST':
        operateur = request.form['operateur']
        numero = request.form['numero']

        reference = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

        cotisation.statut = 'paye'
        cotisation.date_paiement = date.today()
        cotisation.operateur = operateur
        cotisation.reference_transaction = reference
        db.session.commit()

        cycle = cotisation.cycle
        toutes_payees = all(c.statut == 'paye' for c in cycle.cotisations)
        if toutes_payees:
            cycle.statut = 'termine'
            db.session.commit()

        enregistrer_action('paiement_mobile_money', f"Paiement {cotisation.montant} FCFA via {operateur}, ref {reference}")
        flash(f"Paiement simule avec succes via {operateur}. Reference : {reference}")
        return redirect(url_for('detail_groupe', groupe_id=cycle.groupe_id))

    return render_template('payer_mobile_money.html', cotisation=cotisation)


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)