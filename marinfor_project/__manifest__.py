# -*- coding: utf-8 -*-
{
    'name': 'Marinfor - Gestion de Projet',
    'version': '18.0.1.0.0',
    'category': 'Project',
    'summary': 'Cycle de vie complet des projets Marinfor',
    'description': """
        Module pivot pour la gestion du cycle de vie des projets :
        - Appel d'offre → Délibération → Notification → Administratif → Importation → Réalisation
        - Intégration avec les modules importation et finance_marinfor
    """,
    'author': 'Marinfor',
    'depends': ['base', 'mail', 'importation', 'finance_marinfor'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_lifecycle_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
