# -*- coding: utf-8 -*-
from odoo import models, fields

class MarinforBank(models.Model):
    _name = 'marinfor.bank'
    _description = 'Banque Marinfor'

    name = fields.Char(string='Nom de la Banque', required=True)
    rib = fields.Char(string='RIB / Numéro de Compte', required=True)
    active = fields.Boolean(default=True)
