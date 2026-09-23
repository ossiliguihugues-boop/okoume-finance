from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.types import TypeDecorator, String
from datetime import date
from crypto_utils import chiffrer, dechiffrer

db = SQLAlchemy()


class ChampChiffre(TypeDecorator):
    """Type de colonne qui chiffre/dechiffre automatiquement une valeur numerique."""
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return chiffrer(value)

    def process_result_value(self, value, dialect):
        resultat = dechiffrer(value)
        return float(resultat) if resultat is not None else None


class Utilisateur(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(20), unique=True, nullable=False)
    mot_de_passe_hash = db.Column(db.String(200), nullable=False)
    telephone_verifie = db.Column(db.Boolean, default=False)
    code_verification = db.Column(db.String(10))

    memberships = db.relationship('MembreGroupe', backref='utilisateur', lazy=True)

    def definir_mot_de_passe(self, mot_de_passe):
        self.mot_de_passe_hash = generate_password_hash(mot_de_passe)

    def verifier_mot_de_passe(self, mot_de_passe):
        return check_password_hash(self.mot_de_passe_hash, mot_de_passe)


class GroupeTontine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    montant_cotisation = db.Column(ChampChiffre(300), nullable=False)
    frequence = db.Column(db.String(20), nullable=False)
    nb_membres = db.Column(db.Integer, nullable=False)

    membres = db.relationship('MembreGroupe', backref='groupe', lazy=True)
    cycles = db.relationship('Cycle', backref='groupe', lazy=True)


class MembreGroupe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    groupe_id = db.Column(db.Integer, db.ForeignKey('groupe_tontine.id'), nullable=False)
    ordre_tour = db.Column(db.Integer, nullable=False)


class Cycle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    groupe_id = db.Column(db.Integer, db.ForeignKey('groupe_tontine.id'), nullable=False)
    beneficiaire_id = db.Column(db.Integer, db.ForeignKey('membre_groupe.id'), nullable=False)
    date_debut = db.Column(db.Date, default=date.today)
    statut = db.Column(db.String(20), default='en_cours')

    cotisations = db.relationship('Cotisation', backref='cycle', lazy=True)
    beneficiaire = db.relationship('MembreGroupe', foreign_keys=[beneficiaire_id])


class Cotisation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cycle_id = db.Column(db.Integer, db.ForeignKey('cycle.id'), nullable=False)
    membre_id = db.Column(db.Integer, db.ForeignKey('membre_groupe.id'), nullable=False)
    montant = db.Column(ChampChiffre(300), nullable=False)
    date_paiement = db.Column(db.Date)
    statut = db.Column(db.String(20), default='en_attente')
    operateur = db.Column(db.String(20))
    reference_transaction = db.Column(db.String(50))

    membre = db.relationship('MembreGroupe', foreign_keys=[membre_id])


class JournalAudit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.String(300))
    date_heure = db.Column(db.DateTime, default=db.func.now())