# Copyright 2018 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountAnalyticInvoiceLineWizard(models.TransientModel):

    _name = 'account.analytic.invoice.line.wizard'
    _description = 'Contract Line Wizard'

    date_start = fields.Date(string='Date Start')
    date_end = fields.Date(string='Date End')
    recurring_next_date = fields.Date(string='Date of Next Invoice')
    contract_line_id = fields.Many2one(
        comodel_name="account.analytic.invoice.line",
        string="Contract Line",
        required=True,
    )

    @api.onchange('date_start')
    def onchange_date_start(self):
        contract_line_env = self.env['account.analytic.invoice.line']
        for rec in self:
            if rec.date_start:
                rec.recurring_next_date = \
                    contract_line_env._compute_first_recurring_next_date(
                        rec.date_start,
                        rec.contract_line_id.recurring_invoicing_type,
                        rec.contract_line_id.recurring_rule_type,
                        rec.contract_line_id.recurring_interval,
                    )

    @api.multi
    def stop(self):
        for wizard in self:
            wizard.contract_line_id.date_end = wizard.date_end
        return True

    @api.multi
    def start(self):
        contract_line_env = self.env['account.analytic.invoice.line']
        for wizard in self:
            new_vals = wizard.contract_line_id.read()[0]
            values = wizard.contract_line_id._convert_to_write(new_vals)
            values['date_start'] = wizard.date_start
            values['date_end'] = wizard.date_end
            values['recurring_next_date'] = wizard.recurring_next_date
            values['origin_id'] = wizard.contract_line_id.id
            contract_line_env.create(values)
        return True
