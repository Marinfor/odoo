# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProjectLifecycle(models.Model):
    _name = 'project.lifecycle'
    _description = 'Cycle de Vie Projet Marinfor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # =====================================================================
    # Champs Généraux
    # =====================================================================
    name = fields.Char(
        string='Référence Projet',
        required=True, copy=False, tracking=True,
        default=lambda self: _('Nouveau'),
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Société',
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Devise',
        related='company_id.currency_id', store=True,
    )
    bank_id = fields.Many2one(
        'res.bank', string='Banque du Projet', tracking=True,
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('tender', 'Appel d\'Offre'),
        ('deliberation', 'Offre Soumise'),
        ('notification', 'Notification'),
        ('administrative', 'Administratif'),
        ('importation', 'Importation'),
        ('realization', 'Réalisation'),
        ('done', 'Terminé (Sous Garantie)'),
        ('realized', 'Réalisé (Archive)'),
        ('cancelled', 'Annulé'),
    ], string='État', default='draft', tracking=True, group_expand='_expand_states')

    active = fields.Boolean(default=True)

    # =====================================================================
    # Phase 1 : BROUILLON (Draft)
    # =====================================================================
    partner_id = fields.Many2one(
        'res.partner', string='Client',
        required=True, tracking=True,
    )
    tender_number = fields.Char(
        string='N° Appel d\'Offre', tracking=True,
    )
    tender_submission_deadline = fields.Date(
        string='Date Limite de Soumission', tracking=True,
    )

    # =====================================================================
    # Phase 2 : APPEL D'OFFRE (Tender)
    # =====================================================================
    caution_soumission_id = fields.Many2one(
        'finance.caution', string='Caution de Soumission',
        domain="[('type_caution', '=', 'soumission')]",
        tracking=True,
    )

    # =====================================================================
    # Phase 3 : DÉLIBÉRATION (Deliberation)
    # =====================================================================
    deliberation_file = fields.Binary(
        string='PV de Délibération (PDF)', attachment=True,
    )
    deliberation_filename = fields.Char(string='Nom du fichier')
    deliberation_result = fields.Selection([
        ('won', 'Gagné'),
        ('partial', 'Partiel'),
        ('lost', 'Null'),
    ], string='Résultat Délibération', tracking=True)
    offer_validity_date = fields.Date(
        string="Date de Validité de l'Offre", tracking=True,
    )

    # =====================================================================
    # Phase 4 : NOTIFICATION
    # =====================================================================
    notification_date = fields.Date(
        string='Date de Notification', tracking=True,
    )
    delay_days = fields.Integer(
        string='Délai (jours)', tracking=True,
    )
    realization_deadline = fields.Date(
        string='Date Limite de Réalisation',
        compute='_compute_realization_deadline', store=True,
    )
    realization_remaining_days = fields.Integer(
        string='Jours Restants (Réalisation)',
        compute='_compute_realization_remaining',
    )
    project_technical_name = fields.Char(
        string='Nom du Projet Technique', tracking=True,
    )
    caution_gbe_id = fields.Many2one(
        'finance.caution', string='Caution GBE',
        domain="[('type_caution', '=', 'gbe')]",
        tracking=True,
    )

    # =====================================================================
    # Phase 5 : ADMINISTRATIF
    # =====================================================================
    # --- ALGEX ---
    algex_status = fields.Selection([
        ('na', 'Non Applicable'),
        ('submitted', 'Soumis'),
        ('obtained', 'Obtenu'),
        ('refused', 'Refusé'),
    ], string='Statut ALGEX', default='na', tracking=True)
    algex_submission_date = fields.Date(string='Date Soumission ALGEX')
    algex_decision_date = fields.Date(string='Date Décision ALGEX')

    # --- Homologation ---
    homologation_status = fields.Selection([
        ('not_required', 'Non Requise'),
        ('submitted', 'Soumise (Produits notés)'),
        ('obtained', 'Obtenue'),
    ], string='Statut Homologation', default='not_required', tracking=True)
    homologation_notes = fields.Text(string='Produits à Homologuer / Notes')

    # --- Bons de Commande Client ---
    client_order_ids = fields.One2many(
        'project.client.order', 'project_id',
        string='Bons de Commande Client',
    )

    # =====================================================================
    # Phase 6 : IMPORTATION
    # =====================================================================
    import_tracking_ids = fields.One2many(
        'import.tracking', 'project_id',
        string='Importations Liées',
    )
    import_count = fields.Integer(
        string='Nb Importations',
        compute='_compute_import_count',
    )

    # =====================================================================
    # Phase 7 : RÉALISATION
    # =====================================================================
    delivery_status = fields.Selection([
        ('pending', 'En attente'),
        ('in_progress', 'En cours'),
        ('delivered', 'Livré'),
    ], string='Statut Livraison', compute='_compute_delivery_status', store=True, tracking=True)

    # --- Garantie ---
    warranty_duration = fields.Integer(string='Durée Garantie (mois)', default=12)
    warranty_start_date = fields.Date(string='Début Garantie')
    warranty_end_date = fields.Date(string='Fin Garantie', compute='_compute_warranty_end', store=True)

    # --- Champs pour le Dashboard ---
    client_order_count = fields.Integer(string='Nb Bons Commande', compute='_compute_client_order_count')
    dashboard_status = fields.Char(string='Info Dynamique', compute='_compute_dashboard_status')
    warranty_remaining_days = fields.Integer(string='Jours de Garantie Restants', compute='_compute_warranty_remaining')

    # =====================================================================
    # Séquence automatique
    # =====================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'project.lifecycle'
                ) or _('Nouveau')
        return super().create(vals_list)

    # =====================================================================
    # Computes
    # =====================================================================
    @api.depends('import_tracking_ids')
    def _compute_import_count(self):
        for record in self:
            record.import_count = len(record.import_tracking_ids)

    @api.depends('client_order_ids')
    def _compute_client_order_count(self):
        for record in self:
            record.client_order_count = len(record.client_order_ids)

    @api.depends('warranty_end_date')
    def _compute_warranty_remaining(self):
        from datetime import date
        today = date.today()
        for record in self:
            if record.warranty_end_date and record.warranty_end_date > today:
                delta = record.warranty_end_date - today
                record.warranty_remaining_days = delta.days
            else:
                record.warranty_remaining_days = 0

    @api.depends('notification_date', 'delay_days')
    def _compute_realization_deadline(self):
        from datetime import timedelta
        for record in self:
            if record.notification_date and record.delay_days:
                record.realization_deadline = record.notification_date + timedelta(days=record.delay_days)
            else:
                record.realization_deadline = False

    @api.depends('realization_deadline')
    def _compute_realization_remaining(self):
        from datetime import date
        today = date.today()
        for record in self:
            if record.realization_deadline and record.realization_deadline > today:
                delta = record.realization_deadline - today
                record.realization_remaining_days = delta.days
            else:
                record.realization_remaining_days = 0

    @api.depends('state', 'algex_status', 'homologation_status', 'client_order_count', 'import_tracking_ids.state', 
                 'warranty_remaining_days', 'warranty_end_date', 'realization_remaining_days', 'realization_deadline')
    def _compute_dashboard_status(self):
        for record in self:
            res_deadline_str = ""
            if record.realization_deadline and record.state in ('notification', 'administrative', 'importation', 'realization'):
                res_deadline_str = f" | {record.realization_remaining_days}j restants"

            if record.state == 'notification':
                record.dashboard_status = f"Notifié{res_deadline_str}"
            elif record.state == 'administrative':
                algex = dict(record._fields['algex_status'].selection).get(record.algex_status)
                record.dashboard_status = f"ALGEX: {algex} | BC: {record.client_order_count}{res_deadline_str}"
            elif record.state == 'importation':
                total = len(record.import_tracking_ids)
                received = len(record.import_tracking_ids.filtered(lambda i: i.state == 'received'))
                record.dashboard_status = f"Imports: {received}/{total}{res_deadline_str}"
            elif record.state == 'realization':
                if record.realization_deadline:
                    record.dashboard_status = f"Réalisation: {record.realization_remaining_days} j restants"
                else:
                    record.dashboard_status = "Réalisation en cours"
            elif record.state == 'done':
                if record.warranty_end_date:
                    record.dashboard_status = f"Garantie: {record.warranty_remaining_days} j restants"
                else:
                    record.dashboard_status = "Sous Garantie"
            elif record.state == 'realized':
                record.dashboard_status = "Projet Clôturé - Archive"
            else:
                record.dashboard_status = False

    @api.depends('state')
    def _compute_delivery_status(self):
        for record in self:
            if record.state in ('done', 'realized'):
                record.delivery_status = 'delivered'
            elif record.state == 'realization':
                record.delivery_status = 'in_progress'
            else:
                record.delivery_status = 'pending'

    @api.depends('warranty_start_date', 'warranty_duration')
    def _compute_warranty_end(self):
        from dateutil.relativedelta import relativedelta
        for record in self:
            if record.warranty_start_date:
                record.warranty_end_date = record.warranty_start_date + relativedelta(months=record.warranty_duration)
            else:
                record.warranty_end_date = False

    def _expand_states(self, states, domain, order=None):
        """Affiche toutes les colonnes en vue Kanban."""
        return [key for key, val in type(self).state.selection]

    # =====================================================================
    # Transitions d'état
    # =====================================================================
    def action_to_tender(self):
        for rec in self:
            if not rec.partner_id or not rec.tender_number:
                raise UserError(_("Veuillez renseigner le Client et le N° d'Appel d'Offre."))
            rec.state = 'tender'

    def action_to_deliberation(self):
        for rec in self:
            if not rec.tender_submission_deadline:
                raise UserError(_("Veuillez renseigner la Date Limite de Soumission."))
            rec.state = 'deliberation'

    def action_to_notification(self):
        for rec in self:
            if rec.deliberation_result == 'lost':
                raise UserError(_("Le projet a été déclaré 'Null' en délibération. Il ne peut pas avancer."))
            if not rec.deliberation_result:
                raise UserError(_("Veuillez sélectionner le résultat de la délibération."))
            if not rec.offer_validity_date:
                raise UserError(_("Veuillez renseigner la Date de Validité de l'Offre avant de notifier."))
            rec.state = 'notification'

    def action_to_administrative(self):
        for rec in self:
            if not rec.notification_date:
                raise UserError(_("Veuillez renseigner la Date de Notification."))
            if rec.offer_validity_date and rec.offer_validity_date < rec.notification_date:
                raise UserError(_("La validité de l'offre (%s) est dépassée par la date de notification (%s). Veuillez mettre à jour la validité de l'offre.") % (rec.offer_validity_date, rec.notification_date))
            rec.state = 'administrative'

    def action_to_importation(self):
        for rec in self:
            rec.state = 'importation'

    def action_to_realization(self):
        for rec in self:
            rec.state = 'realization'

    def action_done(self):
        for rec in self:
            rec.state = 'done'

    def action_realize(self):
        for rec in self:
            rec.state = 'realized'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    # =====================================================================
    # Synchronisation GBE
    # =====================================================================
    @api.onchange('notification_date', 'caution_gbe_id', 'partner_id', 'tender_number')
    def _onchange_gbe_sync(self):
        """Synchronise les informations vers la caution GBE."""
        if self.caution_gbe_id:
            if self.notification_date:
                self.caution_gbe_id.date_notification = self.notification_date
                # Suggérer une date limite de dépôt (ex: notification + 5 jours)
                if not self.caution_gbe_id.date_limite_depot:
                    self.caution_gbe_id.date_limite_depot = self.notification_date
            
            if self.partner_id and not self.caution_gbe_id.beneficiaire:
                self.caution_gbe_id.beneficiaire = self.partner_id.name
            
            if self.tender_number and not self.caution_gbe_id.name or self.caution_gbe_id.name == '/':
                 # Si la caution n'a pas encore de référence, on peut suggérer le N° d'AO
                 pass

    def write(self, vals):
        from datetime import date
        res = super(ProjectLifecycle, self).write(vals)
        
        # 1. Automatisme État Cautions
        for rec in self:
            # Si le projet est fini (done), on fixe le début de garantie à aujourd'hui si vide
            if 'state' in vals and vals['state'] == 'done' and not rec.warranty_start_date:
                rec.warranty_start_date = date.today()

            # Règle A : Caution de Soumission -> Main Levée dès que la GBE est liée et déposée
            if rec.caution_soumission_id and rec.caution_gbe_id:
                # Si la GBE a une date de dépôt, la soumission est libérée
                if rec.caution_gbe_id.date_depot:
                    rec.caution_soumission_id.state = 'main_levee'
            
            # Règle B : Caution GBE -> Main Levée une fois la garantie finie
            if rec.caution_gbe_id and rec.warranty_end_date:
                if rec.warranty_end_date <= date.today():
                    rec.caution_gbe_id.state = 'main_levee'
                
                # On synchronise aussi la date d'échéance de la GBE avec la fin de garantie du projet
                if rec.caution_gbe_id.date_echeance != rec.warranty_end_date:
                    rec.caution_gbe_id.date_echeance = rec.warranty_end_date

        # 2. Propagation forcée des dates (existant)
        if any(f in vals for f in ['notification_date', 'caution_gbe_id', 'partner_id']):
            for rec in self:
                if rec.caution_gbe_id:
                    sync_vals = {}
                    if rec.notification_date:
                        sync_vals['date_notification'] = rec.notification_date
                    if rec.partner_id:
                        sync_vals['beneficiaire'] = rec.partner_id.name
                    
                    if sync_vals:
                        rec.caution_gbe_id.write(sync_vals)
        return res

    # =====================================================================
    # Actions (Boutons)
    # =====================================================================
    def action_create_import(self):
        """Crée directement un enregistrement d'importation lié au projet."""
        self.ensure_one()
        if self.state != 'importation':
            raise UserError(_("Vous ne pouvez créer une importation que lorsque le projet est en phase d'Importation."))
        
        # On cherche la devise DZD par défaut
        dzd_currency = self.env['res.currency'].search([('name', '=', 'DZD')], limit=1) or self.env.company.currency_id

        new_import = self.env['import.tracking'].create({
            'partner_id': self.partner_id.id,
            'project_id': self.id,
            'initial_currency_id': dzd_currency.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importation'),
            'res_model': 'import.tracking',
            'res_id': new_import.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_imports(self):
        """Ouvre la liste des importations liées."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importations'),
            'res_model': 'import.tracking',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
                'default_partner_id': self.partner_id.id,
            },
        }


class ProjectClientOrder(models.Model):
    _name = 'project.client.order'
    _description = 'Bon de Commande Client'

    project_id = fields.Many2one(
        'project.lifecycle', string='Projet',
        required=True, ondelete='cascade',
    )
    name = fields.Char(string='Référence BC', required=True)
    date = fields.Date(string='Date')
    notes = fields.Text(string='Notes')


# =====================================================================
# Héritage : ajout du champ project_id dans les modèles existants
# =====================================================================
class ImportTrackingInherit(models.Model):
    _inherit = 'import.tracking'

    project_id = fields.Many2one(
        'project.lifecycle', string='Projet',
        tracking=True,
    )


class FinanceCautionInherit(models.Model):
    _inherit = 'finance.caution'

    project_id = fields.Many2one(
        'project.lifecycle', string='Projet',
        tracking=True,
    )
