from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    rc_selection = fields.Selection([
        ('rc_01', 'RC N° 16/00-1234567 B 20'),
        ('rc_02', 'RC N° 16/00-9876543 B 20'),
    ], string="Registre du Commerce", default='rc_01')
    
    nif_selection = fields.Selection([
        ('nif_01', '000123456789012'),
        ('nif_02', '000987654321098'),
    ], string="NIF")

    rib_selection = fields.Selection([
        ('bna', 'BNA: 00100 00000 1234567890'),
        ('bea', 'BEA: 00200 00000 0987654321'),
    ], string="RIB de l'entreprise")