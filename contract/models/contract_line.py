# Copyright 2017 LasLabs Inc.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountAnalyticInvoiceLine(models.Model):
    _name = 'account.analytic.invoice.line'
    _inherit = 'account.abstract.analytic.contract.line'

    contract_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string='Analytic Account',
        required=True,
        ondelete='cascade',
        oldname='analytic_account_id',
    )
    date_start = fields.Date(string='Date Start', default=fields.Date.today())
    date_end = fields.Date(string='Date End', index=True)
    recurring_next_date = fields.Date(string='Date of Next Invoice')
    create_invoice_visibility = fields.Boolean(
        compute='_compute_create_invoice_visibility'
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner (always False)",
        related='contract_id.partner_id',
        store=True,
        readonly=True,
    )
    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string='Pricelist',
        related='contract_id.pricelist_id',
        store=True,
        readonly=True,
    )
    successor_contract_line_id = fields.Many2one(
        comodel_name='account.analytic.invoice.line',
        string="Successor Contract Line",
        required=False,
        readonly=True,
        copy=False,
        help="Contract Line created by this one.",
    )
    predecessor_contract_line_id = fields.Many2one(
        comodel_name='account.analytic.invoice.line',
        string="Predecessor Contract Line",
        required=False,
        readonly=True,
        copy=False,
        help="Contract Line origin of this one.",
    )
    is_start_allowed = fields.Boolean(
        string="Start allowed?", compute='_compute_start_allowed'
    )
    is_pause_allowed = fields.Boolean(
        string="Pause allowed?", compute='_compute_pause_allowed'
    )
    is_stop_allowed = fields.Boolean(
        string="Stop allowed?", compute='_compute_stop_allowed'
    )

    @api.multi
    def _compute_start_allowed(self):
        for rec in self:
            rec.is_start_allowed = False
            if (
                rec.date_end
                and not rec.successor_contract_line_id
                and not rec.is_canceled
            ):
                rec.is_start_allowed = True

    @api.multi
    def _compute_pause_allowed(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_pause_allowed = False
            if (
                not rec.date_end
                or (rec.date_end and today < rec.date_end)
                and not rec.is_canceled
            ):
                rec.is_pause_allowed = True

    @api.multi
    def _compute_stop_allowed(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_stop_allowed = False
            if (
                rec.date_end
                and today < rec.date_end
                and rec.is_auto_renew
                and not rec.successor_contract_line_id
                and not rec.is_canceled
            ):
                rec.is_stop_allowed = True

    @api.constrains('is_auto_renew', 'successor_contract_line_id', 'date_end')
    def _check_auto_renew(self):
        """
            logical impossible combination:
                * a line with is_auto_renew True should have date_end and
                  couldn't have successor_contract_line_id
                * a line without date_end can't have successor_contract_line_id

        """
        for rec in self:
            if rec.is_auto_renew:
                if rec.successor_contract_line_id:
                    raise ValidationError(
                        _(
                            "A contract line with a successor "
                            "can't be set to auto-renew"
                        )
                    )
                if not rec.date_end:
                    raise ValidationError(
                        _("An auto-renew line should have a " "date end ")
                    )
            else:
                if not rec.date_end and rec.successor_contract_line_id:
                    raise ValidationError(
                        _(
                            "A contract line with a successor "
                            "should have date end"
                        )
                    )

    @api.constrains('successor_contract_line_id', 'date_end')
    def _check_overlap_successor(self):
        for rec in self:
            if rec.date_end and rec.successor_contract_line_id:
                if rec.date_end > rec.successor_contract_line_id.date_start:
                    raise ValidationError(
                        _("Contract line and its successor overlapped")
                    )

    @api.model
    def _compute_first_recurring_next_date(
        self,
        date_start,
        recurring_invoicing_type,
        recurring_rule_type,
        recurring_interval,
    ):
        if recurring_rule_type == 'monthlylastday':
            return date_start + self.get_relative_delta(
                recurring_rule_type, recurring_interval - 1
            )
        if recurring_invoicing_type == 'pre-paid':
            return date_start
        return date_start + self.get_relative_delta(
            recurring_rule_type, recurring_interval
        )

    @api.onchange(
        'date_start',
        'recurring_invoicing_type',
        'recurring_rule_type',
        'recurring_interval',
    )
    def _onchange_date_start(self):
        for rec in self.filtered('date_start'):
            rec.recurring_next_date = self._compute_first_recurring_next_date(
                rec.date_start,
                rec.recurring_invoicing_type,
                rec.recurring_rule_type,
                rec.recurring_interval,
            )

    @api.constrains('recurring_next_date', 'date_start')
    def _check_recurring_next_date_start_date(self):
        for line in self.filtered('recurring_next_date'):
            if line.date_start and line.recurring_next_date:
                if line.date_start > line.recurring_next_date:
                    raise ValidationError(
                        _(
                            "You can't have a next invoicing date before the "
                            "start of the contract '%s'"
                        )
                        % line.contract_id.name
                    )

    @api.constrains('recurring_next_date')
    def _check_recurring_next_date_recurring_invoices(self):
        for line in self.filtered('contract_id.recurring_invoices'):
            if not line.recurring_next_date:
                raise ValidationError(
                    _(
                        "You must supply a next invoicing date for contract "
                        "'%s'"
                    )
                    % line.contract_id.name
                )

    @api.constrains('date_start')
    def _check_date_start_recurring_invoices(self):
        for line in self.filtered('contract_id.recurring_invoices'):
            if not line.date_start:
                raise ValidationError(
                    _("You must supply a start date for contract '%s'")
                    % line.contract_id.name
                )

    @api.constrains('date_start', 'date_end')
    def _check_start_end_dates(self):
        for line in self.filtered('date_end'):
            if line.date_start and line.date_end:
                if line.date_start > line.date_end:
                    raise ValidationError(
                        _(
                            "Contract '%s' start date can't be later than "
                            "end date"
                        )
                        % line.contract_id.name
                    )

    @api.depends('recurring_next_date', 'date_end')
    def _compute_create_invoice_visibility(self):
        for line in self:
            line.create_invoice_visibility = not line.date_end or (
                line.recurring_next_date
                and line.date_end
                and line.recurring_next_date <= line.date_end
            )

    @api.model
    def recurring_create_invoice(self, contract=False):
        domain = []
        date_ref = fields.Date.today()
        if contract:
            contract.ensure_one()
            date_ref = contract.recurring_next_date
            domain.append(('contract_id', '=', contract.id))

        domain.extend(
            [
                ('contract_id.recurring_invoices', '=', True),
                ('recurring_next_date', '<=', date_ref),
                ('is_canceled', '=', False),
                '|',
                ('date_end', '=', False),
                ('date_end', '>=', date_ref),
            ]
        )
        lines = self.search(domain).filtered('create_invoice_visibility')
        if lines:
            return lines._recurring_create_invoice()
        return False

    @api.multi
    def _recurring_create_invoice(self):
        """Create invoices from contracts

        :return: invoices created
        """
        invoices = self.env['account.invoice']
        for contract in self.mapped('contract_id'):
            lines = self.filtered(lambda l: l.contract_id == contract)
            invoices |= lines._create_invoice()
            lines._update_recurring_next_date()
        return invoices

    @api.multi
    def _create_invoice(self):
        """
        :param invoice: If not False add lines to this invoice
        :return: invoice created or updated
        """
        contract = self.mapped('contract_id')
        date_invoice = min(self.mapped('recurring_next_date'))
        invoice = self.env['account.invoice'].create(
            contract._prepare_invoice(date_invoice)
        )
        for line in self:
            invoice_line_vals = line._prepare_invoice_line(invoice.id)
            if invoice_line_vals:
                self.env['account.invoice.line'].create(invoice_line_vals)
        invoice.compute_taxes()
        return invoice

    @api.multi
    def _prepare_invoice_line(self, invoice_id):
        self.ensure_one()
        invoice_line = self.env['account.invoice.line'].new(
            {
                'invoice_id': invoice_id,
                'product_id': self.product_id.id,
                'quantity': self.quantity,
                'uom_id': self.uom_id.id,
                'discount': self.discount,
            }
        )
        # Get other invoice line values from product onchange
        invoice_line._onchange_product_id()
        invoice_line_vals = invoice_line._convert_to_write(invoice_line._cache)
        # Insert markers
        contract = self.contract_id
        lang_obj = self.env['res.lang']
        lang = lang_obj.search([('code', '=', contract.partner_id.lang)])
        date_format = lang.date_format or '%m/%d/%Y'
        name = self._insert_markers(date_format)
        invoice_line_vals.update(
            {
                'name': name,
                'account_analytic_id': contract.id,
                'price_unit': self.price_unit,
            }
        )
        return invoice_line_vals

    @api.multi
    def _insert_markers(self, date_format):
        self.ensure_one()
        date_from = fields.Date.from_string(self.recurring_next_date)
        date_to = date_from + self.get_relative_delta(
            self.recurring_rule_type, self.recurring_interval
        )
        name = self.name
        name = name.replace('#START#', date_from.strftime(date_format))
        name = name.replace('#END#', date_to.strftime(date_format))
        return name

    @api.multi
    def _update_recurring_next_date(self):
        for line in self:
            ref_date = line.recurring_next_date or fields.Date.today()
            old_date = fields.Date.from_string(ref_date)
            new_date = old_date + self.get_relative_delta(
                line.recurring_rule_type, line.recurring_interval
            )
            line.recurring_next_date = new_date

    @api.model
    def get_relative_delta(self, recurring_rule_type, interval):
        if recurring_rule_type == 'daily':
            return relativedelta(days=interval)
        elif recurring_rule_type == 'weekly':
            return relativedelta(weeks=interval)
        elif recurring_rule_type == 'monthly':
            return relativedelta(months=interval)
        elif recurring_rule_type == 'monthlylastday':
            return relativedelta(months=interval, day=31)
        else:
            return relativedelta(years=interval)

    @api.multi
    def stop(self, date_end):
        if not all(self.mapped('is_stop_allowed')):
            raise ValidationError(_('Stop not allowed for this line'))
        return self.write({'date_end': date_end, 'is_auto_renew': False})

    @api.multi
    def _prepare_value_for_start(
        self, date_start, date_end, recurring_next_date=False
    ):
        self.ensure_one()
        if not recurring_next_date:
            recurring_next_date = self._compute_first_recurring_next_date(
                date_start,
                self.recurring_invoicing_type,
                self.recurring_rule_type,
                self.recurring_interval,
            )
        new_vals = self.read()[0]
        new_vals.pop("id", None)
        values = self._convert_to_write(new_vals)
        values['date_start'] = date_start
        values['date_end'] = date_end
        values['recurring_next_date'] = recurring_next_date
        values['predecessor_contract_line_id'] = self.id
        return values

    @api.multi
    def start(self, date_start, date_end, recurring_next_date=False):
        contract_line = self.env['account.analytic.invoice.line']
        for rec in self:
            if not rec.is_start_allowed:
                raise ValidationError(_('Start not allowed for this line'))
            new_line = self.create(
                rec._prepare_value_for_start(
                    date_start, date_end, recurring_next_date
                )
            )
            rec.successor_contract_line_id = new_line
            contract_line |= new_line
        return contract_line

    @api.multi
    def pause(self, date_end):
        if not all(self.mapped('is_pause_allowed')):
            raise ValidationError(_('Pause not allowed for this line'))
        return self.write({'date_end': date_end})

    @api.multi
    def cancel(self):
        return self.write({'is_canceled': True})

    @api.multi
    def uncancel(self):
        return self.write({'is_canceled': False})

    @api.multi
    def action_start(self):
        self.ensure_one()
        context = {'default_contract_line_id': self.id}
        context.update(self.env.context)
        view_id = self.env.ref(
            'contract.account_analytic_invoice_line_wizard_start_form_view'
        ).id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reactivate contract line',
            'res_model': 'account.analytic.invoice.line.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': context,
        }

    @api.multi
    def action_stop(self):
        self.ensure_one()
        context = {
            'default_contract_line_id': self.id,
            'default_date_end': self.date_end,
        }
        context.update(self.env.context)
        view_id = self.env.ref(
            'contract.account_analytic_invoice_line_wizard_stop_form_view'
        ).id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Resiliate contract line',
            'res_model': 'account.analytic.invoice.line.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': context,
        }

    @api.multi
    def action_pause(self):
        self.ensure_one()
        context = {
            'default_contract_line_id': self.id,
            'default_date_end': self.date_end,
        }
        context.update(self.env.context)
        view_id = self.env.ref(
            'contract.account_analytic_invoice_line_wizard_pause_form_view'
        ).id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Suspend contract line',
            'res_model': 'account.analytic.invoice.line.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': context,
        }

    @api.multi
    def _get_renewal_dates(self):
        self.ensure_one()
        date_start = self.date_end
        date_end = date_start + self.get_relative_delta(
            self.auto_renew_rule_type, self.auto_renew_interval
        )
        return date_start, date_end

    @api.multi
    def renew(self):
        res = self.env['account.analytic.invoice.line']
        for rec in self:
            is_auto_renew = rec.is_auto_renew
            rec.stop(rec.date_end)
            date_start, date_end = rec._get_renewal_dates()
            new_line = rec.start(date_start, date_end, date_start)
            new_line._onchange_date_start()
            new_line.is_auto_renew = is_auto_renew
            res |= new_line
        return res

    @api.model
    def _search_contract_line_to_renew(self):
        date_ref = fields.datetime.today() + self.get_relative_delta(
            self.termination_notice_rule_type, self.termination_notice_interval
        )
        return self.search(
            [
                ('is_auto_renew', '=', True),
                ('date_end', '<=', date_ref),
                ('is_canceled', '=', False),
            ]
        )

    @api.model
    def cron_renew_contract_line(self):
        to_renew = self._search_contract_line_to_renew()
        to_renew.renew()
