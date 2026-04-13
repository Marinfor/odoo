from odoo import models, fields, api, _
import re

class ImportTracking(models.Model):
    _name = 'import.tracking'
    _description = 'importation Marinfor'
    _inherit = ['mail.thread', 'mail.activity.mixin'] # Pour le chatter et les activités
    _order = 'name desc'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == '/':
                # Get partner name for the prefix
                partner = self.env['res.partner'].browse(vals.get('partner_id'))
                partner_code = re.sub(r'[^A-Z0-9]', '', (partner.name or 'VAR').split()[0].upper())
                year = fields.Date.today().year
                # Get next sequence number
                seq = self.env['ir.sequence'].next_by_code('import.tracking') or '0000'
                # Extract only the numeric part (last 4 digits)
                num = ''.join(filter(str.isdigit, seq))[-4:]
                vals['name'] = f"{partner_code}-{year}-{num}"
        return super().create(vals_list)

    name = fields.Char(
        string='Référence Importation', 
        required=True, 
        copy=False, 
        tracking=True,
        placeholder="Saisissez la référence unique du dossier..."
    )
    
    # Informations Partenaires
    partner_id = fields.Many2one('res.partner', string='Fournisseur', required=True, tracking=True)
    forwarder_id = fields.Many2one('res.partner', string='Transitaire', tracking=True)
    
    # Information Facture
    invoice_number = fields.Char(string='Référence Facture', tracking=True)
    invoice_date = fields.Date(string='Date de la Facture', tracking=True)
    date_d10 = fields.Date(string='Date D10', tracking=True)
    
    # Finances
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id)
    amount_ttc = fields.Monetary(string='Assiette Douane', currency_field='currency_id', tracking=True)
    
    # Détails D10 (Taxes segmentées pour le DD)
    dd_line_ids = fields.One2many('import.tracking.dd.line', 'tracking_id', string='Segmentation DD')
    
    # Totaux D10 (Calculés)
    amount_dd = fields.Monetary(string='Montant DD Total', compute='_compute_d10_amounts', store=True, currency_field='currency_id')
    amount_tva = fields.Monetary(string='TVA (19%)', compute='_compute_d10_amounts', store=True, currency_field='currency_id')
    amount_prct = fields.Monetary(string='PRCT (2%)', compute='_compute_d10_amounts', store=True, currency_field='currency_id')
    amount_tcs = fields.Monetary(string='TCS (3%)', compute='_compute_d10_amounts', store=True, currency_field='currency_id')
    amount_total_d10 = fields.Monetary(string='Total Taxes D10', compute='_compute_d10_amounts', store=True, currency_field='currency_id')
    
    # Autres Frais
    expense_line_ids = fields.One2many('import.tracking.line', 'tracking_id', string='Autres Frais')
    total_expenses_ht = fields.Monetary(string='Total Hors Taxe', compute='_compute_expense_totals', store=True, currency_field='currency_id')
    total_expenses_tva = fields.Monetary(string='Total TVA', compute='_compute_expense_totals', store=True, currency_field='currency_id')
    total_expenses_ttc = fields.Monetary(string='Total Autres Frais', compute='_compute_expense_totals', store=True, currency_field='currency_id')

    # Synthèse Globale et Coût de Revient
    total_amount_global = fields.Monetary(string='Montant Total TTC', compute='_compute_global_totals', store=True, currency_field='currency_id', tracking=True)
    total_tva_global = fields.Monetary(string='Total TVA Global', compute='_compute_global_totals', store=True, currency_field='currency_id', tracking=True)
    total_cost_price = fields.Monetary(string='Coût de Revient Total', compute='_compute_global_totals', store=True, currency_field='currency_id', tracking=True)

    @api.depends('amount_ttc', 'dd_line_ids.amount_tax_line')
    def _compute_d10_amounts(self):
        for record in self:
            # Le DD est maintenant la somme des tranches segmentées
            record.amount_dd = sum(record.dd_line_ids.mapped('amount_tax_line'))
            
            # Les autres taxes restent basées sur l'Assiette Douane totale (TTC)
            record.amount_tva = record.amount_ttc * 0.19
            record.amount_prct = record.amount_ttc * 0.02
            record.amount_tcs = record.amount_ttc * 0.03
            record.amount_total_d10 = record.amount_dd + record.amount_tva + record.amount_prct + record.amount_tcs

    @api.depends('expense_line_ids.amount', 'expense_line_ids.tva_amount')
    def _compute_expense_totals(self):
        for record in self:
            record.total_expenses_ht = sum(record.expense_line_ids.mapped('amount'))
            record.total_expenses_tva = sum(record.expense_line_ids.mapped('tva_amount'))
            record.total_expenses_ttc = sum(record.expense_line_ids.mapped('total_amount'))

    @api.depends('amount_ttc', 'amount_total_d10', 'total_expenses_ttc', 'amount_tva', 'total_expenses_tva')
    def _compute_global_totals(self):
        for record in self:
            record.total_amount_global = record.amount_ttc + record.amount_total_d10 + record.total_expenses_ttc
            record.total_tva_global = record.amount_tva + record.total_expenses_tva
            record.total_cost_price = record.total_amount_global - record.total_tva_global
    
    # Champs de maintenance Odoo
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('shipped', 'En cours de transport'),
        ('customs', 'En Dédouanement'),
        ('received', 'Réceptionné'),
        ('cancelled', 'Annulé')
    ], string='Statut', default='draft', tracking=True)

    company_id = fields.Many2one('res.company', string='Société', default=lambda self: self.env.company)

    def action_confirm(self):
        self.state = 'confirmed'

    def action_done(self):
        self.state = 'received'

class ImportTrackingLine(models.Model):
    _name = 'import.tracking.line'
    _description = 'Ligne de frais d importation'
    
    tracking_id = fields.Many2one('import.tracking', string='Importation', ondelete='cascade')
    name = fields.Char(string='Description des frais', required=True)
    amount = fields.Monetary(string='Montant Hors Taxe', currency_field='currency_id')
    has_tva = fields.Boolean(string='Avec TVA', default=False)
    tva_amount = fields.Monetary(string='Montant TVA (19%)', compute='_compute_line_totals', store=True, currency_field='currency_id')
    total_amount = fields.Monetary(string='Montant TTC', compute='_compute_line_totals', store=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='tracking_id.currency_id')
    
    @api.depends('amount', 'has_tva')
    def _compute_line_totals(self):
        for line in self:
            line.tva_amount = line.amount * 0.19 if line.has_tva else 0.0
            line.total_amount = line.amount + line.tva_amount

class ImportTrackingDDLine(models.Model):
    _name = 'import.tracking.dd.line'
    _description = 'Tranche de Droits de Douane'
    
    tracking_id = fields.Many2one('import.tracking', ondelete='cascade')
    amount_base = fields.Monetary(string='Tranche d\'Assiette', currency_field='currency_id')
    rate_dd = fields.Float(string='Taux DD (%)')
    amount_tax_line = fields.Monetary(string='Montant DD', compute='_compute_tax_line', store=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='tracking_id.currency_id')
    
    @api.depends('amount_base', 'rate_dd')
    def _compute_tax_line(self):
        for line in self:
            line.amount_tax_line = (line.amount_base * line.rate_dd) / 100.0