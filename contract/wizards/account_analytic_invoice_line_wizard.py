# Copyright 2018 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountAnalyticInvoiceLineWizard(models.TransientModel):

    _name = 'account.analytic.invoice.line.wizard'
    _description = 'Contract Line Wizard'

    date_start = fields.Date(string='Date Start')
    date_end = fields.Date(string='Date End')
    contract_line_id = fields.Many2one(
        comodel_name="account.analytic.invoice.line",
        string="Contract Line",
        required=True,
    )

    @api.multi
    def stop(self):
        for wizard in self:
            date_end = (
                wizard.contract_line_id.date_end
                if wizard.contract_line_id.date_end
                and wizard.date_end > wizard.contract_line_id.date_end
                else wizard.date_end
            )
            wizard.contract_line_id.stop(date_end)
        return True

    @api.multi
    def start(self):
        for wizard in self:
            wizard.contract_line_id.start(wizard.date_start, wizard.date_end)
        return True

    @api.multi
    def pause(self):
        for wizard in self:
            remaining_period = False
            if wizard.contract_line_id.date_end:
                remaining_period = (
                    wizard.contract_line_id.date_end - wizard.date_start
                )
            wizard.contract_line_id.pause(wizard.date_start)
            if wizard.date_end:
                date_end = (
                    remaining_period
                    if not remaining_period
                    else wizard.date_end + remaining_period
                )
                wizard.contract_line_id.start(wizard.date_end, date_end)
        return True
