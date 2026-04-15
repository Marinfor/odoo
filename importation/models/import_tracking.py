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
                # Intelligent initials: 3 letters uppercase
                partner_name = partner.name or 'VAR'
                initials = re.sub(r'[^A-Z0-9]', '', partner_name.upper())[:3]
                year = fields.Date.today().year
                # Get next sequence number
                seq = self.env['ir.sequence'].next_by_code('import.tracking') or '0000'
                # Extract only the numeric part (last 4 digits)
                num = ''.join(filter(str.isdigit, seq))[-4:]
                vals['name'] = f"{initials} - {year} - {num}"
        return super().create(vals_list)

    name = fields.Char(
        string='Référence Importation', 
        required=True, 
        copy=False, 
        tracking=True,
        default='/',
        placeholder="La référence sera générée automatiquement : Fournisseur - Année - N°"
    )
    
    # Informations Partenaires
    partner_id = fields.Many2one('res.partner', string='Fournisseur', required=True, tracking=True)
    forwarder_id = fields.Many2one('res.partner', string='Transitaire', tracking=True)
    
    # Information Facture
    invoice_number = fields.Char(string='Référence Facture', tracking=True)
    invoice_date = fields.Date(string='Date de la Facture', tracking=True)
    date_d10 = fields.Date(string='Date D10', tracking=True)
    
    # Finances
    currency_id = fields.Many2one(
        'res.currency', 
        string='Devise', 
        default=lambda self: self.env['res.currency'].search([('name', '=', 'DZD')], limit=1) or self.env.company.currency_id
    )
    # Détails des Produits (D10)
    product_line_ids = fields.One2many('import.tracking.product.line', 'tracking_id', string='Produits Importés')
    
    # Totaux D10 (Calculés à partir des lignes de produits)
    amount_ttc = fields.Monetary(string='Assiette Douane Totale', compute='_compute_d10_amounts', store=True, currency_field='currency_id')
    amount_dd = fields.Monetary(string='Montant DD Total', compute='_compute_d10_amounts', store=True, currency_field='currency_id')
    amount_tva = fields.Monetary(string='TVA (19%)', compute='_compute_d10_amounts', store=True, currency_field='currency_id')
    amount_prct = fields.Monetary(string='PRCT (2%)', compute='_compute_d10_amounts', store=True, currency_field='currency_id')
    amount_tcs = fields.Monetary(string='TCS (3%)', compute='_compute_d10_amounts', store=True, currency_field='currency_id')
    other_d10_frais = fields.Monetary(string='Autres Frais D10', currency_field='currency_id', tracking=True, help="Ex: RPS, etc.")
    other_d10_details = fields.Char(string='Détails Frais D10', placeholder="ex: RPS à 4000 DA")
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

    @api.depends('product_line_ids.amount_base', 'product_line_ids.amount_dd', 'product_line_ids.amount_tva', 'product_line_ids.amount_tcs', 'product_line_ids.amount_prct')
    def _compute_d10_amounts(self):
        for record in self:
            record.amount_ttc = sum(record.product_line_ids.mapped('amount_base'))
            record.amount_dd = sum(record.product_line_ids.mapped('amount_dd'))
            record.amount_tcs = sum(record.product_line_ids.mapped('amount_tcs'))
            record.amount_tva = sum(record.product_line_ids.mapped('amount_tva'))
            record.amount_prct = sum(record.product_line_ids.mapped('amount_prct'))
            record.amount_total_d10 = sum(record.product_line_ids.mapped('amount_total_line')) + record.other_d10_frais

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
    tva_rate = fields.Selection([
        ('0', '0%'),
        ('9', '9%'),
        ('19', '19%')
    ], string='Taux TVA', default='19')
    tva_amount = fields.Monetary(string='Montant TVA', compute='_compute_line_totals', store=True, currency_field='currency_id')
    total_amount = fields.Monetary(string='Montant TTC', compute='_compute_line_totals', store=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='tracking_id.currency_id')
    
    @api.depends('amount', 'tva_rate')
    def _compute_line_totals(self):
        for line in self:
            rate = float(line.tva_rate or 0.0) / 100.0
            line.tva_amount = line.amount * rate
            line.total_amount = line.amount + line.tva_amount

class ImportTrackingProductLine(models.Model):
    _name = 'import.tracking.product.line'
    _description = 'Ligne de produit importation'
    
    tracking_id = fields.Many2one('import.tracking', ondelete='cascade')
    name = fields.Char(string='Description', help="Nom ou description du produit")
    product_id = fields.Many2one('product.product', string='Produit catalogue')
    amount_base = fields.Monetary(string='Assiette', required=True, currency_field='currency_id')
    rate_dd = fields.Float(string='Taux DD (%)', default=30.0)
    
    # Taxes calculées par ligne
    amount_dd = fields.Monetary(string='Montant DD', compute='_compute_line_taxes', store=True, currency_field='currency_id')
    amount_tcs = fields.Monetary(string='TCS (3%)', compute='_compute_line_taxes', store=True, currency_field='currency_id')
    amount_tva = fields.Monetary(string='TVA (19%)', compute='_compute_line_taxes', store=True, currency_field='currency_id')
    amount_prct = fields.Monetary(string='PRCT (2%)', compute='_compute_line_taxes', store=True, currency_field='currency_id')
    amount_total_line = fields.Monetary(string='Total Taxes', compute='_compute_line_taxes', store=True, currency_field='currency_id')
    
    currency_id = fields.Many2one(related='tracking_id.currency_id')
    
    @api.depends('amount_base', 'rate_dd')
    def _compute_line_taxes(self):
        for line in self:
            # 1. DD
            line.amount_dd = (line.amount_base * line.rate_dd) / 100.0
            # 2. TCS (3% de l'assiette)
            line.amount_tcs = line.amount_base * 0.03
            # 3. TVA (19% de Assiette + DD + TCS)
            line.amount_tva = (line.amount_base + line.amount_dd + line.amount_tcs) * 0.19
            # 4. PRCT (2% de Assiette + TVA)
            line.amount_prct = (line.amount_base + line.amount_dd + line.amount_tcs + line.amount_tva) * 0.02
            # 5. Total des taxes de la ligne
            line.amount_total_line = line.amount_dd + line.amount_tcs + line.amount_tva + line.amount_prct