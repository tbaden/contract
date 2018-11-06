# Copyright 2017 LasLabs Inc.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import api, fields, models


class AccountAnalyticInvoiceLine(models.Model):
    _inherit = 'account.analytic.invoice.line'

    qty_type = fields.Selection(
        selection=[
            ('fixed', 'Fixed quantity'),
            ('variable', 'Variable quantity'),
        ],
        required=True,
        default='fixed',
        string="Qty. type",
    )
    qty_formula_id = fields.Many2one(
        comodel_name="contract.line.qty.formula", string="Qty. formula"
    )

    @api.onchange('product_id')
    def onchange_product(self):
        if self.product_id.is_contract:
            self.qty_type = self.product_id.qty_type
            self.qty_formula_id = self.product_id.qty_formula_id
