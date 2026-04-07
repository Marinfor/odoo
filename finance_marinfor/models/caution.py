# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date
from dateutil.relativedelta import relativedelta
import math

class FinanceCaution(models.Model):
    _name = 'finance.caution'
    # Ajout de l'héritage pour le suivi (Chatter)
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Gestion des Cautions Marinfor'
    _order = 'date_echeance desc'

    # Ajout de tracking=True sur les champs pour suivre les modifications par utilisateur
    name = fields.Char(string="Référence", required=True, copy=False, tracking=True)
    
    type_caution = fields.Selection([
        ('soumission', 'Soumission'),
        ('gbe', 'Garantie de Bonne Exécution (GBE)')
    ], string="Type de Caution", default='soumission', required=True, tracking=True)
    
    banque = fields.Selection([
        ('bnp', 'BNP Paribas'),
        ('sg', 'Société Générale'),
        ('ca', 'Crédit Agricole'),
        ('fb', 'FRANSABANK'),
        ('natixis', 'Natixis'),
        ('sga', 'SGA')
    ], string="Banque", required=True, tracking=True)
    
    beneficiaire = fields.Char(string="Bénéficiaire", required=True, tracking=True)
    
    # Gestion de la devise (Monetary)
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id, required=True, tracking=True)
    montant = fields.Monetary(string="Montant de la Caution", currency_field='currency_id', required=True, tracking=True)
    
    # --- Dates de Suivi ---
    date_soumission = fields.Date(string="Date de Soumission")
    date_notification = fields.Date(string="Date de Notification")
    date_limite_depot = fields.Date(string="Date Limite de Dépôt", tracking=True)
    date_depot = fields.Date(string="Date de Dépôt Réelle", tracking=True)
    
    # --- Logique Spécifique GBE ---
    date_pv_reception = fields.Date(string="Date PV Réception Provisoire")
    duree_garantie = fields.Integer(string="Durée Garantie (mois)", default=12)

    # --- Gestion de la Main Levée Partielle ---
    is_partial_release = fields.Boolean(string="Main-levée partielle", tracking=True)
    partial_amount_released = fields.Monetary(string="Montant libéré", currency_field='currency_id', tracking=True)
    date_partial_release = fields.Date(string="Date de main-levée partielle", tracking=True)
    
    # --- Calculs Automatiques ---
    date_echeance = fields.Date(string="Échéance", compute="_compute_echeance", store=True, readonly=False, tracking=True)
    frais_caution = fields.Monetary(string="Frais de Caution", currency_field='currency_id', compute="_compute_frais", store=True)
    
    state = fields.Selection([
        ('active', 'Active'),
        ('main_levee', 'Main Levée'),
        ('restituee', 'Restituée')
    ], string="Statut", compute="_compute_state", store=True, readonly=False, default='active', tracking=True)

    # --- Indicateurs pour Alertes Visuelles (Tableau de bord) ---
    is_late_depot = fields.Boolean(compute="_compute_alerts", string="Retard de Dépôt")
    is_near_expiry = fields.Boolean(compute="_compute_alerts", string="Échéance Proche")
    # Nouvelle alerte : Main levée non récupérée après 7 jours
    is_pending_restitution = fields.Boolean(compute="_compute_alerts", string="Restitution en retard")

    @api.depends('type_caution', 'date_pv_reception', 'duree_garantie')
    def _compute_echeance(self):
        """ Calcule l'échéance auto pour GBE : PV + Durée mois """
        for record in self:
            if record.type_caution == 'gbe' and record.date_pv_reception:
                try:
                    record.date_echeance = record.date_pv_reception + relativedelta(months=record.duree_garantie)
                except (ValueError, TypeError):
                    record.date_echeance = False
            elif not record.date_echeance:
                # Si pas GBE ou pas de date PV, et pas de date échéance manuelle, on laisse vide
                pass

    @api.constrains('montant', 'partial_amount_released', 'is_partial_release')
    def _check_partial_amount(self):
        for record in self:
            if record.is_partial_release and record.partial_amount_released > record.montant:
                raise UserError("Le montant libéré ne peut pas être supérieur au montant total de la caution.")

    @api.depends('montant', 'date_depot', 'date_soumission', 'date_echeance', 'state',
                 'is_partial_release', 'partial_amount_released', 'date_partial_release')
    def _compute_frais(self):
        """ 
        Calcul des frais selon la règle bancaire : Tout trimestre entamé est dû au montant fort.
        Logique par soustraction de l'économie réalisée par la main-levée.
        """
        today = date.today()
        for record in self:
            # Fallbacks pour que le calcul s'affiche même si les données sont partielles
            start_date = record.date_depot or record.date_soumission
            end_date = record.date_echeance or (today if record.state == 'active' else False)
            
            if not (record.montant > 0 and start_date and end_date and start_date < end_date):
                record.frais_caution = 0.0
                continue

            # 1. Calcul des frais maximums (sans aucune libération)
            frais_max = self._calculate_period_frais(record.montant, start_date, end_date)

            # 2. Calcul de l'économie réalisée par la main-levée partielle
            economie = 0.0
            if (record.is_partial_release and 
                record.partial_amount_released > 0 and 
                record.date_partial_release and 
                start_date <= record.date_partial_release < end_date):
                
                # Déterminer quand commence la réduction (Trimestre suivant la main-levée)
                # On ajoute +1 jour car le jour de la main-levée est considéré comme "entamé" avec le montant fort
                date_effective_ml = record.date_partial_release + relativedelta(days=1)
                diff_ml = relativedelta(date_effective_ml, start_date)
                nb_trim_parcourus = math.ceil(((diff_ml.years * 12) + diff_ml.months + (1 if diff_ml.days > 0 else 0)) / 3.0)
                
                date_debut_reduction = start_date + relativedelta(months=int(nb_trim_parcourus * 3))
                
                # L'économie ne s'applique que si la réduction commence avant l'échéance
                if date_debut_reduction < end_date:
                    economie = self._calculate_period_frais(
                        record.partial_amount_released,
                        date_debut_reduction,
                        end_date
                    )
            
            record.frais_caution = max(0.0, frais_max - economie)

    def _calculate_period_frais(self, montant, start_date, end_date):
        """ Calcule les frais pour une période donnée (2.5% / trimestre entamé) """
        if montant <= 0 or not start_date or not end_date or start_date >= end_date:
            return 0.0
            
        diff = relativedelta(end_date, start_date)
        
        # Mois entamé = Mois dû
        total_mois = (diff.years * 12) + diff.months + (1 if diff.days > 0 else 0)
        
        # Trimestre entamé = Trimestre dû
        nb_trimestres = max(1, math.ceil(total_mois / 3.0))
        
        return montant * 0.025 * nb_trimestres

    @api.depends('date_echeance', 'date_limite_depot', 'date_depot', 'state')
    def _compute_alerts(self):
        """ Logique des couleurs Traffic Light """
        today = date.today()
        for record in self:
            # ROUGE : GBE notifiée, pas encore déposée, et limite dans moins de 2 jours
            record.is_late_depot = (
                record.type_caution == 'gbe' and 
                not record.date_depot and 
                record.date_limite_depot and 
                record.date_limite_depot <= (today + relativedelta(days=2))
            )
            # ORANGE : Active et expiration dans moins de 15 jours
            record.is_near_expiry = (
                record.state == 'active' and 
                record.date_echeance and 
                today <= record.date_echeance <= (today + relativedelta(days=15))
            )
            # 3. Alerte BLEUE (Restitution traîne > 7 jours après échéance)
            if record.state == 'main_levee' and record.date_echeance:
                record.is_pending_restitution = record.date_echeance <= (today - relativedelta(days=7))
            else:
                record.is_pending_restitution = False

    def _cron_send_caution_alerts(self):
        """ Fonction appelée par l'action planifiée """
        template = self.env.ref('finance_marinfor.email_template_caution_alerte')
        # On cherche toutes les cautions ayant au moins une alerte
        cautions = self.search(['|', '|', 
            ('is_late_depot', '=', True), 
            ('is_near_expiry', '=', True), 
            ('is_pending_restitution', '=', True)
        ])
        for caution in cautions:
            # Envoi de l'email et ajout d'une note dans le chatter
            caution.message_post_with_source(
                template,
                subtype_xmlid='mail.mt_comment',
            )

    @api.depends('date_echeance')
    def _compute_state(self):
        """ Passage auto en Main Levée si la date est dépassée (BLEU en vue liste) """
        today = date.today()
        for record in self:
            if record.state == 'restituee':
                continue
            if record.date_echeance and record.date_echeance < today:
                record.state = 'main_levee'
            else:
                record.state = 'active'

    def action_restituer(self):
        """ Bouton manuel pour confirmer la récupération du document """
        for record in self:
            if record.state == 'active':
                raise UserError("Impossible de restituer une caution active. Elle doit être en Main Levée.")
            record.state = 'restituee'