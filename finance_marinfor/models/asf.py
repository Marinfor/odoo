from odoo import models, fields, api
from datetime import date, timedelta
import math

class FinanceASF(models.Model):
    _name = 'finance.asf'
    _description = 'Avance Sur Facture (ASF)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_expiry desc'

    name = fields.Char(string="N° ASF", required=True, copy=False, default='Nouveau', tracking=True)
    banque = fields.Selection([
        ('bnp', 'BNP Paribas'),
        ('sg', 'Société Générale'),
        ('ca', 'Crédit Agricole'),
        ('fb', 'FRANSABANK'),
        ('natixis', 'Natixis'),
        ('sga', 'SGA')
    ], string="Banque", required=True, tracking=True)
    invoice_number = fields.Char(string="N° Facture", required=True, tracking=True)
    beneficiary_id = fields.Many2one('res.partner', string="Bénéficiaire", tracking=True)
    
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id, required=True)
    amount = fields.Monetary(string="Montant de l'Avance", currency_field='currency_id', required=True, tracking=True)
    
    date_delivery = fields.Date(string="Date de délivrance", default=fields.Date.context_today, tracking=True)
    date_expiry = fields.Date(string="Échéance", required=True, tracking=True)
    
    # Calcul des frais
    fees_amount = fields.Monetary(string="Frais d'ASF (DZD)", currency_field='currency_id', compute="_compute_asf_fees", store=True)

    state = fields.Selection([
        ('en_cours', 'En cours'),
        ('echue', 'Échue'),
        ('rembourse', 'Remboursé')
    ], string="Statut", default='en_cours', compute="_compute_state", store=True, readonly=False, tracking=True)

    is_near_expiry = fields.Boolean(compute="_compute_alerts", string="Échéance Proche")

    @api.depends('amount', 'date_delivery', 'date_expiry')
    def _compute_asf_fees(self):
        for record in self:
            if record.amount and record.date_delivery and record.date_expiry:
                # Calcul de la différence en jours
                delta = record.date_expiry - record.date_delivery
                days = delta.days
                
                # Nombre de trimestres (on arrondit toujours au supérieur)
                nb_trimestres = math.ceil(days / 90) if days > 0 else 1
                
                # Formule : Montant * 2.5% * nb_trimestres
                record.fees_amount = record.amount * 0.025 * nb_trimestres
            else:
                record.fees_amount = 0.0

    @api.depends('date_expiry', 'state')
    def _compute_alerts(self):
        today = fields.Date.today()
        for record in self:
            record.is_near_expiry = (
                record.state == 'en_cours' and 
                record.date_expiry and 
                today <= record.date_expiry <= (today + timedelta(days=15))
            )

    @api.depends('date_expiry')
    def _compute_state(self):
        today = fields.Date.today()
        for record in self:
            if record.state == 'rembourse':
                continue
            if record.date_expiry and record.date_expiry < today:
                record.state = 'echue'
            else:
                record.state = 'en_cours'

    def action_rembourser(self):
        for record in self:
            record.state = 'rembourse'

