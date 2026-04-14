# importation_marinfor/__manifest__.py
{
    'name': 'importation Marinfor',
    'version': '1.0',
    'category': 'Operations/Logistics',
    'summary': 'Gestion et importation Marinfor et logistique',
    'description': """
        Module importation Marinfor.
        - Suivi des étapes (ETD, ETA)
        - Gestion des transitaires et incoterms
        - Centralisation des documents de douane
    """,
    'author': 'Votre Nom',
    'depends': [
        'base',
        'purchase',
        'stock',
        'mail', # Pour le chatter (historique et notes)
    ],
    
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/currency_data.xml',
        'views/import_tracking_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}