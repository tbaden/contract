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
            wizard.contract_line_id.stop(wizard.date_end)
        return True

    @api.multi
    def start(self):
        for wizard in self:
            wizard.contract_line_id.start(wizard.date_start, wizard.date_end)
        return True
