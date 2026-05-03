{
    'name': 'Marinfor Reporting',
    'version': '1.0',
    'category': 'Extra Tools',
    'summary': 'Daily debrief reports for Finance, Importation and Projects',
    'author': 'Antigravity',
    'depends': [
        'base',
        'mail',
        'marinfor_project',
        'finance_marinfor',
        'importation',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'views/daily_report_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
