# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)

class DailyReport(models.TransientModel):
    _name = 'marinfor.daily.report'
    _description = 'Marinfor Daily Debrief'

    def send_daily_debrief(self, **kwargs):
        """Gather data and send daily debrief email."""
        # Ensure we can run it from model or record
        self = self.sudo()
        
        # 1. Projects Data
        projects = self.env['project.lifecycle'].search([
            ('state', 'not in', ('realized', 'cancelled'))
        ])
        today = date.today()
        
        # Projets en retard ou proches de l'échéance
        critical_projects = projects.filtered(
            lambda p: (p.realization_deadline and p.realization_deadline < today) or
                      (p.realization_remaining_days > 0 and p.realization_remaining_days < 10) or
                      (p.tender_submission_deadline and p.tender_submission_deadline <= (today + timedelta(days=3)) and p.state == 'tender')
        )
        warranty_projects = projects.filtered(
            lambda p: p.state == 'done' and p.warranty_remaining_days > 0 and p.warranty_remaining_days < 30
        )

        # 2. Finance Data
        all_cautions = self.env['finance.caution'].search([
            ('state', '!=', 'restituee')
        ])
        active_cautions = all_cautions.filtered(lambda c: c.state == 'active')
        expiring_cautions = active_cautions.filtered(
            lambda c: c.date_echeance and (c.date_echeance - date.today()).days < 15
        )
        main_levee_cautions = all_cautions.filtered(lambda c: c.state == 'main_levee')

        # 3. Importation Data
        active_imports = self.env['import.tracking'].search([
            ('state', 'not in', ('received', 'cancelled'))
        ])

        # Prepare context for the email
        template_context = {
            'projects': projects,
            'critical_projects': critical_projects,
            'warranty_projects': warranty_projects,
            'active_cautions': active_cautions,
            'expiring_cautions': expiring_cautions,
            'main_levee_cautions': main_levee_cautions,
            'active_imports': active_imports,
            'today': date.today().strftime('%d/%m/%Y'),
        }

        # Send email to managers (or a specific group)
        # For now, let's target all users in the Project Manager or Finance Manager group
        # Or better, just a specific email configured in parameters or the company email.
        
        # Send email
        # Priority 1: System Parameter 'marinfor_reporting.recipients'
        # Priority 2: Company Email
        # Priority 3: Default admin address
        
        recipient_param = self.env['ir.config_parameter'].sudo().get_param('marinfor_reporting.recipients')
        email_to = recipient_param or self.env.company.email or 'admin@example.com'

        template = self.env.ref('marinfor_reporting.email_template_daily_debrief_v2', raise_if_not_found=False)
        if template:
            email_values = {
                'email_to': email_to,
            }
            template.with_context(**template_context).send_mail(self.id or self.env.user.id, force_send=True, email_values=email_values)
            _logger.info("Daily debrief sent to %s", email_to)
        else:
            _logger.warning("Daily debrief template not found.")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': _('Le débriefing a été envoyé avec succès à %s') % email_to,
                'sticky': False,
                'type': 'success',
            }
        }
