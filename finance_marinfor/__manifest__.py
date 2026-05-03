# -*- coding: utf-8 -*-
{
    'name': 'Gestion Finance Marinfor',
    'version': '1.1',
    'category': 'Finance',
    'author': 'Marinfor',
    'website': 'https://www.marinfor.com',
    'license': 'LGPL-3',
    'depends': [
        'base', 
        'web',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_data.xml',
        'data/mail_template_data.xml',
        'views/caution_views.xml',
        'views/asf_views.xml',
        'views/spot_views.xml',
        'views/menus.xml',
        'views/res_bank_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}