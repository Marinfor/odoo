# -*- coding: utf-8 -*-
from odoo import models, fields

class ResBank(models.Model):
    _inherit = 'res.bank'

    rib = fields.Char(string='RIB / Numéro de Compte')
